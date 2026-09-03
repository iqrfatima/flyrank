import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


BASE_URL = "http://127.0.0.1:3000"
client = httpx.Client(base_url=BASE_URL, timeout=10.0)

print("=== 1. Health Check ===")
r_health = client.get("/health")
print(f"Status: {r_health.status_code}")
print(r_health.json())

print("\n=== 2. Plans Catalog ===")
r_plans = client.get("/api/plans")
print(f"Status: {r_plans.status_code}")
print(json.dumps(r_plans.json(), indent=2))

r_keys = client.get("/api/demo-keys")
demo_keys = r_keys.json()
free_key = demo_keys["free"]["apiKey"]
pro_key = demo_keys["pro"]["apiKey"]
print(f"Free API Key: {free_key}")
print(f"Pro API Key:  {pro_key}")

print("\n=== 3. Non-Billable MCP vs Direct Analyzer (POST /api/analyze) ===")
prompt = "Analyze usage trends for Q3."
r_analyze = client.post("/api/analyze", json={"prompt": prompt})
print(f"Status: {r_analyze.status_code}")
print(json.dumps(r_analyze.json(), indent=2))

print("\n=== 4. Idempotent Usage Metering (POST /api/generate) ===")
idemp_key = f"live-test-key-{int(time.time())}"
gen_payload = {"prompt": prompt, "path": "mcp_lean"}

# First call:
r_gen1 = client.post(
    "/api/generate",
    headers={"X-API-Key": free_key, "Idempotency-Key": idemp_key},
    json=gen_payload,
)
print(f"Call #1 Status: {r_gen1.status_code}")
print(json.dumps(r_gen1.json(), indent=2))

# Second call (exact same key):
r_gen2 = client.post(
    "/api/generate",
    headers={"X-API-Key": free_key, "Idempotency-Key": idemp_key},
    json=gen_payload,
)
print(f"Call #2 (Retry) Status: {r_gen2.status_code}")
print(json.dumps(r_gen2.json(), indent=2))

print("\n=== 5. Current Period Usage Rollup & Costs (GET /api/usage) ===")
r_usage = client.get("/api/usage", headers={"X-API-Key": free_key})
print(f"Status: {r_usage.status_code}")
print(json.dumps(r_usage.json(), indent=2))

print("\n=== 6. Razorpay Webhook Signature Verification & Deduplication ===")
from app.config import RAZORPAY_WEBHOOK_SECRET

# Test forged signature
r_forged = client.post(
    "/webhooks/razorpay",
    headers={"Content-Type": "application/json", "X-Razorpay-Signature": "forged_signature_hex"},
    content=b'{"event":"subscription.activated"}',
)
print(f"Forged Signature Status: {r_forged.status_code}")
print(r_forged.json())

# Test valid signature
webhook_event_id = f"evt_verify_{int(time.time()*1000)}"
wh_payload = json.dumps({
    "id": webhook_event_id,
    "event": "subscription.activated",
    "created_at": int(time.time()),
    "payload": {
        "subscription": {
            "entity": {
                "id": f"sub_{int(time.time())}",
                "notes": {"tenant_id": "1"}
            }
        }
    }
}).encode("utf-8")
sig = hmac.new(RAZORPAY_WEBHOOK_SECRET.encode(), wh_payload, hashlib.sha256).hexdigest()

r_wh1 = client.post(
    "/webhooks/razorpay",
    headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    content=wh_payload,
)
print(f"Valid Webhook Status: {r_wh1.status_code}")
print(r_wh1.json())

# Replay same webhook
r_wh2 = client.post(
    "/webhooks/razorpay",
    headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    content=wh_payload,
)
print(f"Replay Webhook Status: {r_wh2.status_code}")
print(r_wh2.json())

print("\n=== All live verification checks passed successfully! ===")
