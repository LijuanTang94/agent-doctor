# Agent Doctor

Root-cause your AI agent with experiments, not guesses.

Agent Doctor is a debugger for AI agents, built around a five-stage loop:

```
Observe -> Intervene -> Attribute -> Repair -> Verify
```

Instead of asking an LLM to read a trace and guess what went wrong, it
reconstructs a failing run as a controlled experiment: it proposes
competing hypotheses (model, prompt, tool, retrieval, serving/retry,
orchestrator), runs counterfactual replays that change one variable at a
time, and reports a causal effect with a confidence interval for each one.
The best-supported hypothesis becomes a minimal, reversible patch, which is
then verified against the original incident, structurally similar variants,
and an unrelated regression suite before it's called safe to review.

This repo implements the MVP scope described in `docs/product-plan.md`
(sections 16-17 of the original plan): Canonical Trace, Cassette/Sandbox
Replay, an Intervention Engine (model/prompt/tool/serving), a Monte-Carlo
Attribution Engine, a rule-based Experiment Planner (V0), a Repair Ladder,
and a three-suite Regression Runner — wired end to end through **Demo A**,
a fully self-contained synthetic incident ("the model wasn't the problem")
that needs no API keys or network access to run.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Run Demo A

```bash
python -m examples.demo_a.run_demo
```

This reconstructs a refund-agent incident where a `search_orders` latency
spike triggers a timeout/retry, a retry bug duplicates the "order
confirmed" observation, and the agent issues a refund twice. It then:

1. Plans competing hypotheses (serving latency, retry/state, tool schema,
   model swap).
2. Runs counterfactual replays for each and estimates the causal effect on
   failure rate, with a bootstrap 95% confidence interval.
3. Picks the safest well-supported repair off the Repair Ladder.
4. Verifies the patch against the original incident, a structurally
   similar variant, and an unrelated FAQ-agent suite, and prints a
   `SAFE_TO_REVIEW` / `REJECT_*` decision.

## CLI

```bash
agentdoctor inspect trace.json
agentdoctor replay --scenario demo_a --n 50 --clear-stale-retry
agentdoctor diagnose trace.json --scenario demo_a --budget 40
agentdoctor repair trace.json --scenario demo_a --budget 40
agentdoctor verify trace.json --scenario demo_a \
    --variant-scenario demo_a_variant --unrelated-scenario demo_a_unrelated
```

`--scenario` looks up a registered `Scenario` (see
`examples/demo_a/scenario.py`) capable of re-running counterfactual
episodes; a saved trace on its own is not enough to run interventions
against, since replay needs somewhere to actually execute the
counterfactual world. Wiring a real agent up as a `Scenario` (cassette
replay against a recorded production trace, or a sandboxed live rerun) is
the integration point for using this against a real system.

## Package layout

```
src/agentdoctor/
  trace/          Canonical Trace schema + recorder + OpenAI adapter
  replay/         replay runtime, cassette/fidelity, tool virtualization policy
  interventions/  typed do-spec + fluent builder API
  attribution/    Monte Carlo effect estimation + bootstrap CI
  planner/        rule-based (V0) experiment planner
  repair/         Repair Ladder + patch selection
  regression/     original/variants/unrelated verification gate
  cli.py          `agentdoctor` command line
examples/demo_a/  the synthetic incident scenario + end-to-end script
examples/demo_b/  the cron/toolsAllow capability-conflict scenario + end-to-end script
examples/demo_c/  the codesFlow_bot intermittent empty-output scenario + end-to-end script
tests/            pytest suite covering every module above
```

## What's explicitly out of scope for this MVP

Multi-agent coordination, computer-use/browser replay, closed-model weight
edits, a hosted dashboard, fully automatic causal graph discovery, and live
replay of destructive/payment tools in production. See the product plan's
section 16.2 for the full list.

## Status

MVP skeleton with three working, tested end-to-end paths: Demo A (a
model/retry-state incident), Demo B (a cron/toolsAllow config-layer vs.
backend capability conflict — see `docs/demo_b.md`), and Demo C (the
`codesFlow_bot` intermittent empty-output incident, an unconfirmed-root-cause
case whose selected fix is a retry/state-clear mitigation rather than a
proven fix — see `docs/demo_c.md`). The Bayesian experiment planner (V1),
production trace ingestion, managed sandbox fleet, and historical incident
intelligence described in the product plan's commercial layer (section 18.2)
are not implemented here.
