"""
Simulated LLM path. No model API key.

Provider-reported token counts are the source of truth for metering.
The optimization layer chooses Direct vs MCP before the (simulated) LLM call.

Direct: dump a large knowledge blob into the prompt (expensive input).
MCP lean: few tools + small targeted result (usually cheaper).
MCP noisy: many tools + huge tool output (can cost MORE than direct).
"""

from dataclasses import dataclass

VALID_PATHS = ("direct", "mcp_lean", "mcp_noisy")


@dataclass(frozen=True)
class ProviderUsage:
    input: int
    cached_input: int
    output: int
    reasoning: int
    path: str
    notes: str

    @property
    def total(self) -> int:
        return self.input + self.cached_input + self.output + self.reasoning

    def as_dict(self) -> dict:
        return {
            "input": self.input,
            "cached_input": self.cached_input,
            "output": self.output,
            "reasoning": self.reasoning,
            "path": self.path,
            "total": self.total,
            "notes": self.notes,
        }


def _approx_tokens(text: str) -> int:
    words = len(text.split()) if text else 0
    return max(1, int(words * 1.3) + len(text) // 8)


def simulate_provider_usage(prompt: str, path: str) -> ProviderUsage:
    path = (path or "direct").lower()
    if path not in VALID_PATHS:
        path = "direct"

    question_tokens = _approx_tokens(prompt or "Summarize monthly usage for this tenant.")
    output = max(80, question_tokens // 4)
    reasoning = 40

    if path == "direct":
        knowledge_dump = 4200
        return ProviderUsage(
            input=knowledge_dump + question_tokens,
            cached_input=0,
            output=output,
            reasoning=reasoning,
            path=path,
            notes="Direct path dumped a large context window. No tool-schema cache.",
        )

    if path == "mcp_lean":
        tool_schema = 180
        targeted_result = 320
        return ProviderUsage(
            input=question_tokens + targeted_result,
            cached_input=tool_schema,
            output=output,
            reasoning=reasoning,
            path=path,
            notes="MCP lean: 2 tools, small targeted fetch. Tool schemas billed as cached input.",
        )

    tool_schema = 2400
    huge_tool_output = 5100
    return ProviderUsage(
        input=question_tokens + huge_tool_output,
        cached_input=tool_schema,
        output=output + 60,
        reasoning=reasoning + 80,
        path=path,
        notes="MCP noisy: many tools + oversized tool payloads. Overhead can beat any savings.",
    )


def compare_paths(prompt: str) -> dict:
    rows = {p: simulate_provider_usage(prompt, p) for p in VALID_PATHS}
    from app.services.cost import calculate_usage_cost

    costs = {}
    for name, usage in rows.items():
        costs[name] = {
            "usage": usage.as_dict(),
            "cost": calculate_usage_cost(
                api_calls=1,
                tokens={
                    "input": usage.input,
                    "cached_input": usage.cached_input,
                    "output": usage.output,
                    "reasoning": usage.reasoning,
                },
            ),
        }

    lean_total = costs["mcp_lean"]["cost"]["total_cost_cents"]
    direct_total = costs["direct"]["cost"]["total_cost_cents"]
    noisy_total = costs["mcp_noisy"]["cost"]["total_cost_cents"]
    return {
        "source_of_truth": "provider_reported_tokens (simulated)",
        "paths": costs,
        "mcp_lean_saves_vs_direct_cents": direct_total - lean_total,
        "mcp_noisy_overhead_vs_direct_cents": noisy_total - direct_total,
    }
