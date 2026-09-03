# Design Document — Usage Metering & Billing Engine (Python)

## Problem

SaaS products must answer: how much has this customer used, what does it cost, and have they hit plan limits? This service meters usage, enforces quotas, calculates AI-token costs, and optionally syncs plans via Razorpay test-mode webhooks.

## Data model

- **plans** — Free / Pro quotas and optional Razorpay plan id
- **tenants** — isolated customers, API key, plan, Razorpay ids, status
- **usage_events** — billable events, unique `(tenant_id, idempotency_key)`
- **webhook_events** — Razorpay event id uniqueness (replay → ignore)
- **cost_snapshots** — monthly rollups from the background job
- **job_runs** — rollup success / failure log

## API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/generate` | Billable dummy LLM request |
| POST | `/api/analyze` | Compare Direct vs MCP costs (not billed) |
| GET | `/api/usage` | Used / limit / cost |
| POST | `/api/checkout` | Razorpay subscription (optional) |
| POST | `/webhooks/razorpay` | Signed, idempotent webhooks |
| GET | `/api/plans` | Plan catalog |
| GET | `/health` | Health |

Headers: `X-API-Key`, `Idempotency-Key` (required on `/generate`).

## LLM methodology (simulated — no model key)

```
Application
     ↓
Token/Cost Analyzer   POST /api/analyze (dry run)
     ↓
Optimization Layer    path = direct | mcp_lean | mcp_noisy
     ↓
Simulated LLM         returns provider-reported usage
     ↓
Usage Meter           idempotent record
     ↓
Billing + Limits      402 / 429 + integer money math
```

Provider-reported token counts are the source of truth. MCP is an optional optimization path whose savings *or overhead* the meter measures.

## Idempotency

Unique `(tenant_id, idempotency_key)`. Duplicate request returns the original event (no second charge).

## Quota semantics

- **429** — Pro plan hit the limit (`Retry-After` set)
- **402** — Free plan at limit (upgrade) or subscription inactive

## Non-goals

- Real LLM provider calls
- Live Razorpay / real money
- Invoicing, proration, overage (stretch)
