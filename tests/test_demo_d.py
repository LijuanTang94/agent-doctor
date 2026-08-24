import random

from agentdoctor import diagnose
from agentdoctor.environment import ENVIRONMENT_BLOCKED, classify
from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.trace.schema import StepType

from examples.demo_d.scenario import SANDBOX_PERMISSION_ERROR, SandboxPermissionDeniedScenario


def _find_failing_incident(scenario, seeds=500):
    baseline = scenario.apply_intervention(InterventionSpec())
    for seed in range(seeds):
        trace = scenario.run_episode(baseline, random.Random(seed))
        if trace.outcome == "failure":
            return trace
    raise AssertionError("expected a sandbox-permission-denied failure in the first 500 seeds")


def test_sandbox_permission_denied_scenario_builds_expected_failing_trace():
    scenario = SandboxPermissionDeniedScenario()
    incident = _find_failing_incident(scenario)

    (step,) = incident.steps
    assert step.type == StepType.TOOL_CALL
    assert step.tool_name == "write_file"
    assert step.error == SANDBOX_PERMISSION_ERROR
    assert step.error == (
        "Permission denied: write access to '/var/agent/workspace/output.log' "
        "blocked by sandbox policy (read-only file system)"
    )
    assert step.provenance["environment_blocked"] is True
    assert step.provenance["reason"] == "sandbox_permission_denied"

    assert incident.outcome == "failure"
    assert incident.final_output == "Something went wrong"


def test_scenario_fails_regardless_of_seed_or_intervention():
    """No InterventionSpec layer is wired to this failure: every seed and
    every intervention must still fail."""
    scenario = SandboxPermissionDeniedScenario()

    for seed in range(10):
        cfg = scenario.apply_intervention(InterventionSpec())
        trace = scenario.run_episode(cfg, random.Random(seed))
        assert trace.outcome == "failure"

    interventions = [
        InterventionSpec(model_override="model_b"),
        InterventionSpec(retry_clear_stale_observation=True),
        InterventionSpec(tool_latency_ms={"write_file": 50.0}),
        InterventionSpec(retrieval_mode="gold"),
        InterventionSpec(config_overrides={"session_target": "main"}),
    ]
    for spec in interventions:
        cfg = scenario.apply_intervention(spec)
        trace = scenario.run_episode(cfg, random.Random(0))
        assert trace.outcome == "failure"


def test_diagnose_yields_no_confident_positive_effect_and_classifies_as_environment_blocked():
    scenario = SandboxPermissionDeniedScenario()
    incident = _find_failing_incident(scenario)

    report = diagnose(incident, scenario, budget=300, seed=42)

    assert len(report.effects) > 0
    assert not any(
        (not effect.inconclusive and effect.point_estimate > 0) for effect in report.effects
    )
    # No repair should be selectable: this mirrors best_repair()'s own
    # "not inconclusive and point_estimate > 0" eligibility gate.
    assert report.best_repair() is None

    verdict = classify(incident, report.effects)
    assert verdict == ENVIRONMENT_BLOCKED
