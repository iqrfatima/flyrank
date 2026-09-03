import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from app.db import get_session
from app.services.razorpay_service import handle_webhook_event, verify_webhook_signature

router = APIRouter()


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, session: Session = Depends(get_session)):
    raw = await request.body()
    signature = request.headers.get("x-razorpay-signature")
    if not signature:
        return JSONResponse(status_code=400, content={"error": "Missing X-Razorpay-Signature header"})
    if not raw:
        return JSONResponse(status_code=400, content={"error": "Empty webhook body"})
    if not verify_webhook_signature(raw, signature):
        return JSONResponse(status_code=400, content={"error": "Invalid webhook signature"})
    try:
        event = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON payload"})
    try:
        result = handle_webhook_event(session, event)
        return {"received": True, **result}
    except Exception as err:
        print("[webhook]", err)
        return JSONResponse(status_code=500, content={"error": "Webhook processing failed"})
