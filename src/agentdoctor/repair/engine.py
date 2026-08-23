"""Repair Engine: minimal, reversible patch selection (spec section 13).

Picks the *lowest-risk* rung on the Repair Ladder that is backed by strong
enough causal evidence, rather than always jumping to the biggest lever
(e.g. swapping models / fine-tuning) available. A hypothesis whose effect
CI straddles zero is never eligible, no matter how attractive its point
estimate looks.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentdoctor.attribution.contrastive import Effect
from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.planner.rule_planner import Hypothesis

#: hypothesis-name-prefix -> (repair ladder rung, risk rank; lower = safer)
REPAIR_LADDER: dict[str, tuple[str, int]] = {
    "clear_stale_retry_state": ("agent policy / retry / state patch", 4),
    "normalize_latency": ("serving / infra config patch", 4),
    "tool_schema_ablation": ("tool description / schema patch", 3),
    "gold_context": ("retrieval configuration patch", 5),
    "config_layer_capability_conflict": ("orchestration / session-routing config patch", 2),
    "model_swap": ("adapter / fine-tune (avoid unless nothing else fits)", 7),
}


@dataclass
class Patch:
    hypothesis_name: str
    ladder_rung: str
    risk_rank: int
    description: str
    spec: InterventionSpec
    evidence: Effect


def best_repair(effects: list[Effect], hypotheses: list[Hypothesis]) -> Patch | None:
    """Choose the safest ladder rung among hypotheses with a confidently
    positive effect (CI excludes zero and favors the intervention)."""
    candidates = [e for e in effects if not e.inconclusive and e.point_estimate > 0]
    if not candidates:
        return None

    by_name = {h.name: h for h in hypotheses}
    ranked = []
    for effect in candidates:
        hyp = by_name.get(effect.label)
        if hyp is None:
            continue
        prefix = hyp.name.split(":")[0]
        rung, risk_rank = REPAIR_LADDER.get(prefix, ("unclassified patch", 8))
        ranked.append((risk_rank, -effect.point_estimate, effect, hyp, rung))

    if not ranked:
        return None

    ranked.sort(key=lambda item: (item[0], item[1]))
    risk_rank, _, effect, hyp, rung = ranked[0]
    return Patch(
        hypothesis_name=hyp.name,
        ladder_rung=rung,
        risk_rank=risk_rank,
        description=hyp.rationale,
        spec=hyp.spec,
        evidence=effect,
    )
