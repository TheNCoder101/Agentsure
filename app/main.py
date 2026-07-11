import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

from app.accounts import store
from app.models import Receipt, ReceiptVerifyResponse, VerifyRequest, VerifyResponse
from app.receipt.build import build_receipt
from app.receipt.export import to_csv, to_pdf
from app.receipt.sign import SigningKeyMissingError, verify_signature
from app.verify.judge import AnthropicJudge, HeuristicJudge, JudgeClient
from app.verify.pipeline import run_verification

_LANDING_PAGE = Path(__file__).parent / "web" / "landing.html"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    store.init_db()
    yield


app = FastAPI(title="Verification Gate", lifespan=_lifespan)


@lru_cache(maxsize=1)
def _anthropic_judge() -> AnthropicJudge:
    return AnthropicJudge()


def get_judge() -> JudgeClient:
    # Real judge in any environment with credentials configured; heuristic
    # stand-in only as a fallback (e.g. local dev without an API key).
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _anthropic_judge()
    return HeuristicJudge()


def require_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> store.KeyRecord:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="missing X-API-Key header")
    record = store.resolve_key(x_api_key)
    if record is None:
        raise HTTPException(status_code=401, detail="invalid API key")
    return record


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing() -> str:
    return _LANDING_PAGE.read_text()


class CreateKeyRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class CreateKeyResponse(BaseModel):
    api_key: str
    plan: str
    monthly_credits: int | None
    note: str


@app.post("/keys", status_code=201)
async def create_key(body: CreateKeyRequest) -> CreateKeyResponse:
    if not _EMAIL.match(body.email):
        raise HTTPException(status_code=422, detail="invalid email address")
    api_key = store.create_key(body.email)
    return CreateKeyResponse(
        api_key=api_key,
        plan=store.SELF_SERVE_PLAN,
        monthly_credits=store.PLAN_CREDITS[store.SELF_SERVE_PLAN],
        note="Store this key now — it is shown only once and held hashed at rest.",
    )


@app.post("/verify")
async def verify(
    body: VerifyRequest,
    key: Annotated[store.KeyRecord, Depends(require_api_key)],
    judge: Annotated[JudgeClient, Depends(get_judge)],
) -> VerifyResponse:
    try:
        store.charge(key, store.CREDIT_COST[body.rigor_level])
    except store.InsufficientCreditsError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    result = run_verification(body.output, body.source_documents, body.rigor_level, judge)
    try:
        receipt = build_receipt(
            body.output, body.source_documents, result.verdict, body.rigor_level
        )
    except SigningKeyMissingError as exc:
        raise HTTPException(status_code=503, detail="signing key not configured") from exc
    store.save_receipt(key, receipt)
    return VerifyResponse(
        verdict=result.verdict,
        unsupported_claims=result.unsupported_claims,
        per_claim_evidence=result.per_claim_evidence,
        confidence=result.confidence,
        receipt=receipt,
    )


@app.post("/receipt/verify")
async def receipt_verify(receipt: Receipt) -> ReceiptVerifyResponse:
    try:
        valid = verify_signature(receipt.model_dump(mode="json"))
    except SigningKeyMissingError as exc:
        raise HTTPException(status_code=503, detail="signing key not configured") from exc
    return ReceiptVerifyResponse(valid=valid)


class ReceiptListResponse(BaseModel):
    receipts: list[Receipt]


@app.get("/receipts", response_model=None)
async def list_receipts(
    key: Annotated[store.KeyRecord, Depends(require_api_key)],
    format: str = "json",
    limit: int = 100,
) -> ReceiptListResponse | PlainTextResponse:
    receipts = store.list_receipts(key, limit=limit)
    if format == "csv":
        return PlainTextResponse(
            to_csv(receipts),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=receipts.csv"},
        )
    return ReceiptListResponse(receipts=receipts)


@app.get("/receipts/{receipt_id}")
async def get_receipt(
    receipt_id: str, key: Annotated[store.KeyRecord, Depends(require_api_key)]
) -> Receipt:
    receipt = store.get_receipt(key, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="receipt not found")
    return receipt


@app.get("/receipts/{receipt_id}/pdf")
async def get_receipt_pdf(
    receipt_id: str, key: Annotated[store.KeyRecord, Depends(require_api_key)]
) -> Response:
    receipt = store.get_receipt(key, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="receipt not found")
    return Response(
        content=to_pdf(receipt),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={receipt_id}.pdf"},
    )


class SubscribeRequest(BaseModel):
    plan: str


class SubscribeResponse(BaseModel):
    plan: str
    monthly_credits: int | None
    note: str


@app.post("/subscribe")
async def subscribe(
    body: SubscribeRequest,
    key: Annotated[store.KeyRecord, Depends(require_api_key)],
) -> SubscribeResponse:
    if body.plan not in store.PLAN_CREDITS:
        raise HTTPException(status_code=422, detail=f"unknown plan: {body.plan}")
    if body.plan == "enterprise":
        raise HTTPException(
            status_code=422, detail="enterprise is sales-assisted — contact sales@agentsure.dev"
        )
    updated = store.set_plan(key, body.plan)
    return SubscribeResponse(
        plan=updated.plan,
        monthly_credits=store.PLAN_CREDITS[updated.plan],
        note="Plan updated. Payment collection is handled at checkout once billing goes live.",
    )


class UsageResponse(BaseModel):
    plan: str
    period: str
    credits_used: int
    credits_limit: int | None
    credits_remaining: int | None


@app.get("/usage")
async def usage(key: Annotated[store.KeyRecord, Depends(require_api_key)]) -> UsageResponse:
    info = store.get_usage(key)
    return UsageResponse(
        plan=info.plan,
        period=info.period,
        credits_used=info.credits_used,
        credits_limit=info.credits_limit,
        credits_remaining=info.credits_remaining,
    )
