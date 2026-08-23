"""Demo C scenario (spec sections 2.1 and 23): 'intermittent empty output'.

Reproduces the real production incident (PROJECT.md real case #1):
``codesFlow_bot`` intermittently returns no reply. On roughly one turn in
three -- independent of what the user typed -- the ``claude-cli`` process
exits within a few hundred milliseconds with ``outBytes=0``, and the
wrapper falls back to "Something went wrong".

The suspected root cause (a ``claude-cli`` resume session-state race) is
NOT confirmed. The only known remedy is retrying the turn after clearing
whatever stale resume/session state carried over from the failed attempt
-- that retry usually passes. This is a MITIGATION, not a root-cause fix:
the pipeline is choosing the best AVAILABLE repair (retry / clear stale
retry state), the same repair-ladder rung Demo A's stale-retry-merge bug
uses, not claiming to have fixed the underlying race.

Like Demo A and Demo B, this is a synthetic, seeded Monte Carlo world
rather than a replay of a recorded cassette: it exists to be a third
"planted root cause" benchmark (spec section 21.1) that ``diagnose()``
and ``verify()`` can be run against end-to-end without any external API
dependency.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.trace.schema import SideEffectClass, StepType, Trace

_EMPTY_OUTPUT_ERROR = "empty output (outBytes=0): claude-cli exited before responding"


@dataclass
class WorldConfig:
    backend: str = "claude-cli"
    resume_race_probability: float = 0.32
    clear_stale_retry_state: bool = False
    retry_after_clear_failure_rate: float = 0.03
    unrelated_error_rate: float = 0.02


@dataclass
class IntermittentEmptyOutputScenario:
    """claude-cli resume session-state race -> process exits in a few
    hundred ms with outBytes=0 -> no automatic retry -> the turn fails and
    the wrapper falls back to "Something went wrong", on roughly 1/3 of
    turns, independent of message content."""

    session_id: str = "codesFlow_bot-session-1"
    resume_race_probability: float = 0.32
    unrelated_error_rate: float = 0.02

    def _base_config(self) -> WorldConfig:
        return WorldConfig(
            resume_race_probability=self.resume_race_probability,
            unrelated_error_rate=self.unrelated_error_rate,
        )

    def apply_intervention(self, spec: InterventionSpec) -> WorldConfig:
        cfg = self._base_config()
        if spec.retry_clear_stale_observation is not None:
            cfg.clear_stale_retry_state = spec.retry_clear_stale_observation
        # Model swap, tool-latency normalization, retrieval mode, and
        # config-layer routing all target failure classes that have no
        # bearing on a claude-cli resume-session race, so they are
        # intentionally left unwired here.
        return cfg

    def run_episode(self, cfg: WorldConfig, rng: random.Random) -> Trace:
        trace = Trace(agent_version=cfg.backend, environment="demo_c_sim")
        trace.initial_input = f"user turn on session {self.session_id} (content-independent)"
        trace.reproducibility_metadata = {"backend": cfg.backend, "session_id": self.session_id}

        race = rng.random() < cfg.resume_race_probability

        if race:
            trace.add_step(
                type=StepType.TOOL_CALL,
                tool_name="claude_cli_invoke",
                tool_args={"session_id": self.session_id, "resume": True},
                latency_ms=180.0,
                error=_EMPTY_OUTPUT_ERROR,
                side_effect_class=SideEffectClass.READ_ONLY,
                provenance={"outBytes": 0, "resume_race": True},
            )
            if cfg.clear_stale_retry_state:
                retry_failed = rng.random() < cfg.retry_after_clear_failure_rate
                trace.add_step(
                    type=StepType.TOOL_CALL,
                    tool_name="claude_cli_invoke",
                    tool_args={"session_id": self.session_id, "resume": True},
                    latency_ms=850.0,
                    retry_count=1,
                    observation=None if retry_failed else "response text",
                    error=_EMPTY_OUTPUT_ERROR if retry_failed else None,
                    side_effect_class=SideEffectClass.READ_ONLY,
                    provenance={"stale_retry_state_cleared": True},
                )
                trace.outcome = "failure" if retry_failed else "success"
                trace.final_output = "Something went wrong" if retry_failed else "response text"
            else:
                trace.outcome = "failure"
                trace.final_output = "Something went wrong"
        else:
            trace.add_step(
                type=StepType.TOOL_CALL,
                tool_name="claude_cli_invoke",
                tool_args={"session_id": self.session_id, "resume": True},
                latency_ms=850.0,
                observation="response text",
                side_effect_class=SideEffectClass.READ_ONLY,
            )
            unrelated_failure = rng.random() < cfg.unrelated_error_rate
            trace.outcome = "failure" if unrelated_failure else "success"
            trace.final_output = (
                "response text" if not unrelated_failure else "Something went wrong (unrelated)."
            )

        trace.grader_results = {"resume_race": race, "outBytes_zero": race}
        return trace


@dataclass
class UnrelatedBotTaskScenario:
    """A totally unrelated bot task (a static slash-command reply, no
    claude-cli invocation at all) with no relationship to the resume race.
    Used as the regression suite's negative control (spec section 14.1.C):
    any patch to the claude-cli retry path must leave this untouched."""

    base_failure_rate: float = 0.05

    def apply_intervention(self, spec: InterventionSpec) -> dict:
        return {}

    def run_episode(self, cfg: dict, rng: random.Random) -> Trace:
        trace = Trace(agent_version="unrelated", environment="demo_c_sim")
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
