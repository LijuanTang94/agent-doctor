"""Demo F scenario: an UNPROPAGATED TOOL ERROR incident.

Reproduces a synthetic incident class distinct from Demo A/B/C/D/E: a tool
call to ``fetch_shipment_status`` hard-errors (the fulfillment API times
out), but the agent's response loop does not check the step's ``error``
field before answering -- it proceeds anyway, falling back to a stale,
previously-cached observation, and confidently reports that stale status to
the user as if it were the answer to THIS request. The tool error is never
propagated to the user or to the caller; the agent just produces a wrong
``final_output``, on roughly one turn in three, independent of which
shipment was asked about.

The only known remedy is to make the agent's response loop actually check
for a tool-call error before answering: on error, retry the tool call
instead of silently falling back to a stale observation (and only answer
once a fresh, error-free observation exists). This scenario reuses the SAME
repair-ladder rung Demo A, Demo C, and Demo E already use --
``clear_stale_retry_state`` -- WITHOUT any change to the planner or
repair-ladder code. The only new semantics live here, in
``IgnoredToolErrorScenario.apply_intervention``, which interprets the
existing generic ``InterventionSpec.retry_clear_stale_observation`` field as
"halt on tool error and retry instead of answering from a stale
observation", rather than "clear stale retry/session state" (Demo C's
interpretation) or "refetch + rebase onto the true tip" (Demo E's
interpretation).

Like Demo A, Demo B, Demo C, and Demo E, this is a synthetic, seeded Monte
Carlo world rather than a replay of a recorded cassette: it exists to be
another "planted root cause" benchmark (spec section 21.1) that
``diagnose()`` and ``verify()`` can be run against end-to-end without any
external API dependency.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.trace.schema import SideEffectClass, StepType, Trace

_TOOL_ERROR = (
    "ToolExecutionError: fetch_shipment_status timed out after 3000ms "
    "(upstream fulfillment API unavailable)"
)


@dataclass
class WorldConfig:
    backend: str = "tool-agent"
    tool_error_probability: float = 0.34
    halt_on_tool_error: bool = False
    retry_after_halt_failure_rate: float = 0.03
    unrelated_error_rate: float = 0.02


@dataclass
class IgnoredToolErrorScenario:
    """``fetch_shipment_status`` hard-errors on roughly 1/3 of requests,
    independent of which shipment was asked about. The agent's response
    loop does not check the step's ``error`` field: it proceeds anyway,
    answering from a stale, previously-cached observation instead of
    halting or retrying, and the tool error never propagates to the
    user."""

    request_id: str = "req-shipment-9821"
    tool_error_probability: float = 0.34
    unrelated_error_rate: float = 0.02

    def _base_config(self) -> WorldConfig:
        return WorldConfig(
            tool_error_probability=self.tool_error_probability,
            unrelated_error_rate=self.unrelated_error_rate,
        )

    def apply_intervention(self, spec: InterventionSpec) -> WorldConfig:
        cfg = self._base_config()
        if spec.retry_clear_stale_observation is not None:
            # Scenario-specific interpretation: this intervention means
            # "halt on tool error and retry instead of silently answering
            # from a stale observation", not "clear stale retry/session
            # state" (Demo C) or "refetch + rebase onto the true tip"
            # (Demo E). The planner and repair-ladder code are unaware of
            # this distinction -- they only ever see the same
            # `clear_stale_retry_state` name/spec.
            cfg.halt_on_tool_error = spec.retry_clear_stale_observation
        # Model swap, tool-latency normalization, retrieval mode, and
        # config-layer routing all target failure classes that have no
        # bearing on an ignored tool error, so they are intentionally left
        # unwired here.
        return cfg

    def run_episode(self, cfg: WorldConfig, rng: random.Random) -> Trace:
        trace = Trace(agent_version=cfg.backend, environment="demo_f_sim")
        trace.initial_input = f"user asks for status of {self.request_id} (content-independent)"
        trace.reproducibility_metadata = {"backend": cfg.backend, "request_id": self.request_id}

        tool_errored = rng.random() < cfg.tool_error_probability

        if tool_errored:
            trace.add_step(
                type=StepType.TOOL_CALL,
                tool_name="fetch_shipment_status",
                tool_args={"request_id": self.request_id},
                latency_ms=140.0,
                error=_TOOL_ERROR,
                side_effect_class=SideEffectClass.READ_ONLY,
                provenance={"tool_error": True},
            )
            if cfg.halt_on_tool_error:
                retry_failed = rng.random() < cfg.retry_after_halt_failure_rate
                trace.add_step(
                    type=StepType.TOOL_CALL,
                    tool_name="fetch_shipment_status",
                    tool_args={"request_id": self.request_id},
                    latency_ms=310.0,
                    retry_count=1,
                    observation=None if retry_failed else "shipment_status=delivered",
                    error=_TOOL_ERROR if retry_failed else None,
                    side_effect_class=SideEffectClass.READ_ONLY,
                    provenance={"error_propagated": True},
                )
                trace.outcome = "failure" if retry_failed else "success"
                trace.final_output = (
                    "I could not retrieve your shipment status right now."
                    if retry_failed
                    else "Your shipment has been delivered."
                )
            else:
                # BUG: the tool call errored, but the agent ignores
                # `step.error` and proceeds anyway, answering from a stale
                # observation cached before this request instead of halting
                # or retrying. The answer looks confident and well-formed;
                # it is simply wrong for this request.
                trace.add_step(
                    type=StepType.MODEL_DECISION,
                    action="answer_from_stale_observation",
                    observation="shipment_status=in_transit (stale, cached before this request)",
                    side_effect_class=SideEffectClass.READ_ONLY,
                    provenance={"ignored_tool_error": True},
                )
                trace.outcome = "failure"
                trace.final_output = "Your shipment is in transit."
        else:
            trace.add_step(
                type=StepType.TOOL_CALL,
                tool_name="fetch_shipment_status",
                tool_args={"request_id": self.request_id},
                latency_ms=310.0,
                observation="shipment_status=delivered",
                side_effect_class=SideEffectClass.READ_ONLY,
            )
            unrelated_failure = rng.random() < cfg.unrelated_error_rate
            trace.outcome = "failure" if unrelated_failure else "success"
            trace.final_output = (
                "Your shipment has been delivered."
                if not unrelated_failure
                else "Your shipment status is unavailable (unrelated failure)."
            )

        trace.grader_results = {"tool_error": tool_errored, "error_ignored": tool_errored}
        return trace


@dataclass
class UnrelatedFaqScenario:
    """A totally unrelated bot task (a static FAQ lookup, no shipment tool
    call at all) with no relationship to the ignored tool error. Used as
    the regression suite's negative control (spec section 14.1.C): any
    patch to the shipment-status tool-error path must leave this
    untouched."""

    base_failure_rate: float = 0.05

    def apply_intervention(self, spec: InterventionSpec) -> dict:
        return {}

    def run_episode(self, cfg: dict, rng: random.Random) -> Trace:
        trace = Trace(agent_version="unrelated", environment="demo_f_sim")
        trace.initial_input = "what are your return hours?"
        trace.add_step(
            type=StepType.TOOL_CALL,
            tool_name="faq_lookup",
            tool_args={"topic": "return_hours"},
            observation="9am-6pm daily",
            side_effect_class=SideEffectClass.READ_ONLY,
        )
        failure = rng.random() < self.base_failure_rate
        trace.outcome = "failure" if failure else "success"
        trace.final_output = "9am-6pm daily." if not failure else "Failed to answer FAQ."
        return trace
