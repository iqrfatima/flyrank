from __future__ import annotations

from sqlalchemy.orm import Session

from app.exceptions import QuotaExceededError
from app.models import UsageEvent
from app.services import tenant as tenant_service


def total_tokens(meta: dict) -> int:
    return (
        int(meta.get("input") or 0)
        + int(meta.get("cached_input") or 0)
        + int(meta.get("output") or 0)
        + int(meta.get("reasoning") or 0)
    )


def check_quota(session: Session, tenant, plan, extra_calls: int = 0, extra_tokens: int = 0):
    if tenant.status in ("payment_failed", "cancelled"):
        raise QuotaExceededError(
            "Subscription inactive. Please update payment or resubscribe to continue.",
            402,
        )

    usage = tenant_service.get_usage_rollup(session, tenant.id)
    projected_calls = usage["api_calls_used"] + extra_calls
    projected_tokens = usage["ai_tokens_used"] + extra_tokens

    if projected_calls > plan.api_calls_limit:
        raise QuotaExceededError(
            f"API call quota exceeded. Used {usage['api_calls_used']}/{plan.api_calls_limit}. "
            "Upgrade your plan or wait until next billing period.",
            402 if plan.name == "Free" else 429,
        )
    if projected_tokens > plan.ai_tokens_limit:
        raise QuotaExceededError(
            f"AI token quota exceeded. Used {usage['ai_tokens_used']}/{plan.ai_tokens_limit}. "
            "Upgrade your plan or wait until next billing period.",
            402 if plan.name == "Free" else 429,
        )
    return usage


def record_usage(session: Session, tenant, plan, idempotency_key: str, token_usage: dict | None):
    from sqlalchemy.exc import IntegrityError

    existing = tenant_service.find_event(session, tenant.id, idempotency_key)
    if existing:
        return existing, True

    extra_tokens = total_tokens(token_usage) if token_usage else 0
    check_quota(session, tenant, plan, extra_calls=1, extra_tokens=extra_tokens)

    try:
        with session.begin_nested():
            event = UsageEvent(
                tenant_id=tenant.id,
                event_type="api_call",
                quantity=1,
                idempotency_key=idempotency_key,
                extra={"source": "generate", "path": (token_usage or {}).get("path")},
            )
            session.add(event)
            session.flush()

            if token_usage:
                token_key = f"{idempotency_key}:tokens"
                token_dup = tenant_service.find_event(session, tenant.id, token_key)
                if not token_dup:
                    session.add(
                        UsageEvent(
                            tenant_id=tenant.id,
                            event_type="ai_tokens",
                            quantity=total_tokens(token_usage),
                            idempotency_key=token_key,
                            extra=token_usage,
                        )
                    )
                    session.flush()
        return event, False
    except IntegrityError:
        existing = tenant_service.find_event(session, tenant.id, idempotency_key)
        if existing:
            return existing, True
        raise

