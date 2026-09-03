# EVIDENCE — Requirement Proofs

This document provides concrete, verifiable evidence for each requirement specified in the Capstone Brief.

---

## 1. Automated Test Suite (28 Passed)

All unit, boundary, integration, idempotency, webhook, and cost calculation tests pass deterministically in one command:

```bash
python -m pytest -v
```

```
============================= test session starts =============================
platform win32 -- Python 3.13.1, pytest-8.3.3, pluggy-1.6.0
rootdir: C:\Users\iqra fatima\Desktop\Capstone
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.0
collected 28 items

tests/test_api.py::test_health_endpoint PASSED                           [  3%]
tests/test_api.py::test_plans_endpoint PASSED                            [  7%]
tests/test_api.py::test_analyze_mcp_optimization_comparison_does_not_bill PASSED [ 10%]
tests/test_api.py::test_usage_endpoint PASSED                            [ 14%]
tests/test_api.py::test_unauthorized_api_access PASSED                   [ 17%]
tests/test_api.py::test_frontend_renders PASSED                          [ 21%]
tests/test_cost.py::test_categories_priced_separately PASSED             [ 25%]
tests/test_cost.py::test_cached_input_cheaper_than_input PASSED          [ 28%]
tests/test_cost.py::test_reasoning_uses_output_rate PASSED               [ 32%]
tests/test_cost.py::test_usage_cost_is_integer_cents PASSED              [ 35%]
tests/test_cost.py::test_microcents_integer_division PASSED              [ 39%]
tests/test_cost.py::test_mcp_lean_cheaper_than_direct PASSED             [ 42%]
tests/test_cost.py::test_mcp_noisy_can_cost_more_than_direct PASSED      [ 46%]
tests/test_cost.py::test_provider_usage_is_source_of_truth_shape PASSED  [ 50%]
tests/test_metering.py::test_exact_once_metering PASSED                  [ 53%]
tests/test_metering.py::test_distinct_keys_record_separate_events PASSED [ 57%]
tests/test_metering.py::test_validation_at_boundary_missing_idempotency_key PASSED [ 60%]
tests/test_metering.py::test_validation_at_boundary_short_idempotency_key PASSED [ 64%]
tests/test_metering.py::test_validation_at_boundary_missing_api_key PASSED [ 67%]
tests/test_metering.py::test_free_quota_exact_boundary_enforcement PASSED [ 71%]
tests/test_metering.py::test_token_quota_enforcement PASSED              [ 75%]
tests/test_metering.py::test_pro_quota_429_with_retry_after PASSED       [ 78%]
tests/test_metering.py::test_inactive_tenant_rejected_with_402 PASSED    [ 82%]
tests/test_webhooks.py::test_webhook_missing_signature PASSED            [ 85%]
tests/test_webhooks.py::test_webhook_invalid_signature PASSED            [ 89%]
tests/test_webhooks.py::test_webhook_subscription_activated_upgrades_tenant PASSED [ 92%]
tests/test_webhooks.py::test_webhook_subscription_cancelled PASSED       [ 96%]
tests/test_webhooks.py::test_webhook_payment_failed PASSED               [100%]

======================= 28 passed, 2 warnings in 0.33s ========================
```

---

## 2. Metering — Idempotent Usage (No Double-Counting)

A billable request with the same `Idempotency-Key` records **exactly one** usage event. The retried request returns the original result with `"duplicate": true` and HTTP 200, without incrementing tenant usage counters.

### Request #1 (New Key)
```bash
curl -i -X POST http://localhost:3000/api/generate \
  -H "X-API-Key: demo_f9cb36e4e182a555a28adf9119c2146d" \
  -H "Idempotency-Key: live-test-key-100" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Analyze usage trends for Q3.","path":"mcp_lean"}'
```

**Response (HTTP 201 Created):**
```json
{
  "message": "Usage recorded",
  "duplicate": false,
  "eventId": 7,
  "providerUsage": {
    "input": 329,
    "cached_input": 180,
    "output": 80,
    "reasoning": 40,
    "path": "mcp_lean",
    "total": 629,
    "notes": "MCP lean: 2 tools, small targeted fetch. Tool schemas billed as cached input."
  },
  "simulatedResponse": {
    "text": "Simulated LLM answer. Tokens come from the provider-usage report, not a real model.",
    "path": "mcp_lean"
  },
  "usage": {
    "apiCallsUsed": 4,
    "aiTokensUsed": 2033
  }
}
```

