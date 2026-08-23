"""Demo A scenario (spec sections 2.1 and 23): 'the model wasn't the problem'.

A refund agent's ``search_orders`` tool occasionally spikes in latency past
its timeout. The retry that follows appends the timed-out call's stale,
partial observation onto the context instead of discarding it (the actual
bug). The planner then sees a duplicated "order confirmed" signal and,
absent a better model catching the anomaly, issues the refund twice.

Swapping the decision model only barely helps (a better model is somewhat
more likely to notice the duplicate and ask for confirmation instead of
double-refunding). Fixing the serving latency, or fixing the retry/state
merge directly, removes the bug at its source.

This is a synthetic, seeded Monte Carlo world rather than a replay of a
recorded cassette: it exists to be a "planted root cause" benchmark (spec
section 21.1) that ``diagnose()`` and ``verify()`` can be run against
end-to-end without any external API dependency.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.trace.schema import SideEffectClass, StepType, Trace

#: how often each model variant notices a duplicated observation and asks
#: for confirmation instead of blindly acting on it twice.
CATCH_DUPLICATE_RATE = {"model_a": 0.05, "model_b": 0.20}


@dataclass
class WorldConfig:
    model_variant: str = "model_a"
    order_id: str = "A-1042"
    base_latency_ms: float = 120.0
    spike_latency_ms: float = 3000.0
    spike_probability: float = 0.42
    timeout_ms: float = 800.0
    retry_clear_stale_observation: bool = False
    unrelated_error_rate: float = 0.04


@dataclass
class RefundAgentScenario:
    """search_orders(latency spike) -> timeout -> retry -> [bug: duplicate
    observation] -> refund_order called once or twice."""

    order_id: str = "A-1042"
    spike_probability: float = 0.42
    unrelated_error_rate: float = 0.04

    def _base_config(self) -> WorldConfig:
        return WorldConfig(
            order_id=self.order_id,
            spike_probability=self.spike_probability,
            unrelated_error_rate=self.unrelated_error_rate,
        )

    def apply_intervention(self, spec: InterventionSpec) -> WorldConfig:
        cfg = self._base_config()
        if spec.model_override:
            cfg.model_variant = spec.model_override
        if "search_orders" in spec.tool_latency_ms:
            # "normalize latency": pin latency low and remove spikes entirely.
            cfg.spike_probability = 0.0
            cfg.base_latency_ms = spec.tool_latency_ms["search_orders"]
        if spec.retry_clear_stale_observation is not None:
            cfg.retry_clear_stale_observation = spec.retry_clear_stale_observation
        return cfg

    def run_episode(self, cfg: WorldConfig, rng: random.Random) -> Trace:
        trace = Trace(agent_version=cfg.model_variant, environment="demo_a_sim")
        trace.initial_input = f"Please refund my order #{cfg.order_id}, it never arrived."

        observations: list[str] = []
        latency = cfg.spike_latency_ms if rng.random() < cfg.spike_probability else cfg.base_latency_ms
        timed_out = latency > cfg.timeout_ms

        if timed_out:
            trace.add_step(
                type=StepType.TOOL_CALL,
                tool_name="search_orders",
                tool_args={"order_id": cfg.order_id},
                latency_ms=latency,
                error="timeout",
                side_effect_class=SideEffectClass.READ_ONLY,
            )
            if not cfg.retry_clear_stale_observation:
                # The bug: the timed-out call's partial observation is not
                # discarded before the retry merges its own observation in.
                observations.append("order_confirmed(partial, stale)")
            observations.append("order_confirmed")
            trace.add_step(
                type=StepType.TOOL_CALL,
                tool_name="search_orders",
                tool_args={"order_id": cfg.order_id},
                latency_ms=cfg.base_latency_ms,
                retry_count=1,
                observation=observations[-1],
                side_effect_class=SideEffectClass.READ_ONLY,
            )
        else:
            observations.append("order_confirmed")
            trace.add_step(
                type=StepType.TOOL_CALL,
                tool_name="search_orders",
                tool_args={"order_id": cfg.order_id},
                latency_ms=latency,
                observation=observations[-1],
                side_effect_class=SideEffectClass.READ_ONLY,
            )

        duplicate_seen = observations.count("order_confirmed") >= 1 and len(observations) >= 2

        catch_rate = CATCH_DUPLICATE_RATE.get(cfg.model_variant, 0.05)
        n_refunds = 2 if (duplicate_seen and rng.random() >= catch_rate) else 1

        trace.add_step(
            type=StepType.MODEL_DECISION,
            message_history=[{"role": "tool", "content": o} for o in observations],
            model_config_snapshot={"model": cfg.model_variant},
            action="refund_order" if n_refunds == 1 else "refund_order,refund_order",
        )
        for _ in range(n_refunds):
            trace.add_step(
                type=StepType.TOOL_CALL,
                tool_name="refund_order",
                tool_args={"order_id": cfg.order_id},
                observation="refund_issued",
                side_effect_class=SideEffectClass.EXTERNAL_PAYMENT,
            )

        unrelated_failure = rng.random() < cfg.unrelated_error_rate
        outcome = "failure" if (n_refunds > 1 or unrelated_failure) else "success"
        trace.outcome = outcome
        trace.final_output = (
            "Refund processed." if outcome == "success" else "Unauthorized duplicate refund issued."
        )
        trace.grader_results = {"duplicate_seen": duplicate_seen, "n_refunds": n_refunds}
        return trace


@dataclass
class UnrelatedTaskScenario:
    """An FAQ lookup agent with no relationship to the refund bug at all.
    Used as the regression suite's negative control (spec section 14.1.C):
    any patch to the refund agent must leave this untouched."""

    base_failure_rate: float = 0.06

    def apply_intervention(self, spec: InterventionSpec) -> dict:
        return {}

    def run_episode(self, cfg: dict, rng: random.Random) -> Trace:
        trace = Trace(agent_version="unrelated", environment="demo_a_sim")
        trace.initial_input = "What is your return policy?"
        trace.add_step(
            type=StepType.TOOL_CALL,
            tool_name="faq_lookup",
            tool_args={"topic": "returns"},
            observation="policy_text",
            side_effect_class=SideEffectClass.READ_ONLY,
        )
        failure = rng.random() < self.base_failure_rate
        trace.outcome = "failure" if failure else "success"
        trace.final_output = "Answered from FAQ." if not failure else "Gave an incorrect policy answer."
        return trace
