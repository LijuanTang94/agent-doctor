import random

from agentdoctor import diagnose, verify
from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.mitigation import MITIGATION_ONLY, classify
from agentdoctor.trace.schema import StepType

from examples.demo_h.scenario import PoolExhaustionRaceScenario, UnrelatedMetricsScrapeScenario

_POOL_EXHAUSTED_ERROR = (
    "PoolExhaustedError: no connections available after 200ms "
    "(suspected leaked connection under concurrent initialization; "
    "root cause not confirmed)"
)


def _find_failing_incident(scenario, seeds=500):
    baseline = scenario.apply_intervention(InterventionSpec())
    for seed in range(seeds):
        trace = scenario.run_episode(baseline, random.Random(seed))
        if trace.outcome == "failure" and trace.grader_results.get("pool_race"):
            return trace
    raise AssertionError("expected at least one pool-exhaustion failure in the first 500 seeds")


def test_pool_exhaustion_race_scenario_builds_expected_failing_trace():
    scenario = PoolExhaustionRaceScenario()
    incident = _find_failing_incident(scenario)

    (step,) = incident.steps
    assert step.type == StepType.TOOL_CALL
    assert step.tool_name == "run_health_check"
    assert step.error == _POOL_EXHAUSTED_ERROR
    assert "PoolExhaustedError" in step.error
    assert step.provenance["pool_race"] is True
    assert step.provenance["masks_root_cause"] is True

    assert incident.outcome == "failure"
    assert incident.grader_results["pool_race"] is True
    assert incident.final_output == "Health check failed: pool exhausted"


def test_unrelated_metrics_scrape_scenario_is_a_benign_control():
    scenario = UnrelatedMetricsScrapeScenario(base_failure_rate=0.0)
    trace = scenario.run_episode(scenario.apply_intervention(InterventionSpec()), random.Random(0))

    assert trace.outcome == "success"
    (step,) = trace.steps
    assert step.tool_name == "scrape_metrics"
    assert step.error is None


def test_clear_stale_retry_state_is_top_ranked_positive_effect():
    scenario = PoolExhaustionRaceScenario()
    incident = _find_failing_incident(scenario)

    report = diagnose(incident, scenario, budget=300, seed=42)
    by_label = {e.label: e for e in report.effects}

    assert "clear_stale_retry_state" in by_label
    top_effect = report.effects[0]
    assert top_effect.label == "clear_stale_retry_state"
    assert not top_effect.inconclusive
    assert top_effect.point_estimate > 0
    assert top_effect.ci_low > 0

    for other_label, other_effect in by_label.items():
        if other_label == "clear_stale_retry_state":
            continue
        assert top_effect.point_estimate >= other_effect.point_estimate

    patch = report.best_repair()
    assert patch is not None
    assert patch.hypothesis_name == "clear_stale_retry_state"


def test_diagnose_to_verify_pipeline_is_safe_to_review_but_mitigation_only():
    scenario = PoolExhaustionRaceScenario()
    incident = _find_failing_incident(scenario)

    report = diagnose(incident, scenario, budget=300, seed=42)
    patch = report.best_repair()
    assert patch is not None
    assert patch.hypothesis_name == "clear_stale_retry_state"

    suites = {
        "original": scenario,
        "variants": PoolExhaustionRaceScenario(
            worker_id="healthcheck-worker-2", pool_race_probability=0.30
        ),
        "unrelated": UnrelatedMetricsScrapeScenario(),
    }
    verification = verify(suites, patch, n=200, seed=7)

    original = verification.suite("original")
    unrelated = verification.suite("unrelated")
    assert original.after_failure_rate < original.before_failure_rate
    assert abs(unrelated.after_failure_rate - unrelated.before_failure_rate) <= 0.05
    assert verification.decision == "SAFE_TO_REVIEW"

    assert classify(incident, patch, verification) == MITIGATION_ONLY