### Request #2 (Idempotent Replay with Same Key)
```bash
curl -i -X POST http://localhost:3000/api/generate \
  -H "X-API-Key: demo_f9cb36e4e182a555a28adf9119c2146d" \
  -H "Idempotency-Key: live-test-key-100" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Analyze usage trends for Q3.","path":"mcp_lean"}'
```

**Response (HTTP 200 OK — No New Usage Event Created):**
```json
{
  "message": "Idempotent replay — no duplicate charge",
  "duplicate": true,
  "eventId": 7,
  "providerUsage": {
    "input": 329,
    "cached_input": 180,
    "output": 80,
    "reasoning": 40,
    "path": "mcp_lean",
    "total": 629,
    "notes": "MCP lean: 2 tools, small targeted fetch. Tool schemas billed as cached input."
  },
  "simulatedResponse": {
    "text": "Simulated LLM answer. Tokens come from the provider-usage report, not a real model.",
    "path": "mcp_lean"
  },
  "usage": {
    "apiCallsUsed": 4,
    "aiTokensUsed": 2033
  }
}
```
*Proof:* `apiCallsUsed` remained at 4, `aiTokensUsed` remained at 2033, `eventId` was identical (`7`), and `duplicate` is `true`.

---

## 3. Quota Enforcement & Boundary Honesty (402 vs 429)

### Free Plan Boundary:
- Limit: 1,000 calls / month.
- Call #1,000: **Allowed** (HTTP 201).
- Call #1,001: **Rejected with HTTP 402 Payment Required**:
```json
{
  "error": "Payment Required",
  "message": "API call quota exceeded. Used 1000/1000. Upgrade your plan or wait until next billing period.",
  "retryAfter": null
}
```

### Token Quota Boundary:
- Limit: 100,000 tokens / month.
- Request exceeding 100,000 tokens -> **Rejected with HTTP 402 Payment Required**:
```json
{
  "error": "Payment Required",
  "message": "AI token quota exceeded. Used 0/100000. Upgrade your plan or wait until next billing period.",
  "retryAfter": null
}
```

### Pro Plan Boundary (Rate/Quota Limit):
- Limit: 10,000 calls / 1,000,000 tokens.
- Exceeding limit on Pro plan -> **Rejected with HTTP 429 Too Many Requests** with `Retry-After: 3600` header:
```
HTTP/1.1 429 Too Many Requests
Retry-After: 3600
Content-Type: application/json

{
  "error": "Too Many Requests",
  "message": "API call quota exceeded. Used 10000/10000. Upgrade your plan or wait until next billing period."
}
```

---

## 4. Cost Calculation & Integer Money Math

- Stored strictly as **integer microcents and cents** — zero floating-point math.
- Pinned configuration:
  - API call: `1 cent`
  - Input token: `300 microcents`
  - Cached input token: `150 microcents` (50% discount)
  - Output token: `600 microcents`
  - Reasoning token: `600 microcents` (billed at output rate)

### Pinned Formula Verification:
1,000 input + 500 cached input + 800 output + 200 reasoning:
$$\text{Cost} = (1000 \times 300) + (500 \times 150) + (800 \times 600) + (200 \times 600) = 300,000 + 75,000 + 480,000 + 120,000 = 975,000\,\mu\text{cents}$$
$$\text{Total in Cents} = \lfloor 975,000 / 10,000 \rfloor = 97\text{ cents}$$

Verified by unit test: `tests/test_cost.py::test_categories_priced_separately` (PASSED).

---

## 5. Razorpay Webhooks (Test Mode) — Signature Verification & Replay Protection

### A. Forged / Invalid Signature (HTTP 400 Bad Request):
```bash
curl -i -X POST http://localhost:3000/webhooks/razorpay \
  -H "Content-Type: application/json" \
  -H "X-Razorpay-Signature: forged_signature_hex" \
  -d '{"event":"subscription.activated"}'
```
**Response:**
```json
HTTP/1.1 400 Bad Request

{
  "error": "Invalid webhook signature"
}
```

### B. Valid Signature (`subscription.activated` -> Free to Pro Upgrade):
```bash
python scripts/demo_webhook.py 1
```
**Response:**
```json
HTTP/1.1 200 OK

{
  "received": true,
  "processed": true,
  "eventType": "subscription.activated",
  "tenantId": 1,
  "newPlan": 2,
  "status": "active"
}
```

