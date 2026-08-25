import random

from agentdoctor import diagnose, verify
from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.trace.schema import StepType

from examples.demo_g.scenario import NoProgressToolLoopScenario, UnrelatedBotTaskScenario


def _find_failing_incident(scenario, seeds=500):
    baseline = scenario.apply_intervention(InterventionSpec())
    for seed in range(seeds):
        trace = scenario.run_episode(baseline, random.Random(seed))
        if trace.outcome == "failure" and trace.grader_results.get("no_progress_loop"):
            return trace
    raise AssertionError("expected at least one no-progress-loop failure in the first 500 seeds")


def test_no_progress_tool_loop_scenario_builds_expected_failing_trace():
    scenario = NoProgressToolLoopScenario()
    incident = _find_failing_incident(scenario)

    assert len(incident.steps) == scenario.max_loop_iterations
    for step in incident.steps:
        assert step.type == StepType.TOOL_CALL
        assert step.tool_name == "list_open_tickets"
        assert step.tool_args == {"queue": "unassigned", "page": 1}
        assert step.observation == "3 open tickets (unchanged)"
        assert step.state_hash == "ticket_queue_state_v1"

    assert incident.outcome == "failure"
    assert incident.grader_results["no_progress_loop"] is True
    assert incident.final_output == (
        f"Gave up after {scenario.max_loop_iterations} repeated list_open_tickets calls "
        "with no state change."
    )


def test_unrelated_bot_task_scenario_is_a_benign_control():
    scenario = UnrelatedBotTaskScenario(base_failure_rate=0.0)
    trace = scenario.run_episode(scenario.apply_intervention(InterventionSpec()), random.Random(0))

    assert trace.outcome == "success"
    (step,) = trace.steps
    assert step.tool_name == "slash_command_lookup"
    assert step.error is None


def test_tool_schema_ablation_is_top_ranked_positive_effect():
    scenario = NoProgressToolLoopScenario()
    incident = _find_failing_incident(scenario)

    report = diagnose(incident, scenario, budget=300, seed=42)
    by_label = {e.label: e for e in report.effects}

    assert "tool_schema_ablation" in by_label
    top_effect = report.effects[0]
    assert top_effect.label == "tool_schema_ablation"
    assert not top_effect.inconclusive
    assert top_effect.point_estimate > 0
    assert top_effect.ci_low > 0

    for other_label, other_effect in by_label.items():
        if other_label == "tool_schema_ablation":
            continue
        assert top_effect.point_estimate >= other_effect.point_estimate

    patch = report.best_repair()
    assert patch is not None
    assert patch.hypothesis_name == "tool_schema_ablation"


def test_diagnose_to_verify_pipeline_is_safe_to_review():
    scenario = NoProgressToolLoopScenario()
    incident = _find_failing_incident(scenario)

    report = diagnose(incident, scenario, budget=300, seed=42)
    patch = report.best_repair()
    assert patch is not None
    assert patch.hypothesis_name == "tool_schema_ablation"

    suites = {
        "original": scenario,
        "variants": NoProgressToolLoopScenario(
            session_id="ticket-triage-session-2", loop_probability=0.50
        ),
        "unrelated": UnrelatedBotTaskScenario(),
    }
    verification = verify(suites, patch, n=200, seed=7)

    original = verification.suite("original")
    unrelated = verification.suite("unrelated")
    assert original.after_failure_rate < original.before_failure_rate
    assert abs(unrelated.after_failure_rate - unrelated.before_failure_rate) <= 0.05
    assert verification.decision == "SAFE_TO_REVIEW"
