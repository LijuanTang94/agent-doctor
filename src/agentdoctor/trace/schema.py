"""Canonical Trace: the unified trace data model (spec section 8).

This is the substrate every other component (replay, intervention,
attribution, repair, regression) reads and writes. A trace must be complete
enough to re-run as a controlled experiment, not just complete enough to
render in a UI.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class SideEffectClass(str, enum.Enum):
    """How dangerous is it to re-execute this tool call during replay."""

    READ_ONLY = "read_only"
    IDEMPOTENT_WRITE = "idempotent_write"
    DESTRUCTIVE_WRITE = "destructive_write"
    EXTERNAL_PAYMENT = "external_payment"


class StepType(str, enum.Enum):
    MODEL_DECISION = "model_decision"
    TOOL_CALL = "tool_call"
    RETRIEVAL = "retrieval"
    OBSERVATION = "observation"
    FINAL_OUTPUT = "final_output"


class Step(BaseModel):
    index: int
    timestamp: float = Field(default_factory=time.time)
    type: StepType

    # model decision provenance
    prompt_snapshot: str | None = None
    message_history: list[dict[str, Any]] = Field(default_factory=list)
    model_config_snapshot: dict[str, Any] = Field(default_factory=dict)

    # action taken
    action: str | None = None
    tool_name: str | None = None
    tool_args: dict[str, Any] = Field(default_factory=dict)

    # result
    observation: Any = None
    retrieval_docs: list[dict[str, Any]] = Field(default_factory=list)

    # serving-layer provenance
    latency_ms: float = 0.0
    retry_count: int = 0
    error: str | None = None

    # replay bookkeeping
    state_hash: str | None = None
    side_effect_class: SideEffectClass = SideEffectClass.READ_ONLY
    provenance: dict[str, Any] = Field(default_factory=dict)


class Trace(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_version: str = "unknown"
    environment: str = "unknown"

    initial_input: Any = None
    final_output: Any = None
    outcome: str | None = None  # "success" | "failure" | None

    steps: list[Step] = Field(default_factory=list)

    external_dependencies: dict[str, Any] = Field(default_factory=dict)
    grader_results: dict[str, Any] = Field(default_factory=dict)
    reproducibility_metadata: dict[str, Any] = Field(default_factory=dict)

    def add_step(self, **kwargs: Any) -> Step:
        step = Step(index=len(self.steps), **kwargs)
        self.steps.append(step)
        return step

    def to_jsonl(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json())
            f.write("\n")

    @classmethod
    def from_jsonl(cls, path: str) -> "Trace":
        with open(path, encoding="utf-8") as f:
            line = f.readline()
        return cls.model_validate_json(line)
