from agentdoctor.interventions.base import InterventionSpec, active_builder, intervene
from agentdoctor.replay.runtime import run
from tests.scenarios import CoinFlipScenario


def test_builder_fluent_api():
    with intervene() as x:
        x.tool("search_orders").latency(ms=100)
        x.retry_policy(clear_stale_observation=True)
        x.prompt.replace(rule_id="refund_policy", text="new rule")
        x.model(override="model_b")
        spec = x.build()

    assert spec.tool_latency_ms == {"search_orders": 100}
    assert spec.retry_clear_stale_observation is True
    assert spec.prompt_overrides == {"refund_policy": "new rule"}
    assert spec.model_override == "model_b"


def test_active_builder_is_scoped_to_with_block():
    assert active_builder() is None
    with intervene() as x:
        assert active_builder() is x
    assert active_builder() is None


def test_replay_run_picks_up_active_builder_when_no_explicit_spec():
    scenario = CoinFlipScenario()
    with intervene() as x:
        x.model(override="fixed")
        result = run(scenario, n=200, seed=0)

    # fixed bias (0.05) should give a much lower failure rate than baseline (0.5)
    assert result.failure_rate < 0.2


def test_explicit_interventions_override_active_builder():
    scenario = CoinFlipScenario()
    explicit = InterventionSpec()  # baseline, no override
    with intervene() as x:
        x.model(override="fixed")
        result = run(scenario, n=200, interventions=explicit, seed=0)

    assert result.failure_rate > 0.3
