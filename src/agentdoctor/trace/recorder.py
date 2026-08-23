"""Trace Ingestor / Recorder (spec section 7 + 24.2 API draft).

MVP scope: a lightweight context manager an agent loop calls into directly.
A real deployment would sit behind an OpenTelemetry/OpenAI-SDK adapter (see
``agentdoctor.trace.adapters``); the direct API is what that adapter targets.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from agentdoctor.trace.schema import Step, Trace


class RecordingRun:
    def __init__(self, name: str, agent_version: str = "unknown", environment: str = "local"):
        self.name = name
        self.trace = Trace(agent_version=agent_version, environment=environment)

    def set_input(self, value: Any) -> None:
        self.trace.initial_input = value

    def step(self, **kwargs: Any) -> Step:
        return self.trace.add_step(**kwargs)

    def finish(self, final_output: Any = None, outcome: str | None = None) -> None:
        self.trace.final_output = final_output
        self.trace.outcome = outcome


@contextmanager
def record(
    name: str, agent_version: str = "unknown", environment: str = "local"
) -> Iterator[RecordingRun]:
    run = RecordingRun(name=name, agent_version=agent_version, environment=environment)
    yield run
