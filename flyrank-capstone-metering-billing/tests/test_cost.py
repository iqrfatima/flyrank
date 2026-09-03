from app.services.cost import calculate_token_cost_microcents, calculate_usage_cost, microcents_to_cents
from app.services.optimizer import compare_paths, simulate_provider_usage


def test_categories_priced_separately():
    cost = calculate_token_cost_microcents(input_tokens=1000, cached_input=500, output=800, reasoning=200)
    assert cost == 975_000


def test_cached_input_cheaper_than_input():
    regular = calculate_token_cost_microcents(input_tokens=1000)
    cached = calculate_token_cost_microcents(cached_input=1000)
    assert cached < regular


def test_reasoning_uses_output_rate():
    assert calculate_token_cost_microcents(output=500) == calculate_token_cost_microcents(reasoning=500)


def test_usage_cost_is_integer_cents():
    result = calculate_usage_cost(10, {"input": 100, "cached_input": 50, "output": 200, "reasoning": 100})
    assert result["api_calls_cost_cents"] == 10
    assert isinstance(result["total_cost_cents"], int)


def test_microcents_integer_division():
    assert microcents_to_cents(975_000) == 97


def test_mcp_lean_cheaper_than_direct():
    cmp = compare_paths("What did tenant A use this month?")
    assert cmp["mcp_lean_saves_vs_direct_cents"] > 0


def test_mcp_noisy_can_cost_more_than_direct():
    cmp = compare_paths("What did tenant A use this month?")
    assert cmp["mcp_noisy_overhead_vs_direct_cents"] > 0


def test_provider_usage_is_source_of_truth_shape():
    usage = simulate_provider_usage("hello world", "mcp_lean")
    assert usage.cached_input > 0
    assert usage.total == usage.input + usage.cached_input + usage.output + usage.reasoning
