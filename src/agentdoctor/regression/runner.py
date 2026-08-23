"""Regression Runner: prove a repair didn't just fix one case (spec section 14).

Three suites are run before and after applying a candidate patch:

- ``original``  — the exact incident that triggered diagnosis.
- ``variants``   — structurally similar incidents, to catch overfitting to
  one specific input.
- ``unrelated``  — a suite unrelated to the incident, to catch regressions
  the patch introduced elsewhere.

A patch only clears the gate if the original (and ideally variants) suite
improves and the unrelated suite does not measurably regress.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.repair.engine import Patch
from agentdoctor.replay.runtime import Scenario, run

#: unrelated-suite failure rate is allowed to drift by at most this much
#: before the patch is flagged as introducing a regression.
UNRELATED_REGRESSION_TOLERANCE = 0.05


@dataclass
class SuiteResult:
    name: str
    before_failure_rate: float
    after_failure_rate: float

    @property
    def delta(self) -> float:
        """Positive = failure rate went down (improved) after the patch."""
        return self.before_failure_rate - self.after_failure_rate


@dataclass
class VerificationReport:
    patch: Patch
    suites: list[SuiteResult]

    def suite(self, name: str) -> SuiteResult | None:
        return next((s for s in self.suites if s.name == name), None)

    @property
    def decision(self) -> str:
        original = self.suite("original")
        variants = self.suite("variants")
        unrelated = self.suite("unrelated")

        if original is not None and original.after_failure_rate >= original.before_failure_rate:
            return "REJECT_NO_IMPROVEMENT"
        if variants is not None and variants.after_failure_rate >= variants.before_failure_rate:
            # The fix only works on the exact recorded incident, not on
            # structurally similar cases -- overfit to one input (spec 14.1.B).
            return "REJECT_OVERFIT"
        if unrelated is not None and (
            unrelated.after_failure_rate
            > unrelated.before_failure_rate + UNRELATED_REGRESSION_TOLERANCE
        ):
            return "REJECT_REGRESSION"
        return "SAFE_TO_REVIEW"


def verify(
    suites: dict[str, Scenario],
    patch: Patch,
    n: int = 100,
    seed: int = 0,
) -> VerificationReport:
    results = []
    for name, scenario in suites.items():
        before = run(scenario, n=n, interventions=InterventionSpec(), seed=seed)
        after = run(scenario, n=n, interventions=patch.spec, seed=seed)
        results.append(
            SuiteResult(
                name=name,
                before_failure_rate=before.failure_rate,
                after_failure_rate=after.failure_rate,
            )
        )
    return VerificationReport(patch=patch, suites=results)
