# BUILDLOG — AI Usage Log

## Where AI Helped

- **FastAPI & Clean Architecture**: Scaffolded layered architecture separating routing (`app/routers/`), domain logic (`app/services/`), and ORM models (`app/models.py`).
- **Single-File React Dashboard**: Generated an unbundled, modern single-file React component in `public/index.html` (via CDN React 18 and Babel) with live quota progress bars, interactive idempotency testing, token breakdown pills, and Razorpay modal integration.
- **MCP vs Direct LLM Optimizer**: Implemented the simulated optimization layer (`app/services/optimizer.py`) measuring token savings for lean tool fetching vs token overhead for bloated tool schemas without needing paid model API keys.
- **Razorpay Test Mode Integration**: Automated HMAC SHA256 signature verification over raw request bodies and deduplicated webhook processing for subscription and payment lifecycle events.
- **Pytest Suite**: Constructed 28 automated tests covering token price math, quota boundary conditions, idempotent replay guarantees, and webhook flows.

## Where AI Was Wrong / What Changed

- **Python & SQLite Zero-Setup Stack**: The capstone originally mentioned Node/Express and Stripe. In India, Stripe is paid and requires business verification; Razorpay test mode provides a $0 alternative. The backend was fully built in Python with FastAPI, supporting zero-install SQLite by default while remaining PostgreSQL-compatible.
- **SQLAlchemy URL Dialect**: In SQLAlchemy 2.0, `postgres://` URLs fail with `NoSuchModuleError`. Implemented automatic normalization to `postgresql+psycopg2://` in `app/db.py`.
- **SQLite BigInteger Primary Key Autoincrement**: In SQLite, columns declared as `BigInteger` do not trigger 64-bit rowid autoincrement by default, causing `NOT NULL constraint failed: job_runs.id`. Fixed by specifying `.with_variant(Integer, "sqlite")` with `autoincrement=True` across all primary keys.
- **Python 3.12+ `pkg_resources` Deprecation**: In Python 3.12 and 3.13, `setuptools 80+` removed `pkg_resources`, causing imports of `razorpay` to crash. Identified and pinned `setuptools<72` in `requirements.txt`.
- **Concurrency Race Condition on Idempotency**: Simple read-then-write checks allow race conditions if two identical requests arrive simultaneously. Upgraded `app/services/meter.py` with SQLAlchemy nested transaction savepoints (`session.begin_nested()`) catching `IntegrityError` to safely return the existing event without failing with HTTP 500.
- **Raw Body in Webhook Signature**: Webhook HMAC calculation must use the unparsed byte stream (`await request.body()`), not parsed JSON or re-encoded strings, to avoid whitespace and key-ordering discrepancies.
- **MCP Overhead Realism**: Avoided the naive assumption that MCP tools always reduce token costs. Modeled `mcp_noisy` to demonstrate that excessive tool schemas and large payloads actually create overhead exceeding Direct LLM context dumps.

## What I Can Confidently Explain to Evaluators

1. **Guaranteed Exactly-Once Metering**: The composite unique constraint `(tenant_id, idempotency_key)` at the database engine level is the foundational ACID guarantee against double charging. When duplicate keys arrive, the system returns the original event with HTTP 200 and `"duplicate": true` without inserting new usage records.
2. **Quota Boundary Honesty**: At call 1,000 of a 1,000 limit, the call is permitted because projected usage is $\le$ limit. Call 1,001 returns HTTP 402 with an explanatory upgrade message for Free plans, and HTTP 429 with `Retry-After: 3600` for Pro plans.
3. **Integer Money Math**: Money is never calculated or stored as floating point numbers. All tokens are priced in microcents ($10^{-6}$ USD/INR) and converted to integer cents using floor division, preventing IEEE 754 rounding inaccuracies.
4. **Resilient Webhook Synchronization**: Webhooks verify HMAC SHA256 against `RAZORPAY_WEBHOOK_SECRET` before processing. Event IDs are recorded in `webhook_events`, rendering duplicate webhook deliveries idempotent.
5. **Off-Request-Path Background Jobs**: The `usage_rollup` process runs decoupled from incoming requests, aggregating period usage, updating `cost_snapshots`, and recording execution status or errors in `job_runs`.
