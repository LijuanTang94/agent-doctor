"""Top-level ``verify()`` (spec section 24.2 API draft): thin re-export of
:func:`agentdoctor.regression.runner.verify` so callers can do
``from agentdoctor import verify`` without reaching into the submodule.
"""

from agentdoctor.regression.runner import VerificationReport, verify

__all__ = ["verify", "VerificationReport"]
