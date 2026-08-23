import random

from agentdoctor import diagnose, verify
from agentdoctor.interventions.base import InterventionSpec

from examples.demo_b.scenario import CronCapabilityConflictScenario, UnrelatedCronScenario


def _find_failing_incident(scenario, seeds=500):
    baseline = scenario.apply_intervention(InterventionSpec())
    for seed in range(seeds):
        trace = scenario.run_episode(baseline, random.Random(seed))
        if trace.outcome == "failure" and trace.grader_results.get("capability_conflict"):
            return trace
    raise AssertionError("expected at least one capability-conflict failure in the first 500 seeds")


def test_cron_capability_conflict_scenario_builds_expected_failing_trace():
    scenario = CronCapabilityConflictScenario()
    incident = _find_failing_incident(scenario)

    cron_step, backend_step = incident.steps
    assert cron_step.tool_name == "cron_dispatch"
    assert cron_step.tool_args["session_target"] == "isolated"
    assert "toolsAllow=['Read', 'Grep', 'Bash']" in cron_step.observation

    assert backend_step.tool_name == "backend_dispatch"
    assert backend_step.error == "CLI backend claude-cli cannot enforce runtime toolsAllow"

    assert incident.outcome == "failure"
    assert incident.grader_results["capability_conflict"] is True


def test_unrelated_cron_scenario_is_a_benign_control():
    scenario = UnrelatedCronScenario(base_failure_rate=0.0)
    trace = scenario.run_episode(scenario.apply_intervention(InterventionSpec()), random.Random(0))

    assert trace.outcome == "success"
    (step,) = trace.steps
    assert step.tool_name == "log_rotate"
    assert step.error is None


def test_config_layer_capability_conflict_is_top_ranked_positive_effect():
    scenario = CronCapabilityConflictScenario()
    incident = _find_failing_incident(scenario)

    report = diagnose(incident, scenario, budget=300, seed=42)
    by_label = {e.label: e for e in report.effects}

    assert "config_layer_capability_conflict" in by_label
    top_effect = report.effects[0]
    assert top_effect.label == "config_layer_capability_conflict"
    assert not top_effect.inconclusive
    assert top_effect.point_estimate > 0

    for other_label, other_effect in by_label.items():
        if other_label == "config_layer_capability_conflict":
            continue
        assert top_effect.point_estimate >= other_effect.point_estimate

    patch = report.best_repair()
    assert patch is not None
    assert patch.hypothesis_name == "config_layer_capability_conflict"


def test_diagnose_to_verify_pipeline_is_safe_to_review():
    scenario = CronCapabilityConflictScenario()
    incident = _find_failing_incident(scenario)

    report = diagnose(incident, scenario, budget=300, seed=42)
    patch = report.best_repair()
    assert patch is not None

    suites = {
        "original": scenario,
        "variants": CronCapabilityConflictScenario(job_name="weekly_backup_job"),
        "unrelated": UnrelatedCronScenario(),
    }
    verification = verify(suites, patch, n=200, seed=7)

    original = verification.suite("original")
    unrelated = verification.suite("unrelated")
    assert original.after_failure_rate < original.before_failure_rate
    assert unrelated.after_failure_rate <= unrelated.before_failure_rate + 0.05
    assert verification.decision == "SAFE_TO_REVIEW"
