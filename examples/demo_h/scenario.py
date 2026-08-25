"""Demo H scenario: a repair that clears the regression gate but only
masks its root cause.

Reproduces a synthetic incident class distinct from Demo A/B/C/D/E: a
connection-pool-exhaustion race in a health-check worker. On roughly one
check in three, independent of what is being checked, the pool is briefly
exhausted and the health check hard-fails with a ``PoolExhaustedError``.
The suspected root cause (a leaked connection under concurrent
initialization) is NOT confirmed or fixed here. The only known remedy is
retrying the check after clearing whatever stale pool-lease state carried
over from the failed attempt -- that retry usually passes, using the SAME
repair-ladder rung Demo A, Demo C, and Demo E already use --
``clear_stale_retry_state`` -- WITHOUT any change to the planner or
repair-ladder code.

Unlike Demo A/C/E, this scenario explicitly tags the incident's failing
step's ``provenance`` with ``masks_root_cause=True``: an independent,
free-form signal (spec section 21.2) that says the clean, regression-gate-
passing repair the pipeline is about to pick is a mitigation, not a fix --
the leaked-connection race under concurrent initialization is still there,
merely papered over by clearing pool-lease state before each retry. This
is exactly the signal :func:`agentdoctor.mitigation.classify` looks for,
making Demo H the first caller of that classifier (t-009).

Like Demo A, Demo B, Demo C, and Demo E, this is a synthetic, seeded Monte
Carlo world rather than a replay of a recorded cassette: it exists to be a
"planted root cause" benchmark (spec section 21.1) that ``diagnose()`` and
``verify()`` can be run against end-to-end without any external API
dependency or real connection pool.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.trace.schema import SideEffectClass, StepType, Trace

_POOL_EXHAUSTED_ERROR = (
    "PoolExhaustedError: no connections available after 200ms "
    "(suspected leaked connection under concurrent initialization; "
    "root cause not confirmed)"
)


@dataclass
class WorldConfig:
    backend: str = "health-checker"
    pool_race_probability: float = 0.33
    clear_stale_retry_state: bool = False
    retry_after_clear_failure_rate: float = 0.03
    unrelated_error_rate: float = 0.02


@dataclass
class PoolExhaustionRaceScenario:
    """A leaked-connection race under concurrent initialization exhausts
    the connection pool -> the health check hard-errors with
    ``PoolExhaustedError``, on roughly 1/3 of checks, independent of what
    is being checked. Clearing stale pool-lease state before retrying
    usually clears the failure but does not touch the leaked-connection
    race itself -- a mitigation, not a fix."""

    worker_id: str = "healthcheck-worker-1"
    pool_race_probability: float = 0.33
    unrelated_error_rate: float = 0.02

    def _base_config(self) -> WorldConfig:
        return WorldConfig(
            pool_race_probability=self.pool_race_probability,
            unrelated_error_rate=self.unrelated_error_rate,
        )

    def apply_intervention(self, spec: InterventionSpec) -> WorldConfig:
        cfg = self._base_config()
        if spec.retry_clear_stale_observation is not None:
            # Scenario-specific interpretation: this intervention means
            # "clear stale pool-lease state and retry the health check",
            # not "clear stale retry/session state" (Demo C) or "refetch
            # and rebase" (Demo E). The planner and repair-ladder code are
            # unaware of this distinction -- they only ever see the same
            # `clear_stale_retry_state` name/spec.
            cfg.clear_stale_retry_state = spec.retry_clear_stale_observation
        # Model swap, tool-latency normalization, retrieval mode, and
        # config-layer routing all target failure classes that have no
        # bearing on a connection-pool race, so they are intentionally
        # left unwired here.
        return cfg

    def run_episode(self, cfg: WorldConfig, rng: random.Random) -> Trace:
        trace = Trace(agent_version=cfg.backend, environment="demo_h_sim")
        trace.initial_input = f"health check on {self.worker_id} (content-independent)"
        trace.reproducibility_metadata = {"backend": cfg.backend, "worker_id": self.worker_id}

        race = rng.random() < cfg.pool_race_probability

        if race:
            trace.add_step(
                type=StepType.TOOL_CALL,
                tool_name="run_health_check",
                tool_args={"worker_id": self.worker_id},
                latency_ms=200.0,
                error=_POOL_EXHAUSTED_ERROR,
                side_effect_class=SideEffectClass.READ_ONLY,
                provenance={
                    "pool_race": True,
                    "masks_root_cause": True,
                    "reason": "clearing stale pool-lease state before retry hides the "
                    "leaked-connection race under concurrent initialization instead "
                    "of fixing it",
                },
            )
            if cfg.clear_stale_retry_state:
                retry_failed = rng.random() < cfg.retry_after_clear_failure_rate
                trace.add_step(
                    type=StepType.TOOL_CALL,
                    tool_name="run_health_check",
                    tool_args={"worker_id": self.worker_id},
                    latency_ms=430.0,
                    retry_count=1,
                    observation=None if retry_failed else "healthy",
                    error=_POOL_EXHAUSTED_ERROR if retry_failed else None,
                    side_effect_class=SideEffectClass.READ_ONLY,
                    provenance={"stale_pool_lease_cleared": True},
                )
                trace.outcome = "failure" if retry_failed else "success"
                trace.final_output = (
                    "Health check failed: pool exhausted" if retry_failed else "healthy"
                )
            else:
                trace.outcome = "failure"
                trace.final_output = "Health check failed: pool exhausted"
        else:
            trace.add_step(
                type=StepType.TOOL_CALL,
                tool_name="run_health_check",
                tool_args={"worker_id": self.worker_id},
                latency_ms=430.0,
                observation="healthy",
                side_effect_class=SideEffectClass.READ_ONLY,
            )
            unrelated_failure = rng.random() < cfg.unrelated_error_rate
            trace.outcome = "failure" if unrelated_failure else "success"
            trace.final_output = (
                "healthy" if not unrelated_failure else "Health check failed (unrelated flake)."
            )

        trace.grader_results = {"pool_race": race, "pool_exhausted": race}
        return trace


@dataclass
class UnrelatedMetricsScrapeScenario:
    """A totally unrelated task (a metrics-scrape, no connection pool or
    health-check step at all) with no relationship to the pool race. Used
    as the regression suite's negative control (spec section 14.1.C): any
    patch to the health-check retry path must leave this untouched."""

    base_failure_rate: float = 0.05

    def apply_intervention(self, spec: InterventionSpec) -> dict:
        return {}

    def run_episode(self, cfg: dict, rng: random.Random) -> Trace:
        trace = Trace(agent_version="unrelated", environment="demo_h_sim")
        trace.initial_input = "scrape metrics endpoint"
        trace.add_step(
            type=StepType.TOOL_CALL,
            tool_name="scrape_metrics",
            tool_args={"target": "prometheus"},
            observation="scraped",
            side_effect_class=SideEffectClass.READ_ONLY,
        )
        failure = rng.random() < self.base_failure_rate
        trace.outcome = "failure" if failure else "success"
        trace.final_output = "Scraped metrics." if not failure else "Failed to scrape metrics."
        return trace
