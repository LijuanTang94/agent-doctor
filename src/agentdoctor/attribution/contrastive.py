"""Causal Attribution: relative-to-correlational evidence (spec section 11).

``Effect(X) = P(failure | baseline) - P(failure | do(X = patched))``

An :class:`Effect` is deliberately not just a number: it carries a
confidence interval and an explicit ``inconclusive`` flag so a hypothesis
that only "sort of" reduced failure under noise isn't mistaken for a
verified root cause.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentdoctor.attribution.confidence import bootstrap_ci
from agentdoctor.replay.runtime import ReplayResult


@dataclass
class Effect:
    label: str
    baseline_failure_rate: float
    intervention_failure_rate: float
    point_estimate: float  # positive = intervention reduced failure
    ci_low: float
    ci_high: float

    @property
    def inconclusive(self) -> bool:
        """True if the CI straddles zero: we cannot rule out no effect."""
        return self.ci_low <= 0.0 <= self.ci_high


def estimate_effect(
    baseline: ReplayResult,
    intervention: ReplayResult,
    label: str,
    n_bootstrap: int = 2000,
    seed: int = 0,
) -> Effect:
    baseline_outcomes = [1 if t.outcome == "failure" else 0 for t in baseline.traces]
    intervention_outcomes = [1 if t.outcome == "failure" else 0 for t in intervention.traces]

    point = baseline.failure_rate - intervention.failure_rate
    ci_low, ci_high = bootstrap_ci(
        baseline_outcomes, intervention_outcomes, n_bootstrap=n_bootstrap, seed=seed
    )

    return Effect(
        label=label,
        baseline_failure_rate=baseline.failure_rate,
        intervention_failure_rate=intervention.failure_rate,
        point_estimate=point,
        ci_low=ci_low,
        ci_high=ci_high,
    )


def rank_hypotheses(effects: list[Effect]) -> list[Effect]:
    """Highest, most confident failure-reduction first."""
    return sorted(effects, key=lambda e: e.point_estimate, reverse=True)
