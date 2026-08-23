"""Experiment Planner V0: rule-based hypothesis generation (spec section 12.1).

Looks at surface signals in a failing trace (retries, errors/timeouts,
repeated tool calls, thin retrieval) and proposes a ranked list of
competing hypotheses to test via intervention + replay. V1 (Bayesian
information-gain selection, section 12.2) can reuse the same
:class:`Hypothesis` shape and just re-rank/re-select adaptively as evidence
comes in instead of using fixed priors.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.trace.schema import StepType, Trace


@dataclass
class Hypothesis:
    name: str
    spec: InterventionSpec
    prior: float
    rationale: str


def plan_experiments(trace: Trace) -> list[Hypothesis]:
    steps = trace.steps
    hypotheses: list[Hypothesis] = []

    has_retry = any(s.retry_count > 0 for s in steps)
    has_error_or_timeout = any(s.error for s in steps)
    slow_tools = sorted({s.tool_name for s in steps if s.tool_name and s.latency_ms > 500})
    tool_call_counts = Counter(s.tool_name for s in steps if s.tool_name)
    repeated_tools = [name for name, c in tool_call_counts.items() if c > 1]
    retrieval_steps = [s for s in steps if s.type == StepType.RETRIEVAL]
    thin_retrieval = any(len(s.retrieval_docs) == 0 for s in retrieval_steps)

    if has_retry or has_error_or_timeout or slow_tools:
        for tool in slow_tools or [s.tool_name for s in steps if s.tool_name][:1]:
            hypotheses.append(
                Hypothesis(
                    name=f"normalize_latency:{tool}",
                    spec=InterventionSpec(tool_latency_ms={tool: 50.0}),
                    prior=0.35,
                    rationale=(
                        f"{tool} shows high latency/timeout/retry; test whether "
                        "normalizing serving latency removes the failure"
                    ),
                )
            )
        hypotheses.append(
            Hypothesis(
                name="clear_stale_retry_state",
                spec=InterventionSpec(retry_clear_stale_observation=True),
                prior=0.40,
                rationale=(
                    "retries observed; test whether clearing the stale observation "
                    "before a retry merge removes duplicated context"
                ),
            )
        )

    if repeated_tools:
        hypotheses.append(
            Hypothesis(
                name="tool_schema_ablation",
                spec=InterventionSpec(prompt_overrides={"tool_disambiguation": "<clarified>"}),
                prior=0.20,
                rationale=(
                    f"{repeated_tools} called more than once; test whether clarifying "
                    "tool description/schema reduces repeated/duplicated calls"
                ),
            )
        )

    if thin_retrieval:
        hypotheses.append(
            Hypothesis(
                name="gold_context",
                spec=InterventionSpec(retrieval_mode="gold"),
                prior=0.20,
                rationale="retrieval recall looks abnormal; test a gold-context intervention",
            )
        )

    # Always keep a competing "it's the model" hypothesis in the mix (section
    # 11.2: never test only the favorite explanation).
    hypotheses.append(
        Hypothesis(
            name="model_swap",
            spec=InterventionSpec(model_override="model_b"),
            prior=0.10,
            rationale="competing baseline hypothesis: swap the decision model/policy",
        )
    )

    hypotheses.sort(key=lambda h: h.prior, reverse=True)
    return hypotheses
