"""OpenAI-compatible chat/tool-calling recorder adapter (spec section 16.1).

Wraps a ``chat.completions.create``-shaped call so every model decision is
logged onto the active :class:`RecordingRun` as a ``StepType.MODEL_DECISION``
step, including the provenance fields required for replay (model, params).

This module is imported lazily by callers that opt into the ``openai`` extra;
it must not be imported by the core package so the base install stays
dependency-light.
"""

from __future__ import annotations

import time
from typing import Any

from agentdoctor.trace.recorder import RecordingRun
from agentdoctor.trace.schema import StepType


def record_chat_completion(
    run: RecordingRun,
    client: Any,
    *,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> Any:
    """Call ``client.chat.completions.create`` and record the decision step.

    Returns the raw response object so callers can keep using the OpenAI SDK
    as normal.
    """
    start = time.monotonic()
    error: str | None = None
    response: Any = None
    try:
        response = client.chat.completions.create(
            model=model, messages=messages, tools=tools, **kwargs
        )
    except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
        error = repr(exc)
        raise
    finally:
        latency_ms = (time.monotonic() - start) * 1000
        message = None
        tool_name = None
        tool_args: dict[str, Any] = {}
        if response is not None:
            choice = response.choices[0].message
            message = choice.content
            calls = getattr(choice, "tool_calls", None)
            if calls:
                tool_name = calls[0].function.name
                tool_args = {"raw_arguments": calls[0].function.arguments}
        run.step(
            type=StepType.MODEL_DECISION,
            message_history=messages,
            model_config_snapshot={"model": model, **kwargs},
            action=message,
            tool_name=tool_name,
            tool_args=tool_args,
            latency_ms=latency_ms,
            error=error,
            provenance={"model": model},
        )
    return response
