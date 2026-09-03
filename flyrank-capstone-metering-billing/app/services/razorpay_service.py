import hmac
from hashlib import sha256

import razorpay
from sqlalchemy.orm import Session

from app.config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_PRO_PLAN_ID, RAZORPAY_WEBHOOK_SECRET
from app.models import Tenant
from app.services import tenant as tenant_service


def is_configured() -> bool:
    return bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)


def _client():
    if not is_configured():
        raise RuntimeError("Razorpay credentials not configured")
    return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


def create_subscription_checkout(session: Session, tenant: Tenant) -> dict:
    pro = tenant_service.get_plan_by_name(session, "Pro")
    plan_id = (pro.razorpay_plan_id if pro else None) or RAZORPAY_PRO_PLAN_ID
    if not plan_id:
        err = RuntimeError("Set RAZORPAY_PRO_PLAN_ID to use checkout, or use the seeded Pro API key.")
        err.status_code = 503
        raise err

    subscription = _client().subscription.create(
        {
            "plan_id": plan_id,
            "total_count": 12,
            "customer_notify": 1,
            "notes": {"tenant_id": str(tenant.id), "tenant_name": tenant.name},
        }
    )
    tenant.razorpay_subscription_id = subscription["id"]
    return {
        "subscriptionId": subscription["id"],
        "keyId": RAZORPAY_KEY_ID,
        "planName": "Pro",
        "amount": pro.price_cents if pro else 999,
        "currency": "INR",
        "shortUrl": subscription.get("short_url"),
    }


def verify_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    if not RAZORPAY_WEBHOOK_SECRET or not signature:
        return False
    expected = hmac.new(RAZORPAY_WEBHOOK_SECRET.encode(), raw_body, sha256).hexdigest()
    if len(expected) != len(signature):
        return False
    return hmac.compare_digest(expected, signature)


def handle_webhook_event(session: Session, event: dict) -> dict:
    event_id = event.get("id") or f"{event.get('event')}_{event.get('created_at')}"
    event_type = event.get("event") or ""

    if tenant_service.is_webhook_processed(session, event_id):
        return {"processed": False, "reason": "duplicate"}

    payload = event.get("payload") or {}
    sub = (payload.get("subscription") or {}).get("entity") or {}
    payment = (payload.get("payment") or {}).get("entity") or {}
    notes = sub.get("notes") or payment.get("notes") or {}
    tenant_id_raw = notes.get("tenant_id")
    sub_id = sub.get("id") or payment.get("subscription_id")

    tenant = None
    if tenant_id_raw:
        try:
            tenant = session.get(Tenant, int(tenant_id_raw))
        except (ValueError, TypeError):
            tenant = None
    if not tenant and sub_id:
        tenant = tenant_service.tenant_by_subscription(session, sub_id)

    if event_type in ("subscription.activated", "subscription.charged", "subscription.resumed"):
        if tenant:
            pro = tenant_service.get_plan_by_name(session, "Pro")
            if pro:
                tenant.plan_id = pro.id
                tenant.status = "active"
                if sub_id:
                    tenant.razorpay_subscription_id = sub_id

    elif event_type in ("subscription.cancelled", "subscription.halted"):
        if tenant:
            free = tenant_service.get_plan_by_name(session, "Free")
            if free:
                tenant.plan_id = free.id
                tenant.status = "payment_failed" if event_type == "subscription.halted" else "cancelled"

    elif event_type in ("payment.failed",):
        if tenant:
            tenant.status = "payment_failed"

    tenant_service.mark_webhook_processed(session, event_id, event_type, event)
    return {
        "processed": True,
        "eventType": event_type,
        "tenantId": tenant.id if tenant else None,
        "newPlan": tenant.plan_id if tenant else None,
        "status": tenant.status if tenant else None,
    }

