import os
from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: str) -> int:
    return int(os.getenv(name, default))


PORT = int(os.getenv("PORT", "3000"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./billing.db")

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "local_demo_secret").strip()
RAZORPAY_PRO_PLAN_ID = os.getenv("RAZORPAY_PRO_PLAN_ID", "").strip()

PRICING = {
    "api_call_cents": _int("PRICE_API_CALL_CENTS", "1"),
    "input_token_microcents": _int("PRICE_INPUT_TOKEN_MICROCENTS", "300"),
    "cached_input_token_microcents": _int("PRICE_CACHED_INPUT_TOKEN_MICROCENTS", "150"),
    "output_token_microcents": _int("PRICE_OUTPUT_TOKEN_MICROCENTS", "600"),
    "reasoning_token_microcents": _int("PRICE_REASONING_TOKEN_MICROCENTS", "600"),
}

PLANS = {
    "Free": {"api_calls_limit": 1000, "ai_tokens_limit": 100_000, "price_cents": 0},
    "Pro": {"api_calls_limit": 10_000, "ai_tokens_limit": 1_000_000, "price_cents": 999},
}
