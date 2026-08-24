import random

from agentdoctor import diagnose, verify
from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.trace.schema import StepType

from examples.demo_e.scenario import StaleBaseRebaseScenario, UnrelatedDeployScenario

_STALE_REF_ERROR = (
    "ModuleNotFoundError: No module named 'agentdoctor.repair.ladder_v2' "
    "(symbol merged to origin/main after this worker branch's fork point; "
    "the worker's local base is stale)"
)


def _find_failing_incident(scenario, seeds=500):
    baseline = scenario.apply_intervention(InterventionSpec())
    for seed in range(seeds):
        trace = scenario.run_episode(baseline, random.Random(seed))
        if trace.outcome == "failure" and trace.grader_results.get("stale_base"):
            return trace
    raise AssertionError("expected at least one stale-base failure in the first 500 seeds")


def test_stale_base_rebase_scenario_builds_expected_failing_trace():
    scenario = StaleBaseRebaseScenario()
    incident = _find_failing_incident(scenario)

    (step,) = incident.steps
    assert step.type == StepType.TOOL_CALL
    assert step.tool_name == "worker_build"
    assert step.tool_args["base_ref"] == "main@stale"
    assert step.error == _STALE_REF_ERROR
    assert "ModuleNotFoundError" in step.error
    assert "agentdoctor.repair.ladder_v2" in step.error
    assert step.provenance["stale_base"] is True

    assert incident.outcome == "failure"
    assert incident.grader_results["stale_base"] is True
    assert incident.final_output == "Build failed: stale base"


def test_unrelated_deploy_scenario_is_a_benign_control():
    scenario = UnrelatedDeployScenario(base_failure_rate=0.0)
    trace = scenario.run_episode(scenario.apply_intervention(InterventionSpec()), random.Random(0))

    assert trace.outcome == "success"
    (step,) = trace.steps
    assert step.tool_name == "deploy_static_bundle"
    assert step.error is None


def test_clear_stale_retry_state_is_top_ranked_positive_effect():
    scenario = StaleBaseRebaseScenario()
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


def test_diagnose_to_verify_pipeline_is_safe_to_review():
    scenario = StaleBaseRebaseScenario()
    incident = _find_failing_incident(scenario)

    report = diagnose(incident, scenario, budget=300, seed=42)
    patch = report.best_repair()
    assert patch is not None
    assert patch.hypothesis_name == "clear_stale_retry_state"

    suites = {
        "original": scenario,
        "variants": StaleBaseRebaseScenario(
            branch_id="worker/t-778-stale-base", stale_base_probability=0.30
        ),
        "unrelated": UnrelatedDeployScenario(),
    }
    verification = verify(suites, patch, n=200, seed=7)

    original = verification.suite("original")
    unrelated = verification.suite("unrelated")
    assert original.after_failure_rate < original.before_failure_rate
    assert abs(unrelated.after_failure_rate - unrelated.before_failure_rate) <= 0.05
    assert verification.decision == "SAFE_TO_REVIEW"
