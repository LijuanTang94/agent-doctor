"""Tool virtualization policy (spec section 9.2).

Deny-by-default: a tool's ``SideEffectClass`` decides whether it may ever
be re-executed live during a causal replay. Destructive writes and payment
tools are never allowed live during replay, matching the spec's safety
requirement that ``Replay Safety`` (real side effects triggered) must be 0.
"""

from __future__ import annotations

from agentdoctor.trace.schema import SideEffectClass

#: side_effect_class -> allowed replay modes, most permissive first.
_ALLOWED_MODES: dict[SideEffectClass, tuple[str, ...]] = {
    SideEffectClass.READ_ONLY: ("live", "cassette"),
    SideEffectClass.IDEMPOTENT_WRITE: ("sandbox", "cassette"),
    SideEffectClass.DESTRUCTIVE_WRITE: ("mock", "sandbox"),
    SideEffectClass.EXTERNAL_PAYMENT: ("mock",),
}


class UnsafeReplayError(RuntimeError):
    """Raised when a replay would execute a real side effect."""


def allowed_modes(side_effect_class: SideEffectClass) -> tuple[str, ...]:
    return _ALLOWED_MODES[side_effect_class]


def check_replay_mode(side_effect_class: SideEffectClass, mode: str) -> None:
    """Deny-by-default guard: raise unless ``mode`` is explicitly allowed."""
    if mode not in allowed_modes(side_effect_class):
        raise UnsafeReplayError(
            f"mode={mode!r} is not permitted for side_effect_class="
            f"{side_effect_class.value!r}; allowed={allowed_modes(side_effect_class)}"
        )
