"""CLI (spec section 24.1).

MVP scope note: ``diagnose``/``replay``/``repair``/``verify`` need a
*Scenario* to run counterfactual experiments against, not just a saved
trace — a real deployment would resolve that from the trace's
``agent_version``/``environment`` metadata against a registered adapter.
For MVP the registry below only knows about the bundled Demo A scenario;
``--scenario`` is explicit rather than silently falling back to a network
call to a real agent.
"""

from __future__ import annotations

import json
import os
import sys

import click

from agentdoctor.diagnose import diagnose as diagnose_fn
from agentdoctor.interventions.base import InterventionSpec
from agentdoctor.replay.runtime import run as replay_run
from agentdoctor.trace.schema import Trace


def _load_scenario_registry() -> dict:
    # The bundled demo scenarios live in examples/, at the repo root rather
    # than inside the installed package. A console-script entry point does
    # not put the current working directory on sys.path the way `python -m`
    # does, so add it explicitly -- this only ever resolves anything when
    # invoked from a checkout of this repo.
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    try:
        from examples.demo_a.scenario import RefundAgentScenario, UnrelatedTaskScenario
    except ImportError:
        return {}
    return {
        "demo_a": lambda: RefundAgentScenario(),
        "demo_a_variant": lambda: RefundAgentScenario(order_id="B-2091", spike_probability=0.38),
        "demo_a_unrelated": lambda: UnrelatedTaskScenario(),
    }


def _resolve_scenario(name: str):
    registry = _load_scenario_registry()
    if name not in registry:
        available = ", ".join(sorted(registry)) or "(none registered)"
        raise click.ClickException(f"unknown scenario {name!r}; available: {available}")
    return registry[name]()


@click.group()
def main() -> None:
    """agentdoctor: root-cause your AI agent with experiments, not guesses."""


@main.command()
@click.argument("trace_path", type=click.Path(exists=True))
def inspect(trace_path: str) -> None:
    """Pretty-print a saved Canonical Trace."""
    trace = Trace.from_jsonl(trace_path)
    click.echo(f"trace_id: {trace.trace_id}")
    click.echo(f"outcome:  {trace.outcome}")
    click.echo(f"input:    {trace.initial_input}")
    for step in trace.steps:
        click.echo(
            f"  [{step.index}] {step.type.value} tool={step.tool_name} "
            f"latency={step.latency_ms:.0f}ms retry={step.retry_count} error={step.error}"
        )
    click.echo(f"final_output: {trace.final_output}")


@main.command()
@click.option("--scenario", required=True, help="registered scenario name, e.g. demo_a")
@click.option("--n", default=20, show_default=True, help="number of counterfactual runs")
@click.option("--model", default=None, help="model override, e.g. model_b")
@click.option("--normalize-latency-ms", type=float, default=None)
@click.option("--clear-stale-retry/--no-clear-stale-retry", default=None)
@click.option("--seed", default=0, show_default=True)
def replay(
    scenario: str,
    n: int,
    model: str | None,
    normalize_latency_ms: float | None,
    clear_stale_retry: bool | None,
    seed: int,
) -> None:
    """Run N counterfactual replays under an intervention and report the
    resulting failure rate."""
    scenario_obj = _resolve_scenario(scenario)
    spec = InterventionSpec(model_override=model, retry_clear_stale_observation=clear_stale_retry)
    if normalize_latency_ms is not None:
        spec.tool_latency_ms["search_orders"] = normalize_latency_ms

    result = replay_run(scenario_obj, n=n, interventions=spec, seed=seed)
    click.echo(f"intervention: {spec.describe()}")
    click.echo(f"n={result.n} failure_rate={result.failure_rate:.2%}")


