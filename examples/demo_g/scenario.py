"""Demo G scenario: 'no-progress tool loop'.

Reproduces a ``ticket-triage-agent`` incident: the agent re-issues the exact
same read-only tool call (``list_open_tickets`` against the unassigned
queue) over and over. Nothing about the world changes between calls --
same args, same observation, same :attr:`~agentdoctor.trace.schema.Step.state_hash`
-- so the agent never makes progress toward resolving the queue and
eventually gives up, and the turn fails.

The planner's surface-signal gate for this shape is the ``repeated_tools``
check in :mod:`agentdoctor.planner.rule_planner` (``Counter(tool_name ...)``,
``c > 1``), which proposes the ``tool_schema_ablation`` hypothesis (repair
ladder rung 3, "tool description/schema patch": clarify the tool's
description/schema so the agent stops re-issuing it once nothing has
changed). This demo wires that hypothesis, via the existing generic
:class:`~agentdoctor.interventions.base.InterventionSpec` field
``prompt_overrides["tool_disambiguation"]``, to mean "inject a
check-before-repeat instruction": before re-issuing a tool call, compare its
would-be state hash against the last call's and pivot to a different action
if nothing changed. That breaks the loop and drives the failure rate to
(near) zero.

Like Demo C and Demo E, this is a synthetic, seeded Monte Carlo world rather
than a replay of a recorded cassette: a fourth "planted root cause"
benchmark (spec section 21.1) that ``diagnose()`` and ``verify()`` can be
run against end-to-end without any external API dependency.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.trace.schema import SideEffectClass, StepType, Trace

_TOOL_NAME = "list_open_tickets"
_LOOP_ARGS = {"queue": "unassigned", "page": 1}
_STALE_OBSERVATION = "3 open tickets (unchanged)"
_LOOP_STATE_HASH = "ticket_queue_state_v1"


@dataclass
class WorldConfig:
    backend: str = "ticket-triage-agent"
    tool_name: str = _TOOL_NAME
    loop_probability: float = 0.55
    max_loop_iterations: int = 5
    inject_check_before_repeat: bool = False
    unrelated_error_rate: float = 0.02


@dataclass
class NoProgressToolLoopScenario:
    """The agent repeats ``list_open_tickets`` on the unassigned queue with
    identical args and an unchanged ``state_hash`` every time -- no
    progress -- until it gives up, on roughly half of turns, independent of
    message content."""

    session_id: str = "ticket-triage-session-1"
    loop_probability: float = 0.55
    max_loop_iterations: int = 5
    unrelated_error_rate: float = 0.02

    def _base_config(self) -> WorldConfig:
        return WorldConfig(
            loop_probability=self.loop_probability,
            max_loop_iterations=self.max_loop_iterations,
            unrelated_error_rate=self.unrelated_error_rate,
        )

    def apply_intervention(self, spec: InterventionSpec) -> WorldConfig:
        cfg = self._base_config()
        if spec.prompt_overrides.get("tool_disambiguation"):
            cfg.inject_check_before_repeat = True
        # Retry-state clearing, tool-latency normalization, retrieval mode,
        # config-layer routing, and model swap all target failure classes
        # that have no bearing on an agent repeating one read-only tool
        # call with unchanged state, so they are intentionally left
        # unwired here.
        return cfg

    def run_episode(self, cfg: WorldConfig, rng: random.Random) -> Trace:
        trace = Trace(agent_version=cfg.backend, environment="demo_g_sim")
        trace.initial_input = (
            f"user turn on session {self.session_id}: resolve the unassigned queue"
        )
        trace.reproducibility_metadata = {"backend": cfg.backend, "session_id": self.session_id}

        looping = rng.random() < cfg.loop_probability

        if looping:
            repeats = 2 if cfg.inject_check_before_repeat else cfg.max_loop_iterations
            for i in range(repeats):
                trace.add_step(
                    type=StepType.TOOL_CALL,
                    tool_name=cfg.tool_name,
                    tool_args=dict(_LOOP_ARGS),
                    latency_ms=120.0,
                    observation=_STALE_OBSERVATION,
                    state_hash=_LOOP_STATE_HASH,
                    side_effect_class=SideEffectClass.READ_ONLY,
                    provenance={"iteration": i, "no_state_change": True},
                )

            if cfg.inject_check_before_repeat:
                trace.add_step(
                    type=StepType.MODEL_DECISION,
                    action=(
                        "detected repeated call with unchanged state_hash; "
                        "escalate to human triage instead of repeating"
                    ),
                    latency_ms=10.0,
                    side_effect_class=SideEffectClass.READ_ONLY,
                    provenance={"tool_disambiguation_check": True},
                )
                unrelated_failure = rng.random() < cfg.unrelated_error_rate
                trace.outcome = "failure" if unrelated_failure else "success"
                trace.final_output = (
                    "Escalated unassigned queue to human triage."
                    if not unrelated_failure
                    else "Escalation failed (unrelated)."
                )
            else:
                trace.outcome = "failure"
                trace.final_output = (
                    f"Gave up after {repeats} repeated {cfg.tool_name} calls "
                    "with no state change."
                )
        else:
            trace.add_step(
                type=StepType.TOOL_CALL,
                tool_name=cfg.tool_name,
                tool_args=dict(_LOOP_ARGS),
                latency_ms=120.0,
                observation="3 open tickets -> assigned to agent_1",
                side_effect_class=SideEffectClass.READ_ONLY,
            )
            unrelated_failure = rng.random() < cfg.unrelated_error_rate
            trace.outcome = "failure" if unrelated_failure else "success"
            trace.final_output = (
                "Assigned tickets." if not unrelated_failure else "Assignment failed (unrelated)."
            )

        trace.grader_results = {"no_progress_loop": looping, "state_changed": not looping}
        return trace


@dataclass
class UnrelatedBotTaskScenario:
    """A totally unrelated bot task (a static slash-command reply, no
    ticket-triage tool calls at all) with no relationship to the tool
    loop. Used as the regression suite's negative control (spec section
    14.1.C): any patch to the tool-disambiguation path must leave this
    untouched."""

    base_failure_rate: float = 0.05

    def apply_intervention(self, spec: InterventionSpec) -> dict:
        return {}

    def run_episode(self, cfg: dict, rng: random.Random) -> Trace:
        trace = Trace(agent_version="unrelated", environment="demo_g_sim")
        trace.initial_input = "/help"
        trace.add_step(
            type=StepType.TOOL_CALL,
            tool_name="slash_command_lookup",
            tool_args={"command": "help"},
            observation="help_text",
            side_effect_class=SideEffectClass.READ_ONLY,
        )
        failure = rng.random() < self.base_failure_rate
        trace.outcome = "failure" if failure else "success"
        trace.final_output = "Sent help text." if not failure else "Failed to send help text."
        return trace
