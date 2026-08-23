from agentdoctor.replay.cassette import Cassette, compute_fidelity
from agentdoctor.trace.schema import Trace


def test_cassette_lookup_by_tool_and_args():
    trace = Trace()
    trace.add_step(
        type="tool_call", tool_name="search_orders", tool_args={"order_id": "A-1"}, observation="ok"
    )
    cassette = Cassette.from_trace(trace)

    hit = cassette.lookup("search_orders", {"order_id": "A-1"})
    assert hit is not None
    assert hit.observation == "ok"

    miss = cassette.lookup("search_orders", {"order_id": "B-2"})
    assert miss is None


def test_compute_fidelity_perfect_match():
    original = Trace()
    original.add_step(type="tool_call", tool_name="search_orders", state_hash="h1")
    original.add_step(type="tool_call", tool_name="refund_order", state_hash="h2")

    replayed = Trace()
    replayed.add_step(type="tool_call", tool_name="search_orders", state_hash="h1")
    replayed.add_step(type="tool_call", tool_name="refund_order", state_hash="h2")

    report = compute_fidelity(original, replayed)
    assert report.action_match_rate == 1.0
    assert report.state_match_rate == 1.0
    assert report.n_steps_compared == 2


def test_compute_fidelity_partial_mismatch():
    original = Trace()
    original.add_step(type="tool_call", tool_name="search_orders", state_hash="h1")
    original.add_step(type="tool_call", tool_name="refund_order", state_hash="h2")

    replayed = Trace()
    replayed.add_step(type="tool_call", tool_name="search_orders", state_hash="h1")
    replayed.add_step(type="tool_call", tool_name="get_order", state_hash="different")

    report = compute_fidelity(original, replayed)
    assert report.action_match_rate == 0.5
    assert report.state_match_rate == 0.5


def test_compute_fidelity_empty_traces():
    report = compute_fidelity(Trace(), Trace())
    assert report.n_steps_compared == 0
    assert report.action_match_rate == 0.0
