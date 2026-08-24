import random

from agentdoctor import diagnose, verify
from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.trace.schema import StepType

from examples.demo_c.scenario import IntermittentEmptyOutputScenario, UnrelatedBotTaskScenario

_EMPTY_OUTPUT_ERROR = "empty output (outBytes=0): claude-cli exited before responding"


def _find_failing_incident(scenario, seeds=500):
    baseline = scenario.apply_intervention(InterventionSpec())
    for seed in range(seeds):
        trace = scenario.run_episode(baseline, random.Random(seed))
        if trace.outcome == "failure" and trace.grader_results.get("resume_race"):
            return trace
    raise AssertionError("expected at least one resume-race failure in the first 500 seeds")


def test_intermittent_empty_output_scenario_builds_expected_failing_trace():
    scenario = IntermittentEmptyOutputScenario()
    incident = _find_failing_incident(scenario)

    (step,) = incident.steps
    assert step.type == StepType.TOOL_CALL
    assert step.tool_name == "claude_cli_invoke"
    assert step.tool_args["resume"] is True
    assert step.error == _EMPTY_OUTPUT_ERROR
    assert "outBytes=0" in step.error
    assert "empty output" in step.error
    assert step.provenance["outBytes"] == 0

    assert incident.outcome == "failure"
    assert incident.grader_results["resume_race"] is True
    assert incident.final_output == "Something went wrong"


def test_unrelated_bot_task_scenario_is_a_benign_control():
    scenario = UnrelatedBotTaskScenario(base_failure_rate=0.0)
    trace = scenario.run_episode(scenario.apply_intervention(InterventionSpec()), random.Random(0))

    assert trace.outcome == "success"
    (step,) = trace.steps
    assert step.tool_name == "slash_command_lookup"
    assert step.error is None


def test_clear_stale_retry_state_is_top_ranked_positive_effect():
    scenario = IntermittentEmptyOutputScenario()
    incident = _find_failing_incident(scenario)

    report = diagnose(incident, scenario, budget=300, seed=42)
    by_label = {e.label: e for e in report.effects}

    assert "clear_stale_retry_state" in by_label
    top_effect = report.effects[0]
    assert top_effect.label == "clear_stale_retry_state"
    assert not top_effect.inconclusive
    assert top_effect.point_estimate > 0

    for other_label, other_effect in by_label.items():
        if other_label == "clear_stale_retry_state":
            continue
        assert top_effect.point_estimate >= other_effect.point_estimate

    patch = report.best_repair()
    assert patch is not None
    assert patch.hypothesis_name == "clear_stale_retry_state"


def test_diagnose_to_verify_pipeline_is_safe_to_review():
    scenario = IntermittentEmptyOutputScenario()
    incident = _find_failing_incident(scenario)

    report = diagnose(incident, scenario, budget=300, seed=42)
    patch = report.best_repair()
    assert patch is not None
    assert patch.hypothesis_name == "clear_stale_retry_state"

    suites = {
        "original": scenario,
        "variants": IntermittentEmptyOutputScenario(
            session_id="codesFlow_bot-session-2", resume_race_probability=0.29
        ),
        "unrelated": UnrelatedBotTaskScenario(),
    }
    verification = verify(suites, patch, n=200, seed=7)

    original = verification.suite("original")
    unrelated = verification.suite("unrelated")
    assert original.after_failure_rate < original.before_failure_rate
    assert unrelated.after_failure_rate <= unrelated.before_failure_rate + 0.05
    assert verification.decision == "SAFE_TO_REVIEW"
