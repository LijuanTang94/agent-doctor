from agentdoctor.planner.rule_planner import plan_experiments
from agentdoctor.trace.schema import StepType, Trace


def test_planner_flags_retry_and_latency_signals():
    trace = Trace()
    trace.add_step(type=StepType.TOOL_CALL, tool_name="search_orders", latency_ms=3000, error="timeout")
    trace.add_step(type=StepType.TOOL_CALL, tool_name="search_orders", latency_ms=120, retry_count=1)
    trace.add_step(type=StepType.TOOL_CALL, tool_name="refund_order")

    hypotheses = plan_experiments(trace)
    names = [h.name for h in hypotheses]

    assert any(n.startswith("normalize_latency:search_orders") for n in names)
    assert "clear_stale_retry_state" in names
    assert "model_swap" in names  # always present as a competing baseline


def test_planner_flags_repeated_tool_calls():
    trace = Trace()
    trace.add_step(type=StepType.TOOL_CALL, tool_name="refund_order")
    trace.add_step(type=StepType.TOOL_CALL, tool_name="refund_order")

    hypotheses = plan_experiments(trace)
    names = [h.name for h in hypotheses]
    assert "tool_schema_ablation" in names


def test_planner_ranks_by_prior_descending():
    trace = Trace()
    trace.add_step(type=StepType.TOOL_CALL, tool_name="search_orders", error="timeout")
    hypotheses = plan_experiments(trace)
    priors = [h.prior for h in hypotheses]
    assert priors == sorted(priors, reverse=True)