### C. Webhook Deduplication / Replay:
Replaying the same event ID:
**Response:**
```json
HTTP/1.1 200 OK

{
  "received": true,
  "processed": false,
  "reason": "duplicate"
}
```
*Proof:* Second delivery acknowledged with HTTP 200 to satisfy payment gateway retry policies, but marked `processed: false` and safely ignored.

---

## 6. Token/Cost Analyzer & MCP Optimization Layer

Endpoint: `POST /api/analyze` compares Direct LLM prompt dumps vs. MCP Tool execution paths **without recording billable events**.

```bash
curl -s -X POST http://localhost:3000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Generate quarterly cost breakdown"}'
```

```json
{
  "source_of_truth": "provider_reported_tokens (simulated)",
  "paths": {
    "direct": {
      "usage": {
        "input": 4209,
        "cached_input": 0,
        "output": 80,
        "reasoning": 40,
        "path": "direct",
        "total": 4329,
        "notes": "Direct path dumped a large context window. No tool-schema cache."
      },
      "cost": {
        "api_calls_cost_cents": 1,
        "tokens_cost_microcents": 1334700,
        "tokens_cost_cents": 133,
        "total_cost_cents": 134
      }
    },
    "mcp_lean": {
      "usage": {
        "input": 329,
        "cached_input": 180,
        "output": 80,
        "reasoning": 40,
        "path": "mcp_lean",
        "total": 629,
        "notes": "MCP lean: 2 tools, small targeted fetch. Tool schemas billed as cached input."
      },
      "cost": {
        "api_calls_cost_cents": 1,
        "tokens_cost_microcents": 197700,
        "tokens_cost_cents": 19,
        "total_cost_cents": 20
      }
    },
    "mcp_noisy": {
      "usage": {
        "input": 5109,
        "cached_input": 2400,
        "output": 140,
        "reasoning": 120,
        "path": "mcp_noisy",
        "total": 7769,
        "notes": "MCP noisy: many tools + oversized tool payloads. Overhead can beat any savings."
      },
      "cost": {
        "api_calls_cost_cents": 1,
        "tokens_cost_microcents": 2048700,
        "tokens_cost_cents": 204,
        "total_cost_cents": 205
      }
    }
  },
  "mcp_lean_saves_vs_direct_cents": 114,
  "mcp_noisy_overhead_vs_direct_cents": 71
}
```
*Key Takeaway:*
- `mcp_lean` saves **114 cents (₹1.14)** vs Direct by fetching targeted context and utilizing cached tool schema tokens.
- `mcp_noisy` introduces **71 cents (₹0.71)** in overhead due to oversized schema definitions and bloated tool payloads.
- Demonstrates measuring real MCP overhead vs savings.

---

## 7. Shared Requirements Verification

| # | Capstone Requirement | Implementation Details | Evidence |
|---|----------------------|------------------------|----------|
| 1 | **Layered Architecture** | `app/routers/` (HTTP/validation) $\rightarrow$ `app/services/` (business logic) $\rightarrow$ `app/models.py` (persistence) | Clean separation across all modules |
| 2 | **Boundary Validation** | Pydantic v2 validation + custom HTTP & validation handlers. Missing/short keys return clean 400s; never unhandled 500s. | `tests/test_metering.py` lines 70–95 |
| 3 | **Background Job** | `app/services/rollup.py`: Periodic usage aggregation off the request path with execution logs in `job_runs` and snapshots in `cost_snapshots`. | `[job:usage_rollup] Completed — 2 tenants` logged to `job_runs` |
| 4 | **Real Persistence & Tenant Isolation** | Relational schema with composite indexes and isolation by `tenant_id`. Compatible with SQLite ($0 local) and PostgreSQL (Docker). | `app/models.py`, `migrations/001_schema.sql` |
| 5 | **Idempotency** | Database constraint `uq_tenant_idempotency` + nested transaction with savepoints. Concurrency safe. | `tests/test_metering.py::test_exact_once_metering` |
| 6 | **Clean Secrets** | Zero secrets in repository. `.env` in `.gitignore`. Safe placeholder defaults in `.env.example`. | Repo hygiene verified |
| 7 | **Cost Tracked & Budget Guard** | Integer microcent tracking. Pre-execution quota checks reject calls before writing billable events. | `app/services/meter.py::check_quota` |
