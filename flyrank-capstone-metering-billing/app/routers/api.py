from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from app.db import get_session
from app.exceptions import QuotaExceededError
from app.services import meter, tenant as tenant_service
from app.services.cost import calculate_usage_cost
from app.services.optimizer import compare_paths, simulate_provider_usage
from app.services.razorpay_service import create_subscription_checkout, is_configured

router = APIRouter(prefix="/api")


class GenerateBody(BaseModel):
    prompt: str = "Explain this month's usage in one paragraph."
    path: str = Field(default="direct", description="direct | mcp_lean | mcp_noisy")
    input_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)


class AnalyzeBody(BaseModel):
    prompt: str = "Explain this month's usage in one paragraph."


def require_tenant(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: Session = Depends(get_session),
):
    if not x_api_key or len(x_api_key) < 8:
        raise HTTPException(401, detail={"error": "Unauthorized", "message": "Missing or invalid X-API-Key header."})
    row = tenant_service.get_tenant_by_api_key(session, x_api_key)
    if not row:
        raise HTTPException(401, detail={"error": "Unauthorized", "message": "Invalid API key."})
    return row


def _token_usage(body: GenerateBody) -> dict:
    if any(
        v is not None
        for v in (body.input_tokens, body.cached_input_tokens, body.output_tokens, body.reasoning_tokens)
    ):
        usage = {
            "input": body.input_tokens or 0,
            "cached_input": body.cached_input_tokens or 0,
            "output": body.output_tokens or 0,
            "reasoning": body.reasoning_tokens or 0,
            "path": "manual",
            "notes": "Caller supplied provider-reported token counts.",
        }
    else:
        usage = simulate_provider_usage(body.prompt, body.path).as_dict()
    return usage


@router.get("/plans")
def plans(session: Session = Depends(get_session)):
    rows = tenant_service.list_plans(session)
    return {
        "razorpayEnabled": is_configured(),
        "plans": [
            {
                "id": p.id,
                "name": p.name,
                "api_calls_limit": p.api_calls_limit,
                "ai_tokens_limit": p.ai_tokens_limit,
                "price_cents": p.price_cents,
            }
            for p in rows
        ],
    }


@router.get("/demo-keys")
def demo_keys(session: Session = Depends(get_session)):
    return tenant_service.get_demo_keys(session)



@router.post("/analyze")
def analyze(body: AnalyzeBody):
    """Non-billable comparison of Direct vs MCP paths. Does not write usage events."""
    return compare_paths(body.prompt)


@router.get("/usage")
def usage(ctx=Depends(require_tenant), session: Session = Depends(get_session)):
    tenant, plan = ctx
    rollup = tenant_service.get_usage_rollup(session, tenant.id)
    cost = calculate_usage_cost(rollup["api_calls_used"], rollup["token_breakdown"])
    return {
        "tenant": {"id": tenant.id, "name": tenant.name, "plan": plan.name, "status": tenant.status},
        "period": {"start": rollup["period_start"], "end": rollup["period_end"]},
        "usage": {
            "apiCalls": {"used": rollup["api_calls_used"], "limit": plan.api_calls_limit},
            "aiTokens": {"used": rollup["ai_tokens_used"], "limit": plan.ai_tokens_limit},
            "tokenBreakdown": rollup["token_breakdown"],
            "tokensByPath": rollup["tokens_by_path"],
        },
        "cost": {
            "apiCallsCents": cost["api_calls_cost_cents"],
            "tokensCents": cost["tokens_cost_cents"],
            "totalCents": cost["total_cost_cents"],
            "currency": "INR",
        },
    }


@router.post("/generate")
def generate(
    request: Request,
    body: GenerateBody,
    ctx=Depends(require_tenant),
    session: Session = Depends(get_session),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if not idempotency_key or len(idempotency_key.strip()) < 8 or len(idempotency_key) > 128:
        raise HTTPException(
            400,
            detail={"error": "Bad Request", "message": "Idempotency-Key header is required (8–128 characters)."},
        )
    tenant, plan = ctx
    token_usage = _token_usage(body)
    try:
        event, duplicate = meter.record_usage(session, tenant, plan, idempotency_key.strip(), token_usage)
    except QuotaExceededError as err:
        headers = {"Retry-After": "3600"} if err.status_code == 429 else {}
        return JSONResponse(
            status_code=err.status_code,
            headers=headers,
            content={
                "error": "Payment Required" if err.status_code == 402 else "Too Many Requests",
                "message": err.message,
                "retryAfter": 3600 if err.status_code == 429 else None,
            },
        )
    if duplicate:
        token_dup = tenant_service.find_event(session, tenant.id, f"{idempotency_key.strip()}:tokens")
        if token_dup and token_dup.extra:
            token_usage = token_dup.extra

    rollup = tenant_service.get_usage_rollup(session, tenant.id)
    return JSONResponse(
        status_code=200 if duplicate else 201,
        content={
            "message": "Idempotent replay — no duplicate charge" if duplicate else "Usage recorded",
            "duplicate": duplicate,
            "eventId": event.id,
            "providerUsage": token_usage,
            "simulatedResponse": {
                "text": "Simulated LLM answer. Tokens come from the provider-usage report, not a real model.",
                "path": token_usage.get("path"),
            },
            "usage": {
                "apiCallsUsed": rollup["api_calls_used"],
                "aiTokensUsed": rollup["ai_tokens_used"],
            },
        },
    )


@router.post("/checkout")
def checkout(ctx=Depends(require_tenant), session: Session = Depends(get_session)):
    tenant, plan = ctx
    if not is_configured():
        raise HTTPException(
            503,
            detail={
                "error": "Service Unavailable",
                "message": "Razorpay is not configured. Use the seeded Pro API key, or add test keys to .env.",
            },
        )
    if plan.name == "Pro" and tenant.status == "active":
        raise HTTPException(400, detail={"error": "Bad Request", "message": "Tenant is already on an active Pro plan."})
    try:
        return create_subscription_checkout(session, tenant)
    except RuntimeError as err:
        raise HTTPException(getattr(err, "status_code", 500), detail={"error": str(err)}) from err
