"""Run Demo G end to end: record -> diagnose -> repair -> verify.

    python -m examples.demo_g.run_demo

Reproduces a NO-PROGRESS TOOL LOOP incident -- a ``ticket-triage-agent``
re-issuing the exact same ``list_open_tickets`` tool call, with identical
args and an unchanged state hash, until it gives up -- using the
fully-simulated :class:`NoProgressToolLoopScenario` so the demo needs no API
keys and no network access.
"""

from __future__ import annotations

import random

from agentdoctor import diagnose, record, verify
from agentdoctor.trace.schema import StepType

from examples.demo_g.scenario import NoProgressToolLoopScenario, UnrelatedBotTaskScenario


def find_one_failing_incident(scenario: NoProgressToolLoopScenario, start_seed: int = 0):
    for seed in range(start_seed, start_seed + 500):
        trace = scenario.run_episode(scenario.apply_intervention(_no_intervention()), random.Random(seed))
        if trace.outcome == "failure" and trace.grader_results.get("no_progress_loop"):
            return trace, seed
    raise RuntimeError("could not find a failing incident in 500 seeds")


def _no_intervention():
    from agentdoctor.interventions.base import InterventionSpec

    return InterventionSpec()


def main() -> None:
    scenario = NoProgressToolLoopScenario()

    incident_trace, incident_seed = find_one_failing_incident(scenario)

    print("=" * 72)
    print("PRODUCTION INCIDENT")
    print("=" * 72)
    print(f"outcome: {incident_trace.outcome}")
    print(f"input:   {incident_trace.initial_input}")
    for step in incident_trace.steps:
        if step.type == StepType.TOOL_CALL:
            print(
                f"  step {step.index}: {step.tool_name}({step.tool_args}) "
                f"-> {step.observation!r} state_hash={step.state_hash} "
                f"latency={step.latency_ms:.0f}ms"
            )
    print(f"final_output: {incident_trace.final_output}")
    print()

    print("=" * 72)
    print("DIAGNOSE: planning + running counterfactual experiments")
    print("=" * 72)
    report = diagnose(incident_trace, scenario, budget=300, seed=42)
    print(f"baseline failure rate: {report.baseline.failure_rate:.2f} ({report.runs_per_arm} runs)")
    print(f"total experiment runs: {report.total_runs}")
    print()
    print("HYPOTHESES (ranked by estimated failure reduction)")
    for effect in report.effects:
        flag = "  (inconclusive)" if effect.inconclusive else ""
        print(
            f"  {effect.label:28s} effect={effect.point_estimate:+.2f}"
            f"  95% CI=[{effect.ci_low:+.2f}, {effect.ci_high:+.2f}]{flag}"
        )
    print()

    patch = report.best_repair()
    if patch is None:
        print("No confident repair found.")
        return

    print("=" * 72)
    print("SUGGESTED PATCH")
    print("=" * 72)
    print(f"hypothesis: {patch.hypothesis_name}")
    print(f"ladder rung: {patch.ladder_rung} (risk rank {patch.risk_rank})")
    print(f"rationale: {patch.description}")
    print(
        f"evidence: effect={patch.evidence.point_estimate:+.2f}, "
        f"95% CI=[{patch.evidence.ci_low:+.2f}, {patch.evidence.ci_high:+.2f}]"
    )
    print()

    print("=" * 72)
    print("VERIFY: original incident + variants + unrelated regression suite")
    print("=" * 72)
    suites = {
        "original": scenario,
        "variants": NoProgressToolLoopScenario(
            session_id="ticket-triage-session-2", loop_probability=0.50
        ),
        "unrelated": UnrelatedBotTaskScenario(),
    }
    verification = verify(suites, patch, n=200, seed=7)
    for suite in verification.suites:
        print(
            f"  {suite.name:10s} failure_rate {suite.before_failure_rate:.2%} "
            f"-> {suite.after_failure_rate:.2%}  (delta {suite.delta:+.2%})"
        )
    print()
    print(f"DECISION: {verification.decision}")

    with record(name="demo-g-recorder-smoke-test") as run:
        run.set_input(incident_trace.initial_input)
        run.step(type=StepType.TOOL_CALL, tool_name="list_open_tickets", observation="ok")
        run.finish(final_output="ok", outcome="success")
    assert run.trace.outcome == "success"


if __name__ == "__main__":
    main()
