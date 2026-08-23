"""Minimal scenario fixtures shared across tests, independent of the
examples/demo_a package so core-package tests don't depend on it."""

from __future__ import annotations

import random
from dataclasses import dataclass

from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.trace.schema import Trace


@dataclass
class CoinFlipScenario:
    """do(model="fixed") drops the failure bias from 0.5 to 0.05."""

    baseline_bias: float = 0.5
    fixed_bias: float = 0.05

    def apply_intervention(self, spec: InterventionSpec) -> float:
        return self.fixed_bias if spec.model_override == "fixed" else self.baseline_bias

    def run_episode(self, bias: float, rng: random.Random) -> Trace:
        trace = Trace()
        trace.outcome = "failure" if rng.random() < bias else "success"
        return trace
