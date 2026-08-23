"""Top-level ``diagnose()`` orchestration (spec section 24.2 API draft).

Wires planner -> replay -> attribution into one call: plan competing
hypotheses from the failing trace's surface signals, spend the experiment
budget running each of them (plus a shared baseline) through the replay
runtime, and rank the resulting causal effects.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentdoctor.attribution.contrastive import Effect, estimate_effect, rank_hypotheses
from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.planner.rule_planner import Hypothesis, plan_experiments
from agentdoctor.repair.engine import Patch, best_repair
from agentdoctor.replay.runtime import ReplayResult, Scenario, run
from agentdoctor.trace.schema import Trace

MIN_RUNS_PER_ARM = 5


@dataclass
class DiagnosisReport:
    trace: Trace
    hypotheses: list[Hypothesis]
    effects: list[Effect]
    baseline: ReplayResult
    runs_per_arm: int

    @property
    def total_runs(self) -> int:
        return self.runs_per_arm * (len(self.hypotheses) + 1)

    def best_repair(self) -> Patch | None:
        return best_repair(self.effects, self.hypotheses)


def diagnose(trace: Trace, scenario: Scenario, budget: int = 40, seed: int = 0) -> DiagnosisReport:
    hypotheses = plan_experiments(trace)
    runs_per_arm = max(MIN_RUNS_PER_ARM, budget // (len(hypotheses) + 1))

    baseline = run(scenario, n=runs_per_arm, interventions=InterventionSpec(), seed=seed)

    effects = []
    for hypothesis in hypotheses:
        result = run(scenario, n=runs_per_arm, interventions=hypothesis.spec, seed=seed)
        effects.append(estimate_effect(baseline, result, label=hypothesis.name, seed=seed))

    return DiagnosisReport(
        trace=trace,
        hypotheses=hypotheses,
        effects=rank_hypotheses(effects),
        baseline=baseline,
        runs_per_arm=runs_per_arm,
    )
