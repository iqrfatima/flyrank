from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Plan, Tenant, UsageEvent, WebhookEvent
from app.services.cost import current_period_bounds


def get_tenant_by_api_key(session: Session, api_key: str) -> tuple[Tenant, Plan] | None:
    row = session.execute(
        select(Tenant, Plan).join(Plan, Plan.id == Tenant.plan_id).where(Tenant.api_key == api_key)
    ).first()
    return row if row else None


def list_plans(session: Session) -> list[Plan]:
    return list(session.scalars(select(Plan).order_by(Plan.price_cents)))


def get_plan_by_name(session: Session, name: str) -> Plan | None:
    return session.scalar(select(Plan).where(Plan.name == name))


def get_usage_rollup(session: Session, tenant_id: int) -> dict:
    start, end = current_period_bounds()

    api_calls = session.scalar(
        select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.event_type == "api_call",
            UsageEvent.created_at >= start,
            UsageEvent.created_at < end,
        )
    )
    tokens = session.scalar(
        select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.event_type == "ai_tokens",
            UsageEvent.created_at >= start,
            UsageEvent.created_at < end,
        )
    )
    token_events = session.scalars(
        select(UsageEvent).where(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.event_type == "ai_tokens",
            UsageEvent.created_at >= start,
            UsageEvent.created_at < end,
        )
    )

    breakdown = {"input": 0, "cached_input": 0, "output": 0, "reasoning": 0}
    by_path = {}
    for event in token_events:
        meta = event.extra or {}
        for key in breakdown:
            breakdown[key] += int(meta.get(key) or 0)
        path = meta.get("path") or "unknown"
        by_path[path] = by_path.get(path, 0) + int(event.quantity)

    return {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "api_calls_used": int(api_calls or 0),
        "ai_tokens_used": int(tokens or 0),
        "token_breakdown": breakdown,
        "tokens_by_path": by_path,
    }


def find_event(session: Session, tenant_id: int, idempotency_key: str) -> UsageEvent | None:
    return session.scalar(
        select(UsageEvent).where(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.idempotency_key == idempotency_key,
        )
    )


def is_webhook_processed(session: Session, event_id: str) -> bool:
    return session.scalar(select(WebhookEvent.id).where(WebhookEvent.event_id == event_id)) is not None


def mark_webhook_processed(session: Session, event_id: str, event_type: str, payload: dict) -> None:
    existing = session.scalar(select(WebhookEvent).where(WebhookEvent.event_id == event_id))
    if existing:
        return
    session.add(WebhookEvent(event_id=event_id, event_type=event_type, payload=payload))


def tenant_by_subscription(session: Session, sub_id: str) -> Tenant | None:
    return session.scalar(select(Tenant).where(Tenant.razorpay_subscription_id == sub_id))


def get_demo_keys(session: Session) -> dict:
    tenants = session.scalars(select(Tenant)).all()
    out = {}
    for t in tenants:
        if t.api_key.startswith("demo_"):
            out["free"] = {"name": t.name, "apiKey": t.api_key}
        elif t.api_key.startswith("pro_"):
            out["pro"] = {"name": t.name, "apiKey": t.api_key}
    return out

