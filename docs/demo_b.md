# Demo B: the cron / toolsAllow capability conflict

```bash
python -m examples.demo_b.run_demo
```

Like Demo A, this is a fully self-contained synthetic incident — no API
keys, no network access, no cassette/fixture files. The trace is generated
in-process from a seeded RNG (see `examples/demo_b/scenario.py`).

## The production incident it reproduces

A cron-scheduled job (`daily_cleanup_job`) fails repeatedly with:

```
CLI backend claude-cli cannot enforce runtime toolsAllow
```

The trace shows two steps:

1. `cron_dispatch` — the scheduler creates an **isolated** `agentTurn` task
   for the job and force-attaches whatever `toolsAllow` allowlist the
   parent session had (`["Read", "Grep", "Bash"]`), even though the child
   task never asked for one.
2. `backend_dispatch` — the `claude-cli` backend hard-errors the instant it
   detects **any** `toolsAllow` on the turn, regardless of whether the
   allowlist is actually meaningful for that turn, and the job fails.

## Root cause: two mechanisms stacking

Neither mechanism is a bug in isolation:

- Force-attaching an inherited `toolsAllow` to isolated `agentTurn` tasks
  is reasonable in general (it's how capability restrictions are supposed
  to propagate).
- The `claude-cli` backend refusing to run a turn it can't enforce
  `toolsAllow` on is also reasonable (it's a correctness guardrail, not a
  bug).

The failure only appears when both are true at once: `session_target ==
"isolated"` (which force-attaches the allowlist) **and** `payload_type ==
"agentTurn"` (the path the claude-cli backend capability-checks). This is
exactly the "config layer vs. backend capability conflict" hypothesis
category added to the rule planner in `src/agentdoctor/planner/rule_planner.py`
(`config_layer_capability_conflict`), with a matching Repair Ladder entry
in `src/agentdoctor/repair/engine.py`.

## The fix

The fix does not change either mechanism directly — it reroutes around the
execution path that triggers both, by patching the cron dispatch config:

- `sessionTarget`: `isolated` → `main` (nothing force-attaches an
  allowlist onto the main session)
- `payload`: `agentTurn` → `systemEvent` (a payload type the claude-cli
  backend never capability-checks)

In the demo this is modeled by `InterventionSpec(config_overrides={
"session_target": "main", "payload_type": "systemEvent"})`.

## What the demo shows end to end

Running `python -m examples.demo_b.run_demo` walks through all five
stages:

1. **Observe** — replays the failing incident trace (`cron_dispatch` ->
   `backend_dispatch` error).
2. **Intervene / Attribute** — `diagnose()` plans competing hypotheses
   (config-layer conflict, stale retry state, latency normalization, model
   swap), runs counterfactual replays for each, and ranks them by causal
   effect on failure rate with a bootstrap 95% confidence interval.
   `config_layer_capability_conflict` comes out on top with a large,
   confident effect (~+0.98); the others are inconclusive (effect ~0.00).
3. **Repair** — `best_repair()` selects `config_layer_capability_conflict`
   off the Repair Ladder as the lowest-risk hypothesis with a confidently
   positive effect.
4. **Verify** — the patch is checked against the original incident, a
   structurally similar variant (`weekly_backup_job`), and an unrelated
   regression suite (`UnrelatedCronScenario`, a log-rotation job with no
   relationship to the `toolsAllow` conflict). The original and variant
   suites' failure rates drop while the unrelated suite is untouched,
   producing a `SAFE_TO_REVIEW` decision.

See `examples/demo_b/scenario.py` for `CronCapabilityConflictScenario`
(the failing incident) and `UnrelatedCronScenario` (the regression
control), and `tests/test_demo_b.py` for automated coverage of all of the
above.
