"""Demo B scenario (spec sections 2.1 and 23): 'two mechanisms stacking'.

A cron-scheduled task fails three days running with the production error
``CLI backend claude-cli cannot enforce runtime toolsAllow``. The root
cause is two independently-reasonable mechanisms compounding:

  (1) the cron scheduler creates an ISOLATED ``agentTurn`` task and
      force-attaches whatever ``toolsAllow`` allowlist the parent session
      had onto it, even though the child task never asked for one;
  (2) the ``claude-cli`` backend hard-errors the instant it detects ANY
      ``toolsAllow`` on a turn, regardless of whether the allowlist is
      actually meaningful for that turn.

Neither mechanism is a bug on its own; they only fail when stacked. The
fix does not touch either mechanism directly -- it reroutes around the
execution path that triggers both: pointing ``sessionTarget`` at ``main``
(so nothing force-attaches an allowlist) and the payload at
``systemEvent`` (a path the claude-cli backend never capability-checks).

Like Demo A, this is a synthetic, seeded Monte Carlo world rather than a
replay of a recorded cassette: it exists to be a second "planted root
cause" benchmark (spec section 21.1) that ``diagnose()`` and ``verify()``
can be run against end-to-end without any external API dependency.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.trace.schema import SideEffectClass, StepType, Trace


@dataclass
class WorldConfig:
    backend: str = "claude-cli"
    session_target: str = "isolated"
    payload_type: str = "agentTurn"
    tools_allow: list[str] = field(default_factory=lambda: ["Read", "Grep", "Bash"])
    job_name: str = "daily_cleanup_job"
    unrelated_error_rate: float = 0.03


@dataclass
class CronCapabilityConflictScenario:
    """cron dispatch -> isolated agentTurn force-attaches an inherited
    toolsAllow allowlist -> claude-cli backend hard-errors the moment it
    sees any toolsAllow -> the cron job fails, three days running."""

    job_name: str = "daily_cleanup_job"
    unrelated_error_rate: float = 0.03

    def _base_config(self) -> WorldConfig:
        return WorldConfig(job_name=self.job_name, unrelated_error_rate=self.unrelated_error_rate)

    def apply_intervention(self, spec: InterventionSpec) -> WorldConfig:
        cfg = self._base_config()
        overrides = spec.config_overrides
        if "session_target" in overrides:
            cfg.session_target = overrides["session_target"]
        if "payload_type" in overrides:
            cfg.payload_type = overrides["payload_type"]
        # Tool latency, retry-state, retrieval, and model-swap interventions
        # target different failure classes entirely and have no bearing on
        # whether the scheduler force-attaches toolsAllow onto an isolated
        # agentTurn task, so they are intentionally left unwired here.
        return cfg

    def run_episode(self, cfg: WorldConfig, rng: random.Random) -> Trace:
        trace = Trace(agent_version=cfg.backend, environment="demo_b_sim")
        trace.initial_input = f"cron: run {cfg.job_name} on schedule"
        trace.reproducibility_metadata = {
            "session_target": cfg.session_target,
            "payload_type": cfg.payload_type,
            "backend": cfg.backend,
        }

        force_attaches_allowlist = cfg.session_target == "isolated"
        attached_allowlist = cfg.tools_allow if force_attaches_allowlist else []
        trace.add_step(
            type=StepType.TOOL_CALL,
            tool_name="cron_dispatch",
            tool_args={"session_target": cfg.session_target, "payload_type": cfg.payload_type},
            observation=(
                f"created {cfg.payload_type} task (session_target={cfg.session_target}); "
                f"toolsAllow={attached_allowlist}"
            ),
            side_effect_class=SideEffectClass.READ_ONLY,
        )

        capability_conflict = force_attaches_allowlist and cfg.payload_type == "agentTurn"

        if capability_conflict:
            trace.add_step(
                type=StepType.TOOL_CALL,
                tool_name="backend_dispatch",
                tool_args={"backend": cfg.backend, "toolsAllow": cfg.tools_allow},
                error=f"CLI backend {cfg.backend} cannot enforce runtime toolsAllow",
                side_effect_class=SideEffectClass.READ_ONLY,
                provenance={
                    "capability_conflict": True,
                    "conflicting_layers": [
                        f"session_target={cfg.session_target} force-attaches toolsAllow onto the task",
                        f"backend={cfg.backend} hard-errors the instant it detects any toolsAllow",
                    ],
                },
            )
            trace.outcome = "failure"
            trace.final_output = (
                f"{cfg.job_name} failed: {cfg.backend} cannot enforce runtime toolsAllow"
            )
        else:
            trace.add_step(
                type=StepType.TOOL_CALL,
                tool_name="backend_dispatch",
                tool_args={"backend": cfg.backend, "payload_type": cfg.payload_type},
                observation="dispatched with no toolsAllow attached; backend accepted the turn",
                side_effect_class=SideEffectClass.READ_ONLY,
            )
            unrelated_failure = rng.random() < cfg.unrelated_error_rate
            trace.outcome = "failure" if unrelated_failure else "success"
            trace.final_output = (
                f"{cfg.job_name} completed." if not unrelated_failure else f"{cfg.job_name} failed: unrelated error."
            )

        trace.grader_results = {"capability_conflict": capability_conflict}
        return trace


@dataclass
class UnrelatedCronScenario:
    """A totally unrelated cron job (log rotation) with no relationship to
    the toolsAllow/backend conflict. Used as the regression suite's
    negative control (spec section 14.1.C): any patch to the cron dispatch
    config must leave this untouched."""

    base_failure_rate: float = 0.05

    def apply_intervention(self, spec: InterventionSpec) -> dict:
        return {}

    def run_episode(self, cfg: dict, rng: random.Random) -> Trace:
        trace = Trace(agent_version="unrelated", environment="demo_b_sim")
        trace.initial_input = "cron: rotate logs"
        trace.add_step(
            type=StepType.TOOL_CALL,
            tool_name="log_rotate",
            tool_args={"path": "/var/log/app"},
            observation="rotated",
            side_effect_class=SideEffectClass.READ_ONLY,
        )
        failure = rng.random() < self.base_failure_rate
        trace.outcome = "failure" if failure else "success"
        trace.final_output = "Rotated logs." if not failure else "Log rotation failed."
        return trace
