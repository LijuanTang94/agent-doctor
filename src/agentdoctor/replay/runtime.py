"""Replay Runtime (spec section 7 + 9): re-run a scenario under a given
:class:`InterventionSpec` for N counterfactual trials.

A ``Scenario`` is anything that knows how to (a) turn an intervention spec
into an effective world config, and (b) run one episode against that config
with a seeded RNG, returning a :class:`Trace`. This keeps the runtime
agnostic to *what* is being replayed (a live cassette-backed production
incident, or a fully simulated benchmark world like Demo A) while giving
:mod:`agentdoctor.attribution` and :mod:`agentdoctor.planner` one uniform
interface to run experiments against.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Protocol

from agentdoctor.interventions.base import InterventionSpec, active_builder
from agentdoctor.trace.schema import Trace


class Scenario(Protocol):
    def apply_intervention(self, spec: InterventionSpec) -> dict[str, Any]:
        """Turn a do-spec into an effective, concrete world config."""
        ...

    def run_episode(self, effective_config: dict[str, Any], rng: random.Random) -> Trace:
        """Run one episode against a concrete config, return the resulting trace."""
        ...


@dataclass
class ReplayResult:
    traces: list[Trace]
    n: int
    interventions: InterventionSpec

    @property
    def failure_rate(self) -> float:
        if not self.traces:
            return 0.0
        failures = sum(1 for t in self.traces if t.outcome == "failure")
        return failures / len(self.traces)

    @property
    def success_rate(self) -> float:
        return 1.0 - self.failure_rate


def run(
    scenario: Scenario,
    n: int = 20,
    interventions: InterventionSpec | None = None,
    seed: int = 0,
) -> ReplayResult:
    if interventions is None:
        builder = active_builder()
        interventions = builder.spec if builder is not None else InterventionSpec()

    effective_config = scenario.apply_intervention(interventions)
    traces = []
    for i in range(n):
        rng = random.Random(seed * 1_000_003 + i)
        traces.append(scenario.run_episode(effective_config, rng))
    return ReplayResult(traces=traces, n=n, interventions=interventions)
