# Demo C: the codesFlow_bot intermittent empty-output incident

```bash
python -m examples.demo_c.run_demo
```

Like Demo A and Demo B, this is a fully self-contained synthetic
incident — no API keys, no network access, no cassette/fixture files. The
trace is generated in-process from a seeded RNG (see
`examples/demo_c/scenario.py`).

## The production incident it reproduces

The real incident: the OpenClaw bot `codesFlow_bot` intermittently returns
no reply. On roughly one turn in three — independent of what the user
typed — the `claude-cli` process exits within a few hundred milliseconds
with `outBytes=0`, and the wrapper falls back to `"Something went wrong"`.

The trace shows a single step:

```
claude_cli_invoke(session_id="codesFlow_bot-session-1", resume=True)
  -> error: empty output (outBytes=0): claude-cli exited before responding
```

## Root cause: suspected, not confirmed

**This is the important caveat for this demo.** Unlike Demo A (retry-state
duplication bug) and Demo B (two stacked, well-understood mechanisms), the
root cause here was never fully confirmed. The leading theory is a
`claude-cli` resume session-state race: something about resuming a session
occasionally causes the CLI process to exit almost immediately with no
output, rather than actually failing to produce a response. But this has
not been proven with instrumentation inside `claude-cli` itself — it is
the best explanation the team has, not a verified mechanism.

The only thing that is empirically known is: retrying the turn after
clearing whatever stale resume/session state carried over from the failed
attempt usually succeeds. That observation is what this demo's pipeline
picks up on.

## The fix is a mitigation, not a root-cause fix

Running `diagnose()` against the incident, the rule planner proposes its
existing `clear_stale_retry_state` hypothesis (the same repair-ladder rung
Demo A's stale-retry-merge bug uses) alongside two others (latency
normalization, model swap). No planner or repair-engine change was needed
for this: the planner already proposes `clear_stale_retry_state` whenever
a trace shows a retry or an error/timeout signal, and shaping the failing
step to carry `step.error` was enough to trigger it.

`clear_stale_retry_state` comes out on top with a confident effect
(~+0.35, 95% CI excludes 0); the other two hypotheses are inconclusive
(effect ~0.00), because neither latency nor the model is actually
implicated in this failure.

**Be explicit about what this means:** the pipeline is selecting the best
*available* repair off the ladder, not asserting that it has found and
fixed the underlying race. Clearing stale retry state before a retry does
reduce the observed failure rate substantially in this simulation (as it
does in production), but it does so by working around a symptom
(a corrupted resume attempt) rather than by fixing whatever in
`claude-cli`'s session-resume path causes the empty-output exit in the
first place. If the real root cause is a race condition, this mitigation
may not fully eliminate the failure mode under different timing
conditions — it only handles the failure pattern this demo models
(stale retry state after a resume-race).

## What the demo shows end to end

Running `python -m examples.demo_c.run_demo` walks through all five
stages:

1. **Observe** — replays the failing incident trace (a single
   `claude_cli_invoke(resume=True)` step with the empty-output error).
2. **Intervene / Attribute** — `diagnose()` runs counterfactual replays for
   `clear_stale_retry_state`, latency normalization, and model swap, and
   ranks them by causal effect on failure rate with a bootstrap 95%
   confidence interval. `clear_stale_retry_state` comes out on top
   (~+0.35, CI excludes 0); the other two are inconclusive (~0.00).
3. **Repair** — `best_repair()` selects `clear_stale_retry_state` off the
   Repair Ladder as the best available, confidently positive hypothesis —
   explicitly a mitigation, given the unconfirmed root cause above.
4. **Verify** — the patch is checked against the original incident, a
   structurally similar variant (a different session with a slightly
   different race probability), and an unrelated regression suite
   (`UnrelatedBotTaskScenario`, a static slash-command reply with no
   `claude-cli` invocation at all). The original and variant suites'
   failure rates drop from ~30-33% to ~3% while the unrelated suite is
   untouched (~5% -> ~5%), producing a `SAFE_TO_REVIEW` decision.

See `examples/demo_c/scenario.py` for `IntermittentEmptyOutputScenario`
(the failing incident) and `UnrelatedBotTaskScenario` (the regression
control), and `tests/test_demo_c.py` for automated coverage of all of the
above.
