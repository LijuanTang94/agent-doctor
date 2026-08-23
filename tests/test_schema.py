from agentdoctor.trace.schema import SideEffectClass, StepType, Trace


def test_add_step_and_roundtrip(tmp_path):
    trace = Trace(agent_version="v1", environment="test")
    trace.add_step(type=StepType.TOOL_CALL, tool_name="search_orders", latency_ms=120.0)
    trace.add_step(
        type=StepType.TOOL_CALL,
        tool_name="refund_order",
        side_effect_class=SideEffectClass.EXTERNAL_PAYMENT,
    )
    trace.outcome = "failure"

    assert trace.steps[0].index == 0
    assert trace.steps[1].index == 1
    assert trace.steps[1].side_effect_class == SideEffectClass.EXTERNAL_PAYMENT

    path = tmp_path / "trace.json"
    trace.to_jsonl(str(path))
    loaded = Trace.from_jsonl(str(path))

    assert loaded.trace_id == trace.trace_id
    assert loaded.outcome == "failure"
    assert len(loaded.steps) == 2
    assert loaded.steps[1].tool_name == "refund_order"
