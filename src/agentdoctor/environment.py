"""Environment vs Code Attribution: is this incident even fixable in code?

Some incidents are not caused by anything the agent's prompt, model, tools,
retrieval, or retry policy could ever control -- e.g. a sandbox denying a
filesystem write outright. :mod:`agentdoctor.replay.runtime` and
:mod:`agentdoctor.attribution.contrastive` already surface this correctly as
a purely negative result (every :class:`~agentdoctor.attribution.contrastive.Effect`
comes back ~0 and inconclusive, because no :class:`InterventionSpec` layer was
ever wired to the failure). This module turns that negative result plus the
raw environment signal on the failing step into an explicit terminal
decision, so the pipeline can say "this is an environment limitation" instead
of silently reporting "no confident repair found" and leaving a human to
guess why.

This is deliberately a pure function with no I/O: it only reads the trace's
existing free-form ``Step.provenance`` dict (the same mechanism
``rule_planner.py`` already reads via ``s.provenance.get("capability_conflict")``)
and the effects already computed by :func:`agentdoctor.diagnose.diagnose`.
"""

from __future__ import annotations

from typing import Iterable

from agentdoctor.attribution.contrastive import Effect
from agentdoctor.trace.schema import Trace

ENVIRONMENT_BLOCKED = "ENVIRONMENT_BLOCKED"


def classify(trace: Trace, effects: Iterable[Effect]) -> str | None:
    """Return ``ENVIRONMENT_BLOCKED`` iff a step reports an environment-level
    denial AND no tested hypothesis shows a confident, positive code-level
    fix. A confident positive effect always wins over the raw signal: it is
    direct causal evidence that *some* code-level lever does control the
    outcome, which contradicts "this can't be fixed in code".
    """
    effects = list(effects)

    has_environment_signal = any(
        step.provenance.get("environment_blocked") for step in trace.steps
    )
    if not has_environment_signal:
        return None

    has_confident_code_fix = any(
        not effect.inconclusive and effect.point_estimate > 0 for effect in effects
    )
    if has_confident_code_fix:
        return None

    return ENVIRONMENT_BLOCKED
