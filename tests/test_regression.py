import random
from dataclasses import dataclass

from agentdoctor.attribution.contrastive import Effect
from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.regression.runner import verify
from agentdoctor.repair.engine import Patch
from agentdoctor.trace.schema import Trace
from tests.scenarios import CoinFlipScenario


@dataclass
class ConstantBiasScenario:
    """Unaffected by the patch: an unrelated-suite negative control."""

    bias: float = 0.05

    def apply_intervention(self, spec: InterventionSpec) -> float:
        return self.bias

    def run_episode(self, bias: float, rng: random.Random) -> Trace:
        trace = Trace()
        trace.outcome = "failure" if rng.random() < bias else "success"
        return trace


@dataclass
class RegressesUnderPatchScenario:
    """The patch makes this suite *worse* -- should trip REJECT_REGRESSION."""

    def apply_intervention(self, spec: InterventionSpec) -> float:
        return 0.6 if spec.model_override == "fixed" else 0.05

    def run_episode(self, bias: float, rng: random.Random) -> Trace:
        trace = Trace()
        trace.outcome = "failure" if rng.random() < bias else "success"
        return trace


def _patch() -> Patch:
    return Patch(
        hypothesis_name="model_fix",
        ladder_rung="test rung",
        risk_rank=1,
        description="test patch",
        spec=InterventionSpec(model_override="fixed"),
        evidence=Effect(
            label="model_fix",
            baseline_failure_rate=0.5,
            intervention_failure_rate=0.05,
            point_estimate=0.45,
            ci_low=0.3,
            ci_high=0.6,
        ),
    )


def test_verify_reports_safe_to_review_when_no_regression():
    patch = _patch()
    suites = {
        "original": CoinFlipScenario(),
        "unrelated": ConstantBiasScenario(),
    }
    report = verify(suites, patch, n=300, seed=0)

    original = report.suite("original")
    unrelated = report.suite("unrelated")
    assert original.after_failure_rate < original.before_failure_rate
    assert abs(unrelated.after_failure_rate - unrelated.before_failure_rate) < 0.05
    assert report.decision == "SAFE_TO_REVIEW"


def test_verify_flags_regression_in_unrelated_suite():
    patch = _patch()
    suites = {
        "original": CoinFlipScenario(),
        "unrelated": RegressesUnderPatchScenario(),
    }
    report = verify(suites, patch, n=300, seed=0)

    assert report.decision == "REJECT_REGRESSION"


def test_verify_flags_overfit_when_variants_dont_improve():
    """original improves but variants don't -> the fix is overfit to the
    one recorded incident, not the underlying failure class."""
    patch = _patch()
    suites = {
        "original": CoinFlipScenario(),
        "variants": RegressesUnderPatchScenario(),
        "unrelated": ConstantBiasScenario(),
    }
    report = verify(suites, patch, n=300, seed=0)

    assert report.decision == "REJECT_OVERFIT"
