# flyrank-capstone-metering-billing

> **Production-grade Usage Metering & Billing Engine with MCP Optimization and Razorpay Test Mode**  
> Built with Python 3.13, FastAPI, SQLAlchemy 2.0, SQLite / PostgreSQL, and a Single-File React 18 SPA.

---

## Table of Contents

1. [Overview & Core Value](#overview--core-value)
2. [Key Capabilities](#key-capabilities)
3. [Architecture & Request Pipelines](#architecture--request-pipelines)
4. [LLM & MCP Optimization Methodology](#llm--mcp-optimization-methodology)
5. [Plans & Quotas](#plans--quotas)
6. [Pricing Model (Zero Float Math)](#pricing-model-zero-float-math)
7. [Comprehensive File-by-File Guide](#comprehensive-file-by-file-guide)
8. [Quick Start Guide ($0 Stack)](#quick-start-guide-0-stack)
9. [API Specification](#api-specification)
10. [Testing & Verification](#testing--verification)
11. [Honest Limitations](#honest-limitations)

---

## Overview & Core Value

Every modern SaaS company must reliably answer three fundamental questions:
1. **How much has this customer used?**
2. **How much should they pay?**
3. **Have they hit their subscription limits?**

When real money and usage limits are involved, minor bugs lead to double-charging customers on retries, giving away unbilled resources, or failing audit trails. This repository implements a safe, deterministic, zero-double-count metering and billing engine that handles network retries, quota boundaries, real-world AI token pricing rules, and test-mode payment synchronization via Razorpay.

---

## Key Capabilities

- **Exactly-Once Metering**: Guaranteed via unique database constraints `(tenant_id, idempotency_key)` and transactional savepoints. Retrying any billable request returns the original result with HTTP 200 (`duplicate: true`) without creating new usage events.
- **Boundary-Honest Quota Enforcement**:
  - `402 Payment Required` for Free tier tenants exceeding quotas or tenants with lapsed payments.
  - `429 Too Many Requests` with a compliant `Retry-After: 3600` header for Pro tier tenants hitting plan ceilings.
  - Exact boundary checks: call 1,000 of 1,000 is allowed; call 1,001 is immediately blocked.
- **Accurate Token Pricing (Zero Float Math)**:
  - Cached input tokens are priced with a 50% discount.
  - Reasoning tokens are priced at the output rate.
  - Categories are priced individually before summation.
  - Money is tracked strictly in integer microcents ($10^{-6}$ INR/cents), converted to cents via floor division.
- **MCP Optimization Analysis**:
  - Measures whether Model Context Protocol (MCP) tool execution saves money or adds overhead.
  - Non-billable dry-run endpoint (`POST /api/analyze`) compares Direct prompt dumps vs. Lean MCP vs. Noisy MCP.
- **Razorpay Test Mode Webhook Sync**:
  - Verifies HMAC SHA-256 signatures on raw request bodies.
  - Deduplicates incoming webhooks to safely handle gateway retries.
  - Synchronizes tenant plans and statuses upon subscription events.
- **Single-File React Dashboard**:
  - An interactive UI (`public/index.html`) running React 18 & Babel via CDN with zero build steps or npm compilation needed.

---

## Architecture & Request Pipelines

```
                                  ┌─────────────────────────────────┐
                                  │      Client / React Frontend    │
                                  └──────────────┬──────────────────┘
                                                 │
                   POST /api/generate            │             GET /api/usage
       (Headers: X-API-Key, Idempotency-Key)     │        (Headers: X-API-Key)
                         │                       │                     │
                         ▼                       │                     ▼
        ┌──────────────────────────────────┐     │    ┌──────────────────────────────────┐
        │       Authentication Guard       │     │    │       Authentication Guard       │
        │   (Validates X-API-Key Tenant)   │     │    │   (Validates X-API-Key Tenant)   │
        └────────────────┬─────────────────┘     │    └────────────────┬─────────────────┘
                         │                       │                     │
                         ▼                       │                     ▼
        ┌──────────────────────────────────┐     │    ┌──────────────────────────────────┐
        │   Optimization / Provider Sim    │     │    │        tenant_service            │
        │  (Direct vs MCP Lean vs Noisy)   │     │    │  (Rollup current billing period) │
        └────────────────┬─────────────────┘     │    └────────────────┬─────────────────┘
                         │                       │                     │
                         ▼                       │                     ▼
        ┌──────────────────────────────────┐     │    ┌──────────────────────────────────┐
        │         MeterService             │     │    │       calculate_usage_cost       │
        │ 1. Check existing idempotency_key│     │    │ (Integer microcents -> cents)    │
        │    -> return original if found   │     │    └────────────────┬─────────────────┘
        │ 2. Pre-execution quota check     │     │                     │
        │    -> 402 or 429 if exceeded     │     │                     ▼
        │ 3. Atomic DB insert savepoint    │     │      Returns { usage, limit, cost }
        └────────────────┬─────────────────┘     │
                         │                       │
                         ▼                       │
             HTTP 201 (or 200 on replay)         │
```

---

## LLM & MCP Optimization Methodology

In production AI backends, provider-reported token usage is the authoritative source of truth:

```
Application  ───►  Optimization Layer  ───►  LLM Execution  ───►  Provider Usage Report  ───►  Metering & Billing
```

This service tests and measures the real economic impact of MCP (Model Context Protocol):
1. **Direct LLM Request (`direct`)**: Dumps a large static context block (4,200 tokens) into the system prompt. High input token consumption, 0 cached tokens.
2. **MCP Lean (`mcp_lean`)**: Uses 2 targeted tool definitions with concise tool outputs. Schema tokens are cached (180 tokens), and targeted data is small (320 tokens). **Demonstrates real cost savings.**
3. **MCP Noisy (`mcp_noisy`)**: Exposes excessive tool schemas (2,400 cached tokens) and returns huge raw tool dumps (5,100 input tokens) with increased reasoning overhead. **Demonstrates that unoptimized MCP tools can cost MORE than direct prompts.**

Use `POST /api/analyze` to compare all three paths on any prompt without incurring billing charges.

---

## Plans & Quotas

| Plan | API Calls / Month | AI Tokens / Month | Monthly Cost | Over-Quota Response |
| :--- | :--- | :--- | :--- | :--- |
| **Free** | 1,000 calls | 100,000 tokens | ₹0.00 | **HTTP 402 Payment Required** |
| **Pro** | 10,000 calls | 1,000,000 tokens | ₹9.99 | **HTTP 429 Too Many Requests** (`Retry-After: 3600`) |

---

## Pricing Model (Zero Float Math)

All token calculations use integer microcents ($10^{-6}$ currency units) to avoid floating-point rounding errors:

| Usage Category | Price in Microcents | Effective Rate |
| :--- | :--- | :--- |
| **API Call** | 10,000 microcents | 1 cent / ₹0.01 per call |
| **Input Tokens** | 300 microcents / token | ₹0.003 per 1,000 tokens |
| **Cached Input Tokens** | 150 microcents / token | ₹0.0015 per 1,000 tokens (50% discount) |
| **Output Tokens** | 600 microcents / token | ₹0.006 per 1,000 tokens |
| **Reasoning Tokens** | 600 microcents / token | Billed at the output token rate |

$$\text{Tokens Cost (Microcents)} = (\text{input} \times 300) + (\text{cached} \times 150) + (\text{output} \times 600) + (\text{reasoning} \times 600)$$
$$\text{Tokens Cost (Cents)} = \lfloor \text{Tokens Cost (Microcents)} / 10,000 \rfloor$$
$$\text{Total Cost (Cents)} = \text{API Calls Cost} + \text{Tokens Cost (Cents)}$$

---

## Comprehensive File-by-File Guide

Here is the exact responsibility and internal logic of every file in the codebase:

### Root Configuration & Manifests
- **[`capstone.yaml`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/capstone.yaml)**: Evaluator manifest declaring the single run command, seed command, test command, base URL, and probed endpoints.
- **[`.env.example`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/.env.example)**: Reference environment file with documented placeholder values for ports, database URLs, Razorpay keys, and token prices.
- **[`.env`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/.env)**: Local environment variables containing SQLite URL, test Razorpay keys, and pinned price constants.
- **[`requirements.txt`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/requirements.txt)**: Python dependencies (`fastapi`, `uvicorn`, `sqlalchemy`, `razorpay`, `httpx`, `pytest`, `psycopg2-binary`, `setuptools<72`).
- **[`BUILDLOG.md`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/BUILDLOG.md)**: AI usage transparency document detailing where AI was applied, design corrections made, and key concepts.
- **[`EVIDENCE.md`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/EVIDENCE.md)**: Verification document containing live test outputs, curl transcripts, idempotency proofs, and webhook logs.
- **[`DESIGN.md`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/DESIGN.md)**: Original architecture and data modeling specification.
- **[`docker-compose.yml`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/docker-compose.yml)**: Optional container configuration for running PostgreSQL.

### Core Application (`app/`)
- **[`app/config.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/app/config.py)**: Loads environment variables via `python-dotenv`. Exports `PORT`, `DATABASE_URL`, Razorpay test credentials, `PRICING` dictionary, and `PLANS` dictionary.
- **[`app/db.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/app/db.py)**: Initializes SQLAlchemy engine and session factory. Automatically normalizes `postgres://` to `postgresql+psycopg2://` and configures connection pooling for SQLite and PostgreSQL. Provides the `get_session()` dependency with automatic transaction commit/rollback.
- **[`app/models.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/app/models.py)**: Declarative database models:
  - `Plan`: Subscription limits and pricing.
  - `Tenant`: Multi-tenant customer accounts isolated by API keys.
  - `UsageEvent`: Billable records protected by `UniqueConstraint("tenant_id", "idempotency_key")`.
  - `WebhookEvent`: Record of processed payment gateway event IDs preventing duplicate webhook handling.
  - `CostSnapshot`: Aggregated monthly usage and cost snapshots created by background jobs.
  - `JobRun`: Operational audit log for background jobs recording execution timestamps, tenant counts, and error messages.
- **[`app/exceptions.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/app/exceptions.py)**: Defines `QuotaExceededError` carrying human-readable messages and specific status codes (`402` or `429`).
- **[`app/main.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/app/main.py)**: FastAPI application entrypoint. Configures lifespan context manager, background rollup daemon thread, custom exception handlers (Pydantic 400s, Quota 402/429s, HTTP 401s), static asset routing for `/public`, and route inclusion.

### Routers (`app/routers/`)
- **[`app/routers/api.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/app/routers/api.py)**: Primary API router:
  - `GET /api/plans`: Returns available plans and Razorpay configuration status.
  - `GET /api/demo-keys`: Returns seeded demo API keys for single-click UI testing.
  - `POST /api/analyze`: Non-billable dry-run comparison between Direct LLM and MCP tool paths.
  - `GET /api/usage`: Returns current billing period usage, token breakdown, and calculated cost.
  - `POST /api/generate`: Billable dummy LLM endpoint with header-based tenant authentication and idempotency key enforcement.
  - `POST /api/checkout`: Creates Razorpay subscription orders in test mode.
- **[`app/routers/webhooks.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/app/routers/webhooks.py)**: Webhook ingress for Razorpay. Reads the raw byte stream to verify HMAC SHA-256 signatures, rejects forged requests with HTTP 400, and delegates event handling to the service layer.

### Services (`app/services/`)
- **[`app/services/cost.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/app/services/cost.py)**: Pure mathematical functions for token costing. Implements category-specific pricing, cached token discounts, and calendar month billing period boundaries.
- **[`app/services/meter.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/app/services/meter.py)**: Core metering and quota engine. Implements `check_quota()` boundary checks and `record_usage()` with concurrency-safe nested transaction savepoints.
- **[`app/services/optimizer.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/app/services/optimizer.py)**: Models simulated LLM token usage for Direct, MCP Lean, and MCP Noisy paths, returning structured token counts.
- **[`app/services/razorpay_service.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/app/services/razorpay_service.py)**: Integrates Razorpay test mode. Creates checkout subscriptions, computes raw-body HMAC SHA-256 signatures with constant-time comparison, and handles subscription activations, cancellations, and payment failures with event deduplication.
- **[`app/services/rollup.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/app/services/rollup.py)**: Background worker logic. Queries all active tenants, aggregates their billing-period usage, writes records to `cost_snapshots`, and logs execution outcomes in `job_runs`.
- **[`app/services/tenant.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/app/services/tenant.py)**: Database query abstraction for tenant retrieval, plan queries, usage event aggregation, and webhook replay status checks.

### Frontend (`public/`)
- **[`public/index.html`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/public/index.html)**: Single-file React application loaded via CDN with Babel. Features quick-fill demo keys, real-time quota progress gauges, token category breakdown badges, interactive prompt execution with "Retry Same Key" idempotency validation, MCP comparison views, and Razorpay checkout integration.

### Scripts (`scripts/`)
- **[`scripts/migrate.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/scripts/migrate.py)**: Creates database tables and composite indexes.
- **[`scripts/seed.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/scripts/seed.py)**: Inserts Free and Pro plans and creates demo tenant accounts with API keys.
- **[`scripts/rollup.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/scripts/rollup.py)**: Manual CLI trigger for the off-request-path usage rollup job.
- **[`scripts/demo_webhook.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/scripts/demo_webhook.py)**: Generates signed Razorpay test webhooks locally without needing external webhook forwarders.
- **[`scripts/verify_live.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/scripts/verify_live.py)**: Comprehensive end-to-end integration script verifying all endpoints against a live server.

### Tests (`tests/`)
- **[`tests/conftest.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/tests/conftest.py)**: Pytest setup with an isolated in-memory SQLite database (`StaticPool`) and dependency override fixtures.
- **[`tests/test_cost.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/tests/test_cost.py)**: Tests category-specific pricing, cached input discounts, reasoning output parity, and integer microcent division.
- **[`tests/test_metering.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/tests/test_metering.py)**: Tests exactly-once idempotency, header validation, Free quota boundary conditions (1,000 allowed vs 1,001 rejected with 402), token quota limits, and Pro 429 rate limiting with `Retry-After`.
- **[`tests/test_webhooks.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/tests/test_webhooks.py)**: Tests signature verification, forged signature rejection, subscription plan upgrades, and webhook deduplication.
- **[`tests/test_api.py`](file:///c:/Users/iqra%20fatima/Desktop/Capstone/tests/test_api.py)**: Tests health, plan catalogs, non-billable MCP analyze endpoints, and authentication guards.

---

## Quick Start Guide ($0 Stack)

No Docker or external cloud accounts are required. Follow these steps:

### 1. Environment Setup
```bash
cd Capstone
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Database Migration & Seeding
```bash
python scripts/migrate.py
python scripts/seed.py
```
*The seed script outputs two ready-to-use API keys (Free and Pro).*

### 3. Run the Application
```bash
python -m app.main
```
Open **`http://localhost:3000`** in your browser to access the single-file React dashboard. Click "Use Seeded Free Key" or "Use Seeded Pro Key" to immediately explore the system.

### 4. Run Automated Tests
```bash
python -m pytest -v
```

### 5. Test Webhooks Locally (No Tunnel Needed)
In a separate terminal while the server is running:
```bash
python scripts/demo_webhook.py 1
```

---

## API Specification

| Method | Endpoint | Headers | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | None | Service liveness probe |
| `GET` | `/api/plans` | None | Returns Free & Pro quotas and pricing |
| `GET` | `/api/demo-keys` | None | Returns seeded demo API keys |
| `POST` | `/api/analyze` | None | Non-billable Direct vs MCP cost comparison |
| `GET` | `/api/usage` | `X-API-Key` | Current period usage, quotas, and cost |
| `POST` | `/api/generate` | `X-API-Key`, `Idempotency-Key` | Billable LLM request recording usage |
| `POST` | `/api/checkout` | `X-API-Key` | Initiates Razorpay test mode checkout |
| `POST` | `/webhooks/razorpay` | `X-Razorpay-Signature` | Verified webhook handler |
| `GET` | `/` | None | Renders single-file React frontend |

---

## Testing & Verification

Run the full end-to-end verification script against a running server:
```bash
python scripts/verify_live.py
```

Expected output:
- Health check returns `200 OK`.
- Analyze compares Direct vs MCP Lean vs MCP Noisy without billing.
- First generate call returns `201 Created` with `duplicate: false`.
- Replay of the exact same key returns `200 OK` with `duplicate: true` and identical usage counters.
- Forged webhook returns `400 Bad Request`.
- Valid webhook returns `200 OK` and upgrades tenant to Pro.
- Webhook replay returns `200 OK` with `reason: duplicate`.

---

## Honest Limitations

- **Simulated LLM Tokens**: Token consumption is accurately modeled based on realistic LLM context sizes and tool schemas without making live external API calls to OpenAI or Anthropic.
- **Razorpay Test Mode**: Uses test mode keys with simulated cards (`4111 1111 1111 1111`). No real financial transactions take place.
- **Invoicing & Proration**: Mid-cycle upgrade proration and formal PDF invoice generation are omitted to keep the focus squarely on reliable usage metering and quota enforcement.
