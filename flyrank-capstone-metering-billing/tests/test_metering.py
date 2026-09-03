from app.models import UsageEvent


def test_exact_once_metering(client, seeded_tenants, db_session):
    tenant = seeded_tenants["free"]
    headers = {
        "X-API-Key": tenant.api_key,
        "Idempotency-Key": "req-idemp-key-001",
        "Content-Type": "application/json",
    }
    body = {"prompt": "Summarize billing statement.", "path": "direct"}

    # First call - should record usage
    res1 = client.post("/api/generate", headers=headers, json=body)
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["duplicate"] is False
    assert "eventId" in data1
    assert data1["usage"]["apiCallsUsed"] == 1
    event_id = data1["eventId"]

    # Replay exact same request with same Idempotency-Key
    res2 = client.post("/api/generate", headers=headers, json=body)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["duplicate"] is True
    assert data2["eventId"] == event_id
    assert data2["message"] == "Idempotent replay — no duplicate charge"
    assert data2["usage"]["apiCallsUsed"] == 1

    # Verify in DB: exactly 1 api_call event exists for this tenant
    events = (
        db_session.query(UsageEvent)
        .filter_by(tenant_id=tenant.id, event_type="api_call")
        .all()
    )
    assert len(events) == 1
    assert events[0].idempotency_key == "req-idemp-key-001"


def test_distinct_keys_record_separate_events(client, seeded_tenants, db_session):
    tenant = seeded_tenants["free"]
    body = {"prompt": "Calculate taxes.", "path": "mcp_lean"}

    res1 = client.post(
        "/api/generate",
        headers={"X-API-Key": tenant.api_key, "Idempotency-Key": "req-unique-key-AAA"},
        json=body,
    )
    assert res1.status_code == 201
    assert res1.json()["duplicate"] is False

    res2 = client.post(
        "/api/generate",
        headers={"X-API-Key": tenant.api_key, "Idempotency-Key": "req-unique-key-BBB"},
        json=body,
    )
    assert res2.status_code == 201
    assert res2.json()["duplicate"] is False

    events = (
        db_session.query(UsageEvent)
        .filter_by(tenant_id=tenant.id, event_type="api_call")
        .all()
    )
    assert len(events) >= 2


def test_validation_at_boundary_missing_idempotency_key(client, seeded_tenants):
    tenant = seeded_tenants["free"]
    # Missing Idempotency-Key header
    res = client.post(
        "/api/generate",
        headers={"X-API-Key": tenant.api_key},
        json={"prompt": "test"},
    )
    assert res.status_code == 400
    assert "Idempotency-Key" in res.json().get("message", "")


def test_validation_at_boundary_short_idempotency_key(client, seeded_tenants):
    tenant = seeded_tenants["free"]
    # Idempotency-Key less than 8 chars
    res = client.post(
        "/api/generate",
        headers={"X-API-Key": tenant.api_key, "Idempotency-Key": "short"},
        json={"prompt": "test"},
    )
    assert res.status_code == 400
    assert "8–128 characters" in res.json().get("message", "")


def test_validation_at_boundary_missing_api_key(client):
    res = client.post(
        "/api/generate",
        headers={"Idempotency-Key": "test-key-12345678"},
        json={"prompt": "test"},
    )
    assert res.status_code == 401


def test_free_quota_exact_boundary_enforcement(client, seeded_tenants, db_session):
    tenant = seeded_tenants["free"]
    plan = seeded_tenants["free_plan"]
    assert plan.api_calls_limit == 1000

    # Seed 999 existing api_call events
    db_session.add(
        UsageEvent(
            tenant_id=tenant.id,
            event_type="api_call",
            quantity=999,
            idempotency_key="bulk-seed-prior-calls",
            extra={"source": "seed"},
        )
    )
    db_session.commit()

    # Call #1000 of 1000: Allowed!
    res_1000 = client.post(
        "/api/generate",
        headers={"X-API-Key": tenant.api_key, "Idempotency-Key": "req-boundary-call-1000"},
        json={"prompt": "Boundary check call 1000", "path": "mcp_lean"},
    )
    assert res_1000.status_code == 201

    # Call #1001 of 1000: Rejected with 402 (Payment Required)
    res_1001 = client.post(
        "/api/generate",
        headers={"X-API-Key": tenant.api_key, "Idempotency-Key": "req-boundary-call-1001"},
        json={"prompt": "Boundary check call 1001", "path": "mcp_lean"},
    )
    assert res_1001.status_code == 402
    assert "quota exceeded" in res_1001.json().get("message", "").lower()
    assert "402" in str(res_1001.status_code)


def test_token_quota_enforcement(client, seeded_tenants):
    tenant = seeded_tenants["free"]
    # Request with explicit token usage exceeding 100,000 limit
    res = client.post(
        "/api/generate",
        headers={"X-API-Key": tenant.api_key, "Idempotency-Key": "req-token-overflow-01"},
        json={
            "prompt": "Large doc processing",
            "input_tokens": 120_000,
            "output_tokens": 500,
        },
    )
    assert res.status_code == 402
    assert "AI token quota exceeded" in res.json().get("message", "")


def test_pro_quota_429_with_retry_after(client, seeded_tenants, db_session):
    tenant = seeded_tenants["pro"]
    plan = seeded_tenants["pro_plan"]
    assert plan.api_calls_limit == 10_000

    # Seed 10,000 existing calls
    db_session.add(
        UsageEvent(
            tenant_id=tenant.id,
            event_type="api_call",
            quantity=10_000,
            idempotency_key="bulk-seed-pro-calls",
            extra={"source": "seed"},
        )
    )
    db_session.commit()

    # Call exceeding 10,000 on Pro -> 429 Too Many Requests
    res = client.post(
        "/api/generate",
        headers={"X-API-Key": tenant.api_key, "Idempotency-Key": "req-pro-over-limit"},
        json={"prompt": "Pro call"},
    )
    assert res.status_code == 429
    assert res.headers.get("Retry-After") == "3600"
    assert "Too Many Requests" in res.json().get("error", "")


def test_inactive_tenant_rejected_with_402(client, seeded_tenants):
    tenant = seeded_tenants["inactive"]
    res = client.post(
        "/api/generate",
        headers={"X-API-Key": tenant.api_key, "Idempotency-Key": "req-inactive-tenant"},
        json={"prompt": "Call from cancelled tenant"},
    )
    assert res.status_code == 402
    assert "Subscription inactive" in res.json().get("message", "")
