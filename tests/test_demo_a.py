import random

from agentdoctor import diagnose, verify

from examples.demo_a.scenario import RefundAgentScenario, UnrelatedTaskScenario


def _find_failing_incident(scenario, seeds=200):
    from agentdoctor.interventions.base import InterventionSpec

    baseline = scenario.apply_intervention(InterventionSpec())
    for seed in range(seeds):
        trace = scenario.run_episode(baseline, random.Random(seed))
        if trace.outcome == "failure" and trace.grader_results.get("duplicate_seen"):
            return trace
    raise AssertionError("expected at least one failing incident in the first 200 seeds")


def test_model_swap_barely_helps_but_retry_fix_does():
    scenario = RefundAgentScenario()
    incident = _find_failing_incident(scenario)

    report = diagnose(incident, scenario, budget=90, seed=1)
    by_label = {e.label: e for e in report.effects}

    assert "clear_stale_retry_state" in by_label
    assert "model_swap" in by_label
    assert any(l.startswith("normalize_latency") for l in by_label)

    retry_effect = by_label["clear_stale_retry_state"]
    model_effect = by_label["model_swap"]

    # the retry/state fix should dominate a pure model swap
    assert retry_effect.point_estimate > model_effect.point_estimate


def test_diagnose_to_verify_pipeline_is_safe_to_review():
    scenario = RefundAgentScenario()
    incident = _find_failing_incident(scenario)

    report = diagnose(incident, scenario, budget=90, seed=1)
    patch = report.best_repair()
    assert patch is not None

    suites = {
        "original": scenario,
        "variants": RefundAgentScenario(order_id="B-2091", spike_probability=0.38),
        "unrelated": UnrelatedTaskScenario(),
    }
    verification = verify(suites, patch, n=200, seed=2)

    original = verification.suite("original")
    unrelated = verification.suite("unrelated")
    assert original.after_failure_rate < original.before_failure_rate
    assert unrelated.after_failure_rate <= unrelated.before_failure_rate + 0.05
    assert verification.decision == "SAFE_TO_REVIEW"
