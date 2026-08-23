from agentdoctor.trace.recorder import record
from agentdoctor.trace.schema import StepType


def test_record_context_manager():
    with record(name="unit-test", agent_version="v1") as run:
        run.set_input("hello")
        run.step(type=StepType.TOOL_CALL, tool_name="search_orders", observation="ok")
        run.finish(final_output="done", outcome="success")

    trace = run.trace
    assert trace.initial_input == "hello"
    assert trace.final_output == "done"
    assert trace.outcome == "success"
    assert len(trace.steps) == 1
    assert trace.steps[0].tool_name == "search_orders"
