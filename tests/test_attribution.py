from agentdoctor.attribution.contrastive import estimate_effect, rank_hypotheses
from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.replay.runtime import run
from tests.scenarios import CoinFlipScenario


def test_estimate_effect_detects_real_improvement():
    scenario = CoinFlipScenario()
    baseline = run(scenario, n=400, interventions=InterventionSpec(), seed=2)
    fixed = run(scenario, n=400, interventions=InterventionSpec(model_override="fixed"), seed=2)

    effect = estimate_effect(baseline, fixed, label="fix", seed=2)

    assert effect.point_estimate > 0.2
    assert not effect.inconclusive
    assert effect.ci_low > 0


def test_estimate_effect_flags_noop_as_inconclusive():
    scenario = CoinFlipScenario()
    baseline = run(scenario, n=60, interventions=InterventionSpec(), seed=3)
    noop = run(scenario, n=60, interventions=InterventionSpec(), seed=9)

    effect = estimate_effect(baseline, noop, label="noop", seed=3)
    assert effect.inconclusive


def test_rank_hypotheses_orders_by_point_estimate():
    scenario = CoinFlipScenario()
    baseline = run(scenario, n=200, interventions=InterventionSpec(), seed=4)
    weak = run(scenario, n=200, interventions=InterventionSpec(model_override="weak"), seed=4)
    strong = run(scenario, n=200, interventions=InterventionSpec(model_override="fixed"), seed=4)

    effects = [
        estimate_effect(baseline, weak, label="weak", seed=4),
        estimate_effect(baseline, strong, label="strong", seed=4),
    ]
    ranked = rank_hypotheses(effects)
    assert ranked[0].label == "strong"
