from agentdoctor.attribution.contrastive import Effect
from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.planner.rule_planner import Hypothesis
from agentdoctor.repair.engine import best_repair


def make_effect(label, point, ci_low, ci_high):
    return Effect(
        label=label,
        baseline_failure_rate=0.4,
        intervention_failure_rate=0.4 - point,
        point_estimate=point,
        ci_low=ci_low,
        ci_high=ci_high,
    )


def test_best_repair_prefers_safer_rung_over_bigger_effect():
    hypotheses = [
        Hypothesis("clear_stale_retry_state", InterventionSpec(), 0.4, "r1"),
        Hypothesis("tool_schema_ablation", InterventionSpec(), 0.2, "r2"),
    ]
    effects = [
        make_effect("clear_stale_retry_state", 0.35, 0.2, 0.5),  # bigger effect, riskier rung
        make_effect("tool_schema_ablation", 0.10, 0.02, 0.2),  # smaller effect, safer rung
    ]

    patch = best_repair(effects, hypotheses)
    assert patch is not None
    assert patch.hypothesis_name == "tool_schema_ablation"


def test_best_repair_excludes_inconclusive_effects():
    hypotheses = [Hypothesis("model_swap", InterventionSpec(), 0.1, "r")]
    effects = [make_effect("model_swap", 0.05, -0.1, 0.15)]  # CI straddles zero

    assert best_repair(effects, hypotheses) is None


def test_best_repair_returns_none_when_no_candidates():
    assert best_repair([], []) is None
