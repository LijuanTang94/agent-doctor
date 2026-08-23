"""Cassette replay + fidelity metrics (spec sections 9.1 and 9.3).

A ``Cassette`` records the tool/model observations of a real trace keyed by
``(step_type, tool_name, args)`` so a no-intervention replay can return the
exact recorded values instead of re-executing anything live. Comparing the
cassette-driven replay's action sequence back against the original trace
gives the ``Action Match Rate`` / ``State Match Rate`` fidelity signals the
spec requires before trusting any causal conclusion drawn from replay.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agentdoctor.trace.schema import Step, Trace


def _key(step: Step) -> str:
    return json.dumps(
        {"tool_name": step.tool_name, "tool_args": step.tool_args}, sort_keys=True
    )


@dataclass
class Cassette:
    recordings: dict[str, Step] = field(default_factory=dict)

    @classmethod
    def from_trace(cls, trace: Trace) -> "Cassette":
        recordings = {}
        for step in trace.steps:
            if step.tool_name is not None:
                recordings[_key(step)] = step
        return cls(recordings=recordings)

    def lookup(self, tool_name: str, tool_args: dict[str, Any]) -> Step | None:
        return self.recordings.get(
            json.dumps({"tool_name": tool_name, "tool_args": tool_args}, sort_keys=True)
        )


@dataclass
class FidelityReport:
    action_match_rate: float
    state_match_rate: float
    n_steps_compared: int


def compute_fidelity(original: Trace, replayed: Trace) -> FidelityReport:
    """Compare a no-intervention replay back against the original trace.

    Steps are compared position-by-position (index). This is intentionally
    simple for MVP: framework-agnostic step alignment (e.g. via LCS) is a
    post-MVP improvement noted in the spec's replay fidelity section.
    """
    n = min(len(original.steps), len(replayed.steps))
    if n == 0:
        return FidelityReport(action_match_rate=0.0, state_match_rate=0.0, n_steps_compared=0)

    action_matches = 0
    state_matches = 0
    for i in range(n):
        o, r = original.steps[i], replayed.steps[i]
        if o.action == r.action and o.tool_name == r.tool_name:
            action_matches += 1
        if o.state_hash is not None and o.state_hash == r.state_hash:
            state_matches += 1

    return FidelityReport(
        action_match_rate=action_matches / n,
        state_match_rate=state_matches / n,
        n_steps_compared=n,
    )
