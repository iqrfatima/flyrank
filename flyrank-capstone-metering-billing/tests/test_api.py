from app.models import UsageEvent


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_plans_endpoint(client):
    res = client.get("/api/plans")
    assert res.status_code == 200
    data = res.json()
    assert "plans" in data
    assert len(data["plans"]) >= 2
    names = [p["name"] for p in data["plans"]]
    assert "Free" in names
    assert "Pro" in names


def test_analyze_mcp_optimization_comparison_does_not_bill(client, db_session):
    # Verify DB has 0 usage events before analyze
    count_before = db_session.query(UsageEvent).count()

    prompt = "Summarize the quarterly analytics report for tenant 42."
    res = client.post("/api/analyze", json={"prompt": prompt})
    assert res.status_code == 200
    data = res.json()

    assert "paths" in data
    assert "direct" in data["paths"]
    assert "mcp_lean" in data["paths"]
    assert "mcp_noisy" in data["paths"]

    # Lean MCP saves money vs Direct
    assert data["mcp_lean_saves_vs_direct_cents"] > 0
    # Noisy MCP introduces overhead vs Direct
    assert data["mcp_noisy_overhead_vs_direct_cents"] > 0

    # Ensure this analyze request is non-billable: 0 usage events created!
    count_after = db_session.query(UsageEvent).count()
    assert count_after == count_before


def test_usage_endpoint(client, seeded_tenants):
    tenant = seeded_tenants["free"]
    res = client.get("/api/usage", headers={"X-API-Key": tenant.api_key})
    assert res.status_code == 200
    data = res.json()

    assert data["tenant"]["name"] == tenant.name
    assert data["tenant"]["plan"] == "Free"
    assert "period" in data
    assert "usage" in data
    assert "cost" in data
    assert data["cost"]["currency"] == "INR"
    assert isinstance(data["cost"]["totalCents"], int)


def test_unauthorized_api_access(client):
    res = client.get("/api/usage")
    assert res.status_code == 401
    assert "Unauthorized" in res.json().get("error", "")

    res_invalid = client.get("/api/usage", headers={"X-API-Key": "invalid_random_key_999"})
    assert res_invalid.status_code == 401
    assert "Unauthorized" in res_invalid.json().get("error", "")



def test_frontend_renders(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "Usage Metering &amp; Billing" in res.text or "Usage Metering" in res.text
