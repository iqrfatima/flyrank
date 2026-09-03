import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import PLANS, RAZORPAY_PRO_PLAN_ID
from app.db import SessionLocal, engine
from app.models import Base, Plan, Tenant

Base.metadata.create_all(bind=engine)
session = SessionLocal()

try:
    for name, spec in PLANS.items():
        plan = session.query(Plan).filter_by(name=name).one_or_none()
        if plan is None:
            plan = Plan(name=name)
            session.add(plan)
        plan.api_calls_limit = spec["api_calls_limit"]
        plan.ai_tokens_limit = spec["ai_tokens_limit"]
        plan.price_cents = spec["price_cents"]
        if name == "Pro":
            plan.razorpay_plan_id = RAZORPAY_PRO_PLAN_ID or plan.razorpay_plan_id
    session.flush()

    free = session.query(Plan).filter_by(name="Free").one()
    pro = session.query(Plan).filter_by(name="Pro").one()
    demo_key = "demo_" + secrets.token_hex(16)
    pro_key = "pro_" + secrets.token_hex(16)
    session.add(Tenant(name="Demo Tenant (Free)", api_key=demo_key, plan_id=free.id, status="active"))
    session.add(Tenant(name="Demo Tenant (Pro)", api_key=pro_key, plan_id=pro.id, status="active"))
    session.commit()

    print("\n=== Seed complete ===")
    print("Free tenant API key:", demo_key)
    print("Pro tenant API key: ", pro_key)
    print("\nNo Razorpay needed — use the Pro key to test Pro quotas.")
    print("Open http://localhost:3000 and paste an API key.\n")
finally:
    session.close()
