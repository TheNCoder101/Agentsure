"""API keys, plans, and credit metering (SQLite).

Commercial model mirrors Tavily's: self-serve key with a free monthly credit
allowance and no card required; paid tiers raise the allowance; requests cost
credits by rigor (deeper verification = more credits). Keys are stored as
SHA-256 hashes — the plaintext key is shown exactly once at creation.
"""

import hashlib
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from app.models import RigorLevel

KEY_PREFIX = "vg-"

# Credits per /verify call, by rigor (cf. Tavily: basic search 1, advanced 2).
CREDIT_COST: dict[RigorLevel, int] = {
    RigorLevel.FAST: 1,
    RigorLevel.STANDARD: 2,
    RigorLevel.STRICT: 3,
}

# Monthly credit allowance per plan. None = usage-billed, no hard cap.
PLAN_CREDITS: dict[str, int | None] = {
    "free": 1_000,
    "payg": None,
    "starter": 4_000,
    "growth": 15_000,
    "enterprise": None,
}

SELF_SERVE_PLAN = "free"


class InsufficientCreditsError(Exception):
    """Raised when a key's monthly credit allowance is exhausted."""


@dataclass(frozen=True)
class KeyRecord:
    key_id: int
    email: str
    plan: str


@dataclass(frozen=True)
class SessionSummaryData:
    session_id: str
    total_checks: int
    verdict_counts: dict[str, int]
    unsupported_rate_trend: list[float]
    receipt_ids: list[str]


@dataclass(frozen=True)
class UsageInfo:
    plan: str
    period: str
    credits_used: int
    credits_limit: int | None

    @property
    def credits_remaining(self) -> int | None:
        if self.credits_limit is None:
            return None
        return max(0, self.credits_limit - self.credits_used)


def _db_path() -> str:
    return os.environ.get("VG_DB_PATH", "verification_gate.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _current_period() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def _hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_hash TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL,
                plan TEXT NOT NULL DEFAULT 'free',
                created_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS usage (
                key_id INTEGER NOT NULL REFERENCES api_keys(id),
                period TEXT NOT NULL,
                credits_used INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (key_id, period)
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS receipts (
                receipt_id TEXT PRIMARY KEY,
                key_id INTEGER NOT NULL REFERENCES api_keys(id),
                session_id TEXT,
                verdict TEXT NOT NULL,
                confidence REAL NOT NULL,
                issued_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_receipts_session "
            "ON receipts (key_id, session_id, issued_at)"
        )


def create_key(email: str, plan: str = SELF_SERVE_PLAN) -> str:
    if plan not in PLAN_CREDITS:
        raise ValueError(f"unknown plan: {plan}")
    api_key = KEY_PREFIX + secrets.token_urlsafe(24)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO api_keys (key_hash, email, plan, created_at) VALUES (?, ?, ?, ?)",
            (_hash_key(api_key), email, plan, datetime.now(UTC).isoformat()),
        )
    return api_key


def resolve_key(api_key: str) -> KeyRecord | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, email, plan FROM api_keys WHERE key_hash = ?",
            (_hash_key(api_key),),
        ).fetchone()
    if row is None:
        return None
    return KeyRecord(key_id=row[0], email=row[1], plan=row[2])


def charge(record: KeyRecord, credits: int) -> None:
    """Atomically debit credits for the current period; raise when exhausted."""
    limit = PLAN_CREDITS[record.plan]
    period = _current_period()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT OR IGNORE INTO usage (key_id, period, credits_used) VALUES (?, ?, 0)",
            (record.key_id, period),
        )
        row = conn.execute(
            "SELECT credits_used FROM usage WHERE key_id = ? AND period = ?",
            (record.key_id, period),
        ).fetchone()
        used = int(row[0])
        if limit is not None and used + credits > limit:
            conn.rollback()
            raise InsufficientCreditsError(
                f"monthly credit limit reached ({used}/{limit} used on the "
                f"'{record.plan}' plan)"
            )
        conn.execute(
            "UPDATE usage SET credits_used = credits_used + ? WHERE key_id = ? AND period = ?",
            (credits, record.key_id, period),
        )
        conn.commit()
    finally:
        conn.close()


def set_plan(record: KeyRecord, plan: str) -> KeyRecord:
    """Move a key to a new plan. In production this is called by the billing
    webhook after checkout completes; the endpoint simulates that step until
    Stripe is wired in."""
    if plan not in PLAN_CREDITS:
        raise ValueError(f"unknown plan: {plan}")
    with _connect() as conn:
        conn.execute("UPDATE api_keys SET plan = ? WHERE id = ?", (plan, record.key_id))
    return KeyRecord(key_id=record.key_id, email=record.email, plan=plan)


def record_receipt(
    record: KeyRecord,
    session_id: str | None,
    receipt_id: str,
    verdict: str,
    confidence: float,
    issued_at: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO receipts (receipt_id, key_id, session_id, verdict, confidence, "
            "issued_at) VALUES (?, ?, ?, ?, ?, ?)",
            (receipt_id, record.key_id, session_id, verdict, confidence, issued_at),
        )


def session_summary(record: KeyRecord, session_id: str) -> SessionSummaryData:
    """Aggregate every receipt issued under this key for one session_id.

    Turns a pile of point-in-time receipts into a trend a compliance officer
    can act on: a rising non-supported rate across a session is a signal no
    single receipt can carry on its own.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT receipt_id, verdict FROM receipts WHERE key_id = ? AND session_id = ? "
            "ORDER BY issued_at",
            (record.key_id, session_id),
        ).fetchall()

    verdict_counts: dict[str, int] = {}
    trend: list[float] = []
    non_supported = 0
    for i, (_, verdict) in enumerate(rows, start=1):
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        if verdict != "supported":
            non_supported += 1
        trend.append(round(non_supported / i, 4))

    return SessionSummaryData(
        session_id=session_id,
        total_checks=len(rows),
        verdict_counts=verdict_counts,
        unsupported_rate_trend=trend,
        receipt_ids=[r[0] for r in rows],
    )


def get_usage(record: KeyRecord) -> UsageInfo:
    period = _current_period()
    with _connect() as conn:
        row = conn.execute(
            "SELECT credits_used FROM usage WHERE key_id = ? AND period = ?",
            (record.key_id, period),
        ).fetchone()
    return UsageInfo(
        plan=record.plan,
        period=period,
        credits_used=int(row[0]) if row else 0,
        credits_limit=PLAN_CREDITS[record.plan],
    )
