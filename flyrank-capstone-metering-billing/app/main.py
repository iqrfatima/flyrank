from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import PORT
from app.db import SessionLocal
from app.exceptions import QuotaExceededError
from app.routers.api import router as api_router
from app.routers.webhooks import router as webhook_router
from app.services.rollup import run_usage_rollup

PUBLIC = Path(__file__).resolve().parent.parent / "public"


def _rollup_loop(interval_seconds: int = 3600):
    def tick():
        session = SessionLocal()
        try:
            run_usage_rollup(session)
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
        timer = threading.Timer(interval_seconds, tick)
        timer.daemon = True
        timer.start()

    starter = threading.Timer(5, tick)
    starter.daemon = True
    starter.start()
    print("[job:usage_rollup] Scheduler started")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _rollup_loop()
    yield


app = FastAPI(title="Usage Metering & Billing Engine", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_handler(_request: Request, err: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"error": "Validation Error", "messages": [e["msg"] for e in err.errors()]},
    )


@app.exception_handler(HTTPException)
async def http_handler(_request: Request, err: HTTPException):
    detail = err.detail
    if isinstance(detail, dict):
        return JSONResponse(status_code=err.status_code, content=detail)
    return JSONResponse(status_code=err.status_code, content={"error": str(detail)})


@app.exception_handler(QuotaExceededError)
async def quota_handler(_request: Request, err: QuotaExceededError):
    headers = {"Retry-After": "3600"} if err.status_code == 429 else {}
    return JSONResponse(
        status_code=err.status_code,
        headers=headers,
        content={
            "error": "Payment Required" if err.status_code == 402 else "Too Many Requests",
            "message": err.message,
        },
    )


@app.exception_handler(Exception)
async def unhandled(_request: Request, err: Exception):
    print("[error]", err)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "message": "An unexpected error occurred."},
    )


app.include_router(webhook_router)
app.include_router(api_router)


@app.get("/health")
def health():
    return {"status": "ok"}


if PUBLIC.exists():
    app.mount("/assets", StaticFiles(directory=PUBLIC), name="assets")


@app.get("/")
def index():
    return FileResponse(PUBLIC / "index.html")


def run():
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, reload=False)


if __name__ == "__main__":
    run()
