from __future__ import annotations

from datetime import datetime, timezone

from app.config import PRICING


def calculate_token_cost_microcents(
    input_tokens: int = 0,
    cached_input: int = 0,
    output: int = 0,
    reasoning: int = 0,
) -> int:
    """Price each category separately. Reasoning uses the output rate. Cached input is cheaper."""
    return (
        int(input_tokens) * PRICING["input_token_microcents"]
        + int(cached_input) * PRICING["cached_input_token_microcents"]
        + int(output) * PRICING["output_token_microcents"]
        + int(reasoning) * PRICING["reasoning_token_microcents"]
    )


def microcents_to_cents(microcents: int) -> int:
    return int(microcents) // 10_000


def calculate_usage_cost(api_calls: int = 0, tokens: dict | None = None) -> dict:
    tokens = tokens or {}
    api_cents = int(api_calls) * PRICING["api_call_cents"]
    token_micro = calculate_token_cost_microcents(
        input_tokens=int(tokens.get("input") or 0),
        cached_input=int(tokens.get("cached_input") or 0),
        output=int(tokens.get("output") or 0),
        reasoning=int(tokens.get("reasoning") or 0),
    )
    token_cents = microcents_to_cents(token_micro)
    return {
        "api_calls_cost_cents": api_cents,
        "tokens_cost_microcents": token_micro,
        "tokens_cost_cents": token_cents,
        "total_cost_cents": api_cents + token_cents,
    }


def current_period_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(timezone.utc)
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return start, end
