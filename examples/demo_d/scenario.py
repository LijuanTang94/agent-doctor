"""Demo D scenario (environment vs code attribution): 'sandbox permission
denied'.

Reproduces a class of incident distinct from Demo A/B/C: the agent's tool
call is refused outright by the *sandbox* it is running in -- a read-only
filesystem policy blocking a write -- not by anything the agent's prompt,
model, tools, retrieval, or retry policy chose to do. There is no code-level
lever that could ever make an OS-level permission denial succeed, so unlike
demo_a/b/c, ``apply_intervention`` here deliberately does not wire *any*
``InterventionSpec`` field to the failure: every hypothesis the planner
proposes is, correctly, a dead end.

Like Demo A/B/C, this is a synthetic, self-contained scenario (no cassette,
no API keys, no network) so ``diagnose()`` and
``agentdoctor.environment.classify()`` can be run against it end-to-end.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.trace.schema import SideEffectClass, StepType, Trace

SANDBOX_PERMISSION_ERROR = (
    "Permission denied: write access to '/var/agent/workspace/output.log' "
    "blocked by sandbox policy (read-only file system)"
)


@dataclass
class SandboxPermissionDeniedScenario:
    """The agent's ``write_file`` tool call is denied purely by the
    sandbox's read-only filesystem policy. This always fails, independent
    of message content, seed, or any supported intervention layer -- there
    is no model/prompt/tool-latency/retry/retrieval/config knob that
    controls an OS-level permission decision made outside the agent
    process."""

    session_id: str = "agent-doctor-demo-d-session-1"

    def apply_intervention(self, spec: InterventionSpec) -> dict:
        # Deliberately ignores `spec`: no InterventionSpec layer has any
        # bearing on a sandbox-level permission denial, so none is wired.
        return {}

    def run_episode(self, cfg: dict, rng: random.Random) -> Trace:
        trace = Trace(agent_version="agent-doctor-demo", environment="demo_d_sim")
        trace.initial_input = f"agent turn on session {self.session_id}: write run output to disk"
        trace.reproducibility_metadata = {"session_id": self.session_id}

        trace.add_step(
            type=StepType.TOOL_CALL,
            tool_name="write_file",
            tool_args={"path": "/var/agent/workspace/output.log"},
            latency_ms=12.0,
            error=SANDBOX_PERMISSION_ERROR,
            side_effect_class=SideEffectClass.READ_ONLY,
            provenance={"environment_blocked": True, "reason": "sandbox_permission_denied"},
        )
        trace.outcome = "failure"
        trace.final_output = "Something went wrong"
        trace.grader_results = {"environment_blocked": True}
        return trace
