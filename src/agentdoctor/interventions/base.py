"""Intervention Engine: do-style operations on trace variables (spec section 10).

An :class:`InterventionSpec` is a plain, hashable-by-value description of
"what would be different" during a replay. It never touches the original
trace; :mod:`agentdoctor.replay.runtime` reads it and adjusts the simulated
world (model policy, tool latency, retry behavior, retrieval, prompt rules)
accordingly. Keeping the spec a dumb data object means attribution/planner
code can generate and compare hundreds of them without any replay side
effects.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterator

from agentdoctor.trace.schema import Trace

_active_builder: ContextVar["InterventionBuilder | None"] = ContextVar(
    "_active_builder", default=None
)


@dataclass
class InterventionSpec:
    """do(X = patched) for every supported variable layer."""

    # Model layer
    model_override: str | None = None
    model_resample_seed: int | None = None

    # Prompt layer: rule_id -> replacement text ("" to remove)
    prompt_overrides: dict[str, str] = field(default_factory=dict)

    # Tool layer: tool_name -> override
    tool_latency_ms: dict[str, float] = field(default_factory=dict)
    tool_timeout: dict[str, bool] = field(default_factory=dict)
    tool_error_rate: dict[str, float] = field(default_factory=dict)

    # Retrieval layer
    retrieval_mode: str | None = None  # "gold" | "empty" | None (unchanged)

    # Serving / orchestrator layer
    retry_clear_stale_observation: bool | None = None

    def describe(self) -> str:
        parts = []
        if self.model_override:
            parts.append(f"model={self.model_override}")
        if self.model_resample_seed is not None:
            parts.append(f"resample_seed={self.model_resample_seed}")
        for rule_id in self.prompt_overrides:
            parts.append(f"prompt[{rule_id}]")
        for tool, ms in self.tool_latency_ms.items():
            parts.append(f"latency({tool})={ms}ms")
        for tool, on in self.tool_timeout.items():
            if on:
                parts.append(f"timeout({tool})")
        for tool, rate in self.tool_error_rate.items():
            parts.append(f"error_rate({tool})={rate}")
        if self.retrieval_mode:
            parts.append(f"retrieval={self.retrieval_mode}")
        if self.retry_clear_stale_observation is not None:
            parts.append(f"clear_stale_observation={self.retry_clear_stale_observation}")
        return ", ".join(parts) if parts else "baseline (no intervention)"


class _ToolProxy:
    def __init__(self, spec: InterventionSpec, tool_name: str):
        self._spec = spec
        self._tool_name = tool_name

    def latency(self, ms: float) -> "_ToolProxy":
        self._spec.tool_latency_ms[self._tool_name] = ms
        return self

    def timeout(self, enabled: bool = True) -> "_ToolProxy":
        self._spec.tool_timeout[self._tool_name] = enabled
        return self

    def error_rate(self, rate: float) -> "_ToolProxy":
        self._spec.tool_error_rate[self._tool_name] = rate
        return self


class _PromptProxy:
    def __init__(self, spec: InterventionSpec):
        self._spec = spec

    def replace(self, rule_id: str, text: str) -> "_PromptProxy":
        self._spec.prompt_overrides[rule_id] = text
        return self

    def remove(self, rule_id: str) -> "_PromptProxy":
        self._spec.prompt_overrides[rule_id] = ""
        return self


class InterventionBuilder:
    """Fluent builder matching the spec's section 10.2 API sketch."""

    def __init__(self, trace: Trace | None = None):
        self.trace = trace
        self.spec = InterventionSpec()
        self.prompt = _PromptProxy(self.spec)

    def tool(self, name: str) -> _ToolProxy:
        return _ToolProxy(self.spec, name)

    def model(
        self, override: str | None = None, resample_seed: int | None = None
    ) -> "InterventionBuilder":
        if override is not None:
            self.spec.model_override = override
        if resample_seed is not None:
            self.spec.model_resample_seed = resample_seed
        return self

    def retrieval(self, mode: str) -> "InterventionBuilder":
        self.spec.retrieval_mode = mode
        return self

    def retry_policy(self, clear_stale_observation: bool | None = None) -> "InterventionBuilder":
        if clear_stale_observation is not None:
            self.spec.retry_clear_stale_observation = clear_stale_observation
        return self

    def build(self) -> InterventionSpec:
        return self.spec


@contextmanager
def intervene(trace: Trace | None = None) -> Iterator[InterventionBuilder]:
    builder = InterventionBuilder(trace)
    token = _active_builder.set(builder)
    try:
        yield builder
    finally:
        _active_builder.reset(token)


def active_builder() -> InterventionBuilder | None:
    return _active_builder.get()
