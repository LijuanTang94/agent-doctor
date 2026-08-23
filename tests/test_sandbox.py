import pytest

from agentdoctor.replay.sandbox import UnsafeReplayError, allowed_modes, check_replay_mode
from agentdoctor.trace.schema import SideEffectClass


def test_read_only_allows_live_and_cassette():
    assert "live" in allowed_modes(SideEffectClass.READ_ONLY)
    check_replay_mode(SideEffectClass.READ_ONLY, "live")
    check_replay_mode(SideEffectClass.READ_ONLY, "cassette")


def test_external_payment_denies_everything_but_mock():
    assert allowed_modes(SideEffectClass.EXTERNAL_PAYMENT) == ("mock",)
    check_replay_mode(SideEffectClass.EXTERNAL_PAYMENT, "mock")
    with pytest.raises(UnsafeReplayError):
        check_replay_mode(SideEffectClass.EXTERNAL_PAYMENT, "live")


def test_destructive_write_denies_live():
    with pytest.raises(UnsafeReplayError):
        check_replay_mode(SideEffectClass.DESTRUCTIVE_WRITE, "live")
    check_replay_mode(SideEffectClass.DESTRUCTIVE_WRITE, "sandbox")
