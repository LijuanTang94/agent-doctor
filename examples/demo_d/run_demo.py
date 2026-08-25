"""Run Demo D end to end: record -> diagnose -> attribute (environment vs
code).

    python -m examples.demo_d.run_demo

Reproduces a sandbox-permission-denied incident -- an agent's ``write_file``
call refused outright by the sandbox's read-only filesystem policy, an
environment-level limitation with no code-level fix -- using the fully
simulated :class:`SandboxPermissionDeniedScenario` so the demo needs no API
keys and no network access.

Unlike demo_a/b/c, this pipeline stops at diagnosis: the point of the
environment/code attribution layer (``agentdoctor.environment.classify``) is
to recognize when no ``InterventionSpec`` layer can address the failure and
refuse to hand out a "repair" for something that was never a code bug, so
``best_repair()``/``verify()`` are never called.
"""

from __future__ import annotations

import random

from agentdoctor import diagnose
from agentdoctor.environment import ENVIRONMENT_BLOCKED, classify
from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.trace.schema import StepType

from examples.demo_d.scenario import SandboxPermissionDeniedScenario


def find_one_failing_incident(scenario: SandboxPermissionDeniedScenario, start_seed: int = 0):
    for seed in range(start_seed, start_seed + 500):
        trace = scenario.run_episode(scenario.apply_intervention(InterventionSpec()), random.Random(seed))
        if trace.outcome == "failure":
            return trace, seed
    raise RuntimeError("could not find a failing incident in 500 seeds")


def main() -> None:
    scenario = SandboxPermissionDeniedScenario()

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
                f"-> {step.observation!r} error={step.error} retry={step.retry_count} "
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

    print("=" * 72)
    print("ATTRIBUTE: environment vs code")
    print("=" * 72)
    verdict = classify(incident_trace, report.effects)
    if verdict == ENVIRONMENT_BLOCKED:
        print(f"DECISION: {verdict}")
        print(
            "No repair is proposed: every tested hypothesis measured ~0 effect, "
            "and the failing step's provenance reports a definitive "
            "environment-level denial (sandbox permission, not a code bug)."
        )
        return

    print("No environment-level signal found; this demo does not fall through "
          "to repair/verify.")


if __name__ == "__main__":
    main()
