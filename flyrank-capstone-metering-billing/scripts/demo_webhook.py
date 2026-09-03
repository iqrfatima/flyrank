"""Local webhook demo — no Razorpay account needed. Start the server first."""

import hashlib
import hmac
import json
import os
import sys
import time
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "local_demo_secret")
tenant_id = sys.argv[1] if len(sys.argv) > 1 else "1"
port = os.getenv("PORT", "3000")

payload = json.dumps(
    {
        "id": f"evt_demo_{int(time.time() * 1000)}",
        "event": "subscription.activated",
        "created_at": int(time.time()),
        "payload": {
            "subscription": {
                "entity": {
                    "id": f"sub_demo_{int(time.time() * 1000)}",
                    "notes": {"tenant_id": tenant_id},
                }
            }
        },
    }
).encode("utf-8")

signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
req = Request(
    f"http://localhost:{port}/webhooks/razorpay",
    data=payload,
    headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature},
    method="POST",
)
print(f"Sending subscription.activated for tenant_id={tenant_id}...")
with urlopen(req) as resp:
    print("Status:", resp.status)
    print(resp.read().decode())
