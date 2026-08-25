"""Unit tests for agentdoctor.mitigation.classify, in isolation from the
regression/repair pipeline: hand-built Trace/Patch/VerificationReport
fixtures only."""

from __future__ import annotations

from agentdoctor.attribution.contrastive import Effect
from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.mitigation import MITIGATION_ONLY, classify
from agentdoctor.regression.runner import SuiteResult, VerificationReport
from agentdoctor.repair.engine import Patch
from agentdoctor.trace.schema import StepType, Trace


def _masking_trace() -> Trace:
    trace = Trace()
    trace.add_step(
        type=StepType.TOOL_CALL,
        tool_name="claude_cli_invoke",
        error="assertion timeout",
        provenance={"masks_root_cause": True, "reason": "widened_retry_timeout"},
    )
    return trace


def _clean_trace() -> Trace:
    trace = Trace()
    trace.add_step(
        type=StepType.TOOL_CALL,
        tool_name="claude_cli_invoke",
        error="assertion timeout",
        provenance={},
    )
    return trace


def _patch() -> Patch:
    return Patch(
        hypothesis_name="clear_stale_retry_state",
        ladder_rung="agent policy / retry / state patch",
        risk_rank=4,
        description="clear stale retry state",
        spec=InterventionSpec(),
        evidence=Effect(
            label="clear_stale_retry_state",
            baseline_failure_rate=0.4,
            intervention_failure_rate=0.02,
            point_estimate=0.38,
            ci_low=0.20,
            ci_high=0.55,
        ),
    )


def _verification_report(*, safe_to_review: bool) -> VerificationReport:
    original_after = 0.03 if safe_to_review else 0.5
    suites = [
        SuiteResult(name="original", before_failure_rate=0.4, after_failure_rate=original_after),
        SuiteResult(name="variants", before_failure_rate=0.3, after_failure_rate=0.03),
        SuiteResult(name="unrelated", before_failure_rate=0.05, after_failure_rate=0.05),
    ]
    return VerificationReport(patch=_patch(), suites=suites)


def test_masking_signal_with_safe_to_review_patch_is_mitigation_only():
    trace = _masking_trace()
    verification = _verification_report(safe_to_review=True)

    assert verification.decision == "SAFE_TO_REVIEW"
    assert classify(trace, _patch(), verification) == MITIGATION_ONLY


def test_no_patch_yields_none_regardless_of_masking_signal():
    trace = _masking_trace()
    verification = _verification_report(safe_to_review=True)

    assert classify(trace, None, verification) is None


def test_decision_not_safe_to_review_yields_none():
    trace = _masking_trace()
    verification = _verification_report(safe_to_review=False)

    assert verification.decision != "SAFE_TO_REVIEW"
    assert classify(trace, _patch(), verification) is None


def test_no_masking_signal_yields_none():
    trace = _clean_trace()
    verification = _verification_report(safe_to_review=True)

    assert classify(trace, _patch(), verification) is None


def test_ordinary_clean_repair_without_masks_flag_yields_none():
    """An everyday clean repair carries no `masks_root_cause` provenance at
    all -- absence of the key (not just a falsy value) must yield None."""
    trace = Trace()
    trace.add_step(
        type=StepType.TOOL_CALL,
        tool_name="write_file",
        provenance={"unrelated_key": "irrelevant"},
    )
    verification = _verification_report(safe_to_review=True)

    assert classify(trace, _patch(), verification) is None
