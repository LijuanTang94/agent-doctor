from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.replay.runtime import run
from tests.scenarios import CoinFlipScenario


def test_baseline_vs_intervention_failure_rate():
    scenario = CoinFlipScenario()
    baseline = run(scenario, n=300, interventions=InterventionSpec(), seed=1)
    fixed = run(scenario, n=300, interventions=InterventionSpec(model_override="fixed"), seed=1)

    assert 0.35 < baseline.failure_rate < 0.65
    assert fixed.failure_rate < 0.2
    assert fixed.success_rate == 1 - fixed.failure_rate


def test_run_is_deterministic_given_seed():
    scenario = CoinFlipScenario()
    a = run(scenario, n=50, interventions=InterventionSpec(), seed=5)
    b = run(scenario, n=50, interventions=InterventionSpec(), seed=5)
    assert [t.outcome for t in a.traces] == [t.outcome for t in b.traces]
