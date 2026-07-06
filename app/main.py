from fastapi import FastAPI

app = FastAPI(title="Verification Gate")


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}
