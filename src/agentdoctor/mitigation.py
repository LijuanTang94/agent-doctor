"""Mitigation-only annotation: is this SAFE_TO_REVIEW repair a real fix, or
does it just paper over the symptom?

:class:`~agentdoctor.regression.runner.VerificationReport` already proves a
patch clears the regression gate (the original incident improves, variants
don't overfit, unrelated suites don't regress) before ``decision`` can ever
be ``SAFE_TO_REVIEW``. That gate says nothing about *why* the patch works,
though -- a patch can silence the failing assertion (e.g. widen a retry
timeout, swallow an error, retry until it happens to pass) without touching
whatever upstream defect produced the failure in the first place. This
module turns that observation into an explicit terminal annotation layered
on top of an already-clean verdict, so a human reviewing a "SAFE_TO_REVIEW"
patch can see it may only be masking the root cause.

Deliberately a pure function with no I/O, mirroring
:mod:`agentdoctor.environment`: it only reads the trace's existing free-form
``Step.provenance`` dict (the same mechanism ``rule_planner.py`` already
reads via ``s.provenance.get("capability_conflict")``) plus the already-computed
:class:`~agentdoctor.regression.runner.VerificationReport`. It does not add a
branch to ``VerificationReport.decision`` and is not called from anywhere in
the existing pipeline.
"""

from __future__ import annotations

from agentdoctor.regression.runner import VerificationReport
from agentdoctor.repair.engine import Patch
from agentdoctor.trace.schema import Trace

MITIGATION_ONLY = "MITIGATION_ONLY"


def classify(
    trace: Trace, patch: Patch | None, verification: VerificationReport
) -> str | None:
    """Return ``MITIGATION_ONLY`` iff there is a real, regression-clean
    repair (``patch`` is not ``None`` and ``verification.decision ==
    "SAFE_TO_REVIEW"``) AND a step's ``provenance`` independently reports
    that the repair masks the root cause rather than fixing it. Either
    signal alone is not enough: no patch (or no clean verdict) means there
    is nothing yet worth caveating, and no masking signal means there is no
    evidence the clean repair is anything but a real fix.
    """
    if patch is None or verification.decision != "SAFE_TO_REVIEW":
        return None

    masks_root_cause = any(
        step.provenance.get("masks_root_cause") for step in trace.steps
    )
    if not masks_root_cause:
        return None

    return MITIGATION_ONLY
