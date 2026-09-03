import hashlib
import hmac
import json
import time

from app.config import RAZORPAY_WEBHOOK_SECRET
from app.models import Tenant


def _sign(body: bytes, secret: str = RAZORPAY_WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_missing_signature(client):
    res = client.post(
        "/webhooks/razorpay",
        content=b'{"event":"test"}',
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 400
    assert "Missing X-Razorpay-Signature" in res.json().get("error", "")


def test_webhook_invalid_signature(client):
    res = client.post(
        "/webhooks/razorpay",
        content=b'{"event":"test"}',
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "invalid_forged_signature_12345",
        },
    )
    assert res.status_code == 400
    assert "Invalid webhook signature" in res.json().get("error", "")


def test_webhook_subscription_activated_upgrades_tenant(client, seeded_tenants, db_session):
    tenant = seeded_tenants["free"]
    free_plan_id = tenant.plan_id
    pro_plan = seeded_tenants["pro_plan"]

    event_id = f"evt_test_act_{int(time.time() * 1000)}"
    sub_id = f"sub_test_{int(time.time() * 1000)}"

    payload_data = {
        "id": event_id,
        "event": "subscription.activated",
        "created_at": int(time.time()),
        "payload": {
            "subscription": {
                "entity": {
                    "id": sub_id,
                    "notes": {"tenant_id": str(tenant.id)},
                }
            }
        },
    }
    raw = json.dumps(payload_data).encode("utf-8")
    sig = _sign(raw)

    # First send: should activate and upgrade tenant
    res = client.post(
        "/webhooks/razorpay",
        content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["received"] is True
    assert data["processed"] is True
    assert data["eventType"] == "subscription.activated"

    db_session.refresh(tenant)
    assert tenant.plan_id == pro_plan.id
    assert tenant.plan_id != free_plan_id
    assert tenant.status == "active"
    assert tenant.razorpay_subscription_id == sub_id

    # Replay exact same webhook event: Deduplication test!
    res_dup = client.post(
        "/webhooks/razorpay",
        content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res_dup.status_code == 200
    data_dup = res_dup.json()
    assert data_dup["received"] is True
    assert data_dup["processed"] is False
    assert data_dup["reason"] == "duplicate"


def test_webhook_subscription_cancelled(client, seeded_tenants, db_session):
    tenant = seeded_tenants["pro"]
    free_plan = seeded_tenants["free_plan"]

    event_id = f"evt_test_cancel_{int(time.time() * 1000)}"
    payload_data = {
        "id": event_id,
        "event": "subscription.cancelled",
        "created_at": int(time.time()),
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_test_cancelling",
                    "notes": {"tenant_id": str(tenant.id)},
                }
            }
        },
    }
    raw = json.dumps(payload_data).encode("utf-8")
    sig = _sign(raw)

    res = client.post(
        "/webhooks/razorpay",
        content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res.status_code == 200
    assert res.json()["processed"] is True

    db_session.refresh(tenant)
    assert tenant.plan_id == free_plan.id
    assert tenant.status == "cancelled"


def test_webhook_payment_failed(client, seeded_tenants, db_session):
    tenant = seeded_tenants["pro"]
    tenant.razorpay_subscription_id = "sub_fail_123"
    db_session.commit()

    event_id = f"evt_test_payfail_{int(time.time() * 1000)}"
    payload_data = {
        "id": event_id,
        "event": "payment.failed",
        "created_at": int(time.time()),
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_fail_123",
                    "subscription_id": "sub_fail_123",
                }
            }
        },
    }
    raw = json.dumps(payload_data).encode("utf-8")
    sig = _sign(raw)

    res = client.post(
        "/webhooks/razorpay",
        content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res.status_code == 200
    assert res.json()["processed"] is True

    db_session.refresh(tenant)
    assert tenant.status == "payment_failed"
