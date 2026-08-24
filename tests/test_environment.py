"""Unit tests for agentdoctor.environment.classify, in isolation from the
diagnose/replay pipeline: hand-built Trace/Effect fixtures only."""

from __future__ import annotations

from agentdoctor.attribution.contrastive import Effect
from agentdoctor.environment import ENVIRONMENT_BLOCKED, classify
from agentdoctor.trace.schema import StepType, Trace


def _blocked_trace() -> Trace:
    trace = Trace()
    trace.add_step(
        type=StepType.TOOL_CALL,
        tool_name="write_file",
        error="Permission denied: read-only file system",
        provenance={"environment_blocked": True, "reason": "sandbox_permission_denied"},
    )
    return trace


def _unblocked_trace() -> Trace:
    trace = Trace()
    trace.add_step(
        type=StepType.TOOL_CALL,
        tool_name="claude_cli_invoke",
        error="empty output (outBytes=0)",
        provenance={"outBytes": 0},
    )
    return trace


def _inconclusive_effect(label: str) -> Effect:
    return Effect(
        label=label,
        baseline_failure_rate=1.0,
        intervention_failure_rate=1.0,
        point_estimate=0.0,
        ci_low=-0.05,
        ci_high=0.05,
    )


def _confident_positive_effect(label: str) -> Effect:
    return Effect(
        label=label,
        baseline_failure_rate=0.4,
        intervention_failure_rate=0.02,
        point_estimate=0.38,
        ci_low=0.20,
        ci_high=0.55,
    )


def _confident_negative_effect(label: str) -> Effect:
    """A confident effect that makes things WORSE -- point_estimate < 0.
    Must not be treated as a code fix even though it's not inconclusive."""
    return Effect(
        label=label,
        baseline_failure_rate=0.2,
        intervention_failure_rate=0.5,
        point_estimate=-0.30,
        ci_low=-0.45,
        ci_high=-0.15,
    )


def test_environment_signal_with_all_inconclusive_effects_is_environment_blocked():
    trace = _blocked_trace()
    effects = [
        _inconclusive_effect("clear_stale_retry_state"),
        _inconclusive_effect("model_swap"),
    ]

    assert classify(trace, effects) == ENVIRONMENT_BLOCKED


def test_environment_signal_with_confident_positive_effect_yields_none():
    """Precedence rule: a confident, positive code-level fix wins over the
    raw environment_blocked provenance signal."""
    trace = _blocked_trace()
    effects = [
        _inconclusive_effect("model_swap"),
        _confident_positive_effect("clear_stale_retry_state"),
    ]

    assert classify(trace, effects) is None


def test_no_environment_signal_yields_none_regardless_of_effects():
    trace = _unblocked_trace()

    assert classify(trace, [_inconclusive_effect("clear_stale_retry_state")]) is None
    assert classify(trace, [_confident_positive_effect("clear_stale_retry_state")]) is None
    assert classify(trace, []) is None


def test_environment_signal_with_confident_negative_effect_is_still_environment_blocked():
    """A confident effect that makes failures worse is not a 'code fix';
    the environment verdict must still hold."""
    trace = _blocked_trace()
    effects = [_confident_negative_effect("model_swap")]

    assert classify(trace, effects) == ENVIRONMENT_BLOCKED


def test_environment_signal_requires_truthy_flag_not_just_key_presence():
    trace = Trace()
    trace.add_step(
        type=StepType.TOOL_CALL,
        tool_name="write_file",
        provenance={"environment_blocked": False},
    )

    assert classify(trace, [_inconclusive_effect("model_swap")]) is None
