"""Demo E scenario: a STALE-REFERENCE incident.

Reproduces a synthetic incident class distinct from Demo A/B/C: a worker
branches its task off a LOCALLY-STALE ``main`` (its local remote-tracking
ref lags behind the true tip). The worker's base is therefore missing code
that was already merged upstream, so the build fails with a hard
``ModuleNotFoundError`` for a symbol that exists on the true tip but not on
the worker's stale base.

The only known remedy is to refetch and rebase the worker branch onto the
TRUE tip of ``origin/main`` before retrying the build -- that retry then
passes because the missing symbol is now present. This scenario reuses the
SAME repair-ladder rung Demo A and Demo C already use --
``clear_stale_retry_state`` -- WITHOUT any change to the planner or
repair-ladder code. The only new semantics live here, in
``StaleBaseRebaseScenario.apply_intervention``, which interprets that
intervention as "refetch + rebase onto the true tip clears the stale base
state" rather than "clear stale retry/session state" (Demo C's
interpretation) or "clear a stale retry-merge" (Demo A's interpretation).

Like Demo A, Demo B, and Demo C, this is a synthetic, seeded Monte Carlo
world rather than a replay of a recorded cassette: it exists to be a fourth
"planted root cause" benchmark (spec section 21.1) that ``diagnose()`` and
``verify()`` can be run against end-to-end without any external API
dependency or real git repository.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.trace.schema import SideEffectClass, StepType, Trace

_STALE_REF_ERROR = (
    "ModuleNotFoundError: No module named 'agentdoctor.repair.ladder_v2' "
    "(symbol merged to origin/main after this worker branch's fork point; "
    "the worker's local base is stale)"
)


@dataclass
class WorldConfig:
    backend: str = "git-worker"
    stale_base_probability: float = 0.34
    refetch_and_rebase: bool = False
    rebase_retry_failure_rate: float = 0.03
    unrelated_error_rate: float = 0.02


@dataclass
class StaleBaseRebaseScenario:
    """Worker branches off a locally-stale ``main`` -> its base is missing
    already-merged code -> the build hard-errors on a missing symbol/module,
    on roughly 1/3 of task starts, independent of what the task itself
    changes."""

    branch_id: str = "worker/t-777-stale-base"
    stale_base_probability: float = 0.34
    unrelated_error_rate: float = 0.02

    def _base_config(self) -> WorldConfig:
        return WorldConfig(
            stale_base_probability=self.stale_base_probability,
            unrelated_error_rate=self.unrelated_error_rate,
        )

    def apply_intervention(self, spec: InterventionSpec) -> WorldConfig:
        cfg = self._base_config()
        if spec.retry_clear_stale_observation is not None:
            # Scenario-specific interpretation: this intervention means
            # "refetch origin/main and rebase the worker branch onto the
            # true tip", not "clear stale retry/session state" (Demo C) or
            # "clear a stale retry-merge" (Demo A). The planner and
            # repair-ladder code are unaware of this distinction -- they
            # only ever see the same `clear_stale_retry_state` name/spec.
            cfg.refetch_and_rebase = spec.retry_clear_stale_observation
        # Model swap, tool-latency normalization, retrieval mode, and
        # config-layer routing all target failure classes that have no
        # bearing on a stale git base, so they are intentionally left
        # unwired here.
        return cfg

    def run_episode(self, cfg: WorldConfig, rng: random.Random) -> Trace:
        trace = Trace(agent_version=cfg.backend, environment="demo_e_sim")
        trace.initial_input = f"worker build on {self.branch_id} (base=local main)"
        trace.reproducibility_metadata = {"backend": cfg.backend, "branch_id": self.branch_id}

        stale = rng.random() < cfg.stale_base_probability

        if stale:
            trace.add_step(
                type=StepType.TOOL_CALL,
                tool_name="worker_build",
                tool_args={"branch_id": self.branch_id, "base_ref": "main@stale"},
                latency_ms=210.0,
                error=_STALE_REF_ERROR,
                side_effect_class=SideEffectClass.READ_ONLY,
                provenance={"stale_base": True, "missing_symbol": "agentdoctor.repair.ladder_v2"},
            )
            if cfg.refetch_and_rebase:
                rebase_failed = rng.random() < cfg.rebase_retry_failure_rate
                trace.add_step(
                    type=StepType.TOOL_CALL,
                    tool_name="worker_build",
                    tool_args={"branch_id": self.branch_id, "base_ref": "origin/main@true-tip"},
                    latency_ms=640.0,
                    retry_count=1,
                    observation=None if rebase_failed else "build passed",
                    error=_STALE_REF_ERROR if rebase_failed else None,
                    side_effect_class=SideEffectClass.READ_ONLY,
                    provenance={"refetched_and_rebased": True},
                )
                trace.outcome = "failure" if rebase_failed else "success"
                trace.final_output = "Build failed: stale base" if rebase_failed else "build passed"
            else:
                trace.outcome = "failure"
                trace.final_output = "Build failed: stale base"
        else:
            trace.add_step(
                type=StepType.TOOL_CALL,
                tool_name="worker_build",
                tool_args={"branch_id": self.branch_id, "base_ref": "origin/main@true-tip"},
                latency_ms=640.0,
                observation="build passed",
                side_effect_class=SideEffectClass.READ_ONLY,
            )
            unrelated_failure = rng.random() < cfg.unrelated_error_rate
            trace.outcome = "failure" if unrelated_failure else "success"
            trace.final_output = (
                "build passed" if not unrelated_failure else "Build failed (unrelated flake)."
            )

        trace.grader_results = {"stale_base": stale, "missing_symbol": stale}
        return trace


@dataclass
class UnrelatedDeployScenario:
    """A totally unrelated task (a static asset deploy, no git worktree or
    build step at all) with no relationship to stale git bases. Used as the
    regression suite's negative control (spec section 14.1.C): any patch to
    the worker rebase path must leave this untouched."""

    base_failure_rate: float = 0.05

    def apply_intervention(self, spec: InterventionSpec) -> dict:
        return {}

    def run_episode(self, cfg: dict, rng: random.Random) -> Trace:
        trace = Trace(agent_version="unrelated", environment="demo_e_sim")
        trace.initial_input = "deploy static asset bundle"
        trace.add_step(
            type=StepType.TOOL_CALL,
            tool_name="deploy_static_bundle",
            tool_args={"target": "cdn"},
            observation="deployed",
            side_effect_class=SideEffectClass.READ_ONLY,
        )
        failure = rng.random() < self.base_failure_rate
        trace.outcome = "failure" if failure else "success"
        trace.final_output = "Deployed bundle." if not failure else "Failed to deploy bundle."
        return trace