@main.command()
@click.argument("trace_path", type=click.Path(exists=True))
@click.option("--scenario", required=True, help="registered scenario name, e.g. demo_a")
@click.option("--budget", default=40, show_default=True, help="total counterfactual runs to spend")
@click.option("--seed", default=0, show_default=True)
def diagnose(trace_path: str, scenario: str, budget: int, seed: int) -> None:
    """Plan hypotheses, run counterfactual experiments, rank causal effects."""
    trace = Trace.from_jsonl(trace_path)
    scenario_obj = _resolve_scenario(scenario)
    report = diagnose_fn(trace, scenario_obj, budget=budget, seed=seed)

    click.echo(f"baseline failure_rate={report.baseline.failure_rate:.2%} (n={report.runs_per_arm})")
    click.echo(f"total_runs={report.total_runs}")
    for effect in report.effects:
        flag = " (inconclusive)" if effect.inconclusive else ""
        click.echo(
            f"  {effect.label:28s} effect={effect.point_estimate:+.2f} "
            f"CI=[{effect.ci_low:+.2f},{effect.ci_high:+.2f}]{flag}"
        )

    patch = report.best_repair()
    if patch is None:
        click.echo("root cause: inconclusive; no confident repair found")
        sys.exit(1)
    click.echo(f"root cause: {patch.hypothesis_name} ({patch.ladder_rung})")


@main.command()
@click.argument("trace_path", type=click.Path(exists=True))
@click.option("--scenario", required=True)
@click.option("--budget", default=40, show_default=True)
@click.option("--seed", default=0, show_default=True)
def repair(trace_path: str, scenario: str, budget: int, seed: int) -> None:
    """Diagnose a trace and print the suggested minimal patch."""
    trace = Trace.from_jsonl(trace_path)
    scenario_obj = _resolve_scenario(scenario)
    report = diagnose_fn(trace, scenario_obj, budget=budget, seed=seed)
    patch = report.best_repair()
    if patch is None:
        raise click.ClickException("no confident repair found")
    click.echo(
        json.dumps(
            {
                "hypothesis": patch.hypothesis_name,
                "ladder_rung": patch.ladder_rung,
                "risk_rank": patch.risk_rank,
                "description": patch.description,
                "effect": patch.evidence.point_estimate,
                "ci": [patch.evidence.ci_low, patch.evidence.ci_high],
            },
            indent=2,
        )
    )


@main.command()
@click.option("--scenario", required=True, help="original-incident scenario")
@click.option("--variant-scenario", required=True)
@click.option("--unrelated-scenario", required=True)
@click.option("--budget", default=40, show_default=True)
@click.option("--n", default=100, show_default=True, help="runs per regression suite")
@click.option("--seed", default=0, show_default=True)
@click.argument("trace_path", type=click.Path(exists=True))
def verify(
    trace_path: str,
    scenario: str,
    variant_scenario: str,
    unrelated_scenario: str,
    budget: int,
    n: int,
    seed: int,
) -> None:
    """Diagnose, then verify the suggested patch against original + variants
    + unrelated regression suites. Exits non-zero unless SAFE_TO_REVIEW."""
    from agentdoctor.regression.runner import verify as verify_fn

    trace = Trace.from_jsonl(trace_path)
    scenario_obj = _resolve_scenario(scenario)
    report = diagnose_fn(trace, scenario_obj, budget=budget, seed=seed)
    patch = report.best_repair()
    if patch is None:
        raise click.ClickException("no confident repair found; nothing to verify")

    suites = {
        "original": scenario_obj,
        "variants": _resolve_scenario(variant_scenario),
        "unrelated": _resolve_scenario(unrelated_scenario),
    }
    verification = verify_fn(suites, patch, n=n, seed=seed)
    for suite in verification.suites:
        click.echo(
            f"{suite.name:10s} {suite.before_failure_rate:.2%} -> "
            f"{suite.after_failure_rate:.2%} (delta {suite.delta:+.2%})"
        )
    click.echo(f"decision: {verification.decision}")
    sys.exit(0 if verification.decision == "SAFE_TO_REVIEW" else 1)


if __name__ == "__main__":
    main()
