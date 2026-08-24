# BOARD — agent-doctor / EPIC-001 (demo_b)

Baseline: **29 passed** is the floor. It may only rise, never fall. QA verifies
the number in a real `.venv` created by the worktree hook — a green produced by
system python does not count.

Chain is serial: **t-000 → t-001 → t-002**, all on one branch stack, ending in a
single open PR. No parallelism (single dependency chain).

Design notes that shaped the split:
- demo_a has NO cassette/fixture files; its trace is generated in-process from a
  seeded RNG. demo_b reuses the same self-contained synthetic approach — no data
  files, no API key, no network.
- The rule planner (V0) does not currently propose a "config-layer / backend
  capability conflict" hypothesis category. t-001 ADDS one new planner rule
  (additive only; the existing rules and behavior are untouched). `planner/` is
  not on the do-not-touch list (that list is demo_a, trace/, replay/,
  attribution/). Approved by the CEO/owner.

| Task  | Owner     | Depends | Branch          | Status      |
|-------|-----------|---------|-----------------|-------------|
| t-000 | developer | none    | openclaw/t-000  | DONE |
| t-001 | developer | t-000   | openclaw/t-001  | DONE |
| t-002 | developer | t-001   | openclaw/t-002  | DONE |

---

## TASK t-000 — worktree hook + board
OWNER: developer   DEPENDS: none   BRANCH: openclaw/t-000
OBJECTIVE: Install `.openclaw/worktree-setup.sh` (from repo-hooks source) and this
board, so every new managed worktree auto-creates its venv, installs deps, and
proves the 29-test baseline green before a worker starts.
DELIVERABLES:
- `.openclaw/worktree-setup.sh` (executable bit tracked)
- `docs/board/BOARD.md` (this file)
ACCEPTANCE:
- Both files committed on openclaw/t-000; hook has the executable bit in git.
- The hook selects a Python >=3.10 interpreter and, when run inside a fresh
  managed worktree, builds the venv and prints `29 passed`.
- Auto-trigger on worktree creation activates once t-000 lands on main (the
  source checkout must carry the hook on its current branch for OpenClaw to run
  it automatically); until merge, the hook is verified by running it manually in
  a fresh worktree.
VERIFY (QA): create a new managed worktree off openclaw/t-000, run
`bash .openclaw/worktree-setup.sh` inside it, and observe the venv build + `29 passed`.
STATUS: DONE. reviewer APPROVED, qa PASS — hook builds `.venv` with Python >=3.10
and prints `29 passed` in a fresh managed worktree.

## TASK t-001 — demo_b scenario, five stages, SAFE_TO_REVIEW
OWNER: developer   DEPENDS: t-000   BRANCH: openclaw/t-001 (base openclaw/t-000)
OBJECTIVE: Reproduce, as a fully self-contained synthetic scenario, the real
failure: a cron isolated `agentTurn` task force-injects an inherited `toolsAllow`
allowlist, while the `claude-cli` backend hard-errors on ANY `toolsAllow`
(`CLI backend claude-cli cannot enforce runtime toolsAllow`). Build
`examples/demo_b/` (mirroring demo_a's structure: `__init__.py`, `scenario.py`,
`run_demo.py`) that drives all five stages Observe → Intervene → Attribute →
Repair → Verify and prints `SAFE_TO_REVIEW`.
DELIVERABLES:
- `examples/demo_b/__init__.py`, `examples/demo_b/scenario.py`,
  `examples/demo_b/run_demo.py`
- ONE new additive rule in `src/agentdoctor/planner/rule_planner.py` proposing a
  "config-layer / backend-capability conflict" hypothesis category, plus the
  matching Repair Ladder entry in `src/agentdoctor/repair/engine.py` if required
  for the repair to be selectable. Existing rules/behavior unchanged.
- The fix modeled by the winning hypothesis mirrors the real fix: switch
  sessionTarget isolated→main and payload agentTurn→systemEvent to bypass the
  toolsAllow-injecting path.
CONSTRAINTS: no new third-party deps; no data/cassette files; do NOT change the
behavior of demo_a, trace/, replay/, attribution/.
ACCEPTANCE:
- `python -m examples.demo_b.run_demo` runs all five stages and prints
  `SAFE_TO_REVIEW`.
- Among the planner's competing hypotheses, the "config-layer / backend
  capability conflict" category is correctly proposed and selected.
- Existing 29 tests still pass.
VERIFY (QA): in a hook-provisioned worktree, `python -m examples.demo_b.run_demo`
→ SAFE_TO_REVIEW; `pytest -q` → still ≥29 passed.
STATUS: READY_FOR_REVIEW. `./.venv/bin/python -m examples.demo_b.run_demo` prints
`DECISION: SAFE_TO_REVIEW`; the `config_layer_capability_conflict` hypothesis is
top-ranked (effect +0.98, 95% CI excludes 0) and selected as the repair, while
the other hypotheses (latency/retry/model-swap) show effect 0.00 (inconclusive).
`./.venv/bin/python -m pytest -q` → `29 passed`.
DONE. reviewer APPROVED, qa PASS.

## TASK t-002 — tests + docs + README
OWNER: developer   DEPENDS: t-001   BRANCH: openclaw/t-002 (base openclaw/t-001)
OBJECTIVE: Cover demo_b with tests and document it.
DELIVERABLES:
- `tests/test_demo_b.py` covering scenario construction, end-to-end
  SAFE_TO_REVIEW determination, and that the config-conflict hypothesis is
  selected.
- `docs/demo_b.md` describing which real failure it reproduces, the root cause
  (two stacked mechanisms), and the fix.
- README: add `examples/demo_b/` to the package layout; update the Status section.
ACCEPTANCE:
- Test count rises from 29 (new cases green); the original 29 still pass.
- README/docs match the implementation.
VERIFY (QA): `pytest -q` → ≥30 passed including test_demo_b, in a hook-provisioned
worktree with real command output.
STATUS: READY_FOR_REVIEW. `./.venv/bin/python -m pytest -q` → `33 passed` (29
original + 4 new in `tests/test_demo_b.py`, covering scenario construction, the
end-to-end SAFE_TO_REVIEW pipeline, and `config_layer_capability_conflict`
being top-ranked and selected). `./.venv/bin/python -m examples.demo_b.run_demo`
still ends `DECISION: SAFE_TO_REVIEW`, unchanged. Added `docs/demo_b.md` and
updated README package layout + Status. No files under `src/`, `examples/`,
`trace/`, `replay/`, or `attribution/` were touched.
DONE. reviewer APPROVED, qa PASS.

## Process / discipline
- One task = one worktree = one branch (lowercase names).
- developer READY_FOR_REVIEW → reviewer APPROVED → qa PASS (with real command
  output) before a task is done. "developer says it works" is not done.
- Max 3 review rounds, then escalate the disagreement.
- No merge, no push to main. Terminus is a single open PR.

---

# BOARD — agent-doctor / EPIC-002 (demo_c)

Baseline: **33 passed** is the floor (29 from EPIC-001 + 4 from
`tests/test_demo_b.py`). It may only rise, never fall.

Chain is serial: **t-003 → t-004**, continuing the EPIC-001 stack
(t-000 → t-001 → t-002 → t-003 → t-004), one branch each, ending in the same
single open PR. No parallelism (single dependency chain).

Note for reviewers: the `openclaw/t-003` worktree was provisioned from `main`
(which is still at the pre-EPIC-001 commit), not from `openclaw/t-002` where
demo_b, the worktree hook, and this board actually live. t-003 fast-forward
merged `openclaw/t-002` into itself before starting (`git merge --ff-only
openclaw/t-002`) so the prerequisite code/tooling would exist; no history was
rewritten and no unrelated files were touched.

Design notes that shaped the split:
- demo_c models the real, unconfirmed-root-cause incident: `codesFlow_bot`
  intermittently returns no reply because `claude-cli` exits within a few
  hundred ms with `outBytes=0`, on ~1/3 of turns, independent of message
  content. It reuses demo_a/demo_b's self-contained synthetic-RNG approach —
  no data files, no API key, no network.
- Reuse-first: the existing rule planner (V0) already proposes a
  `clear_stale_retry_state` hypothesis whenever a trace shows a retry OR an
  error/timeout signal (see `rule_planner.py`'s `has_retry or
  has_error_or_timeout or slow_tools` gate). Shaping the demo_c incident trace
  to carry a `step.error` on the failed `claude_cli_invoke` call was enough to
  trigger it — **no planner or repair-engine change was needed**; both stay
  byte-for-byte as EPIC-001 left them.
- This is honest framing, not a root-cause claim: the pipeline selects the
  existing `clear_stale_retry_state` repair-ladder rung (risk rank 4, "agent
  policy / retry / state patch") as the best AVAILABLE mitigation. docs (t-004)
  must describe it as a mitigation with unconfirmed root cause.

| Task  | Owner     | Depends | Branch          | Status      |
|-------|-----------|---------|-----------------|-------------|
| t-003 | developer | t-002   | openclaw/t-003  | DONE |
| t-004 | developer | t-003   | openclaw/t-004  | DONE |

---

## TASK t-003 — demo_c scenario, five stages, SAFE_TO_REVIEW
OWNER: developer   DEPENDS: t-002   BRANCH: openclaw/t-003 (base openclaw/t-002)
OBJECTIVE: Reproduce, as a fully self-contained synthetic scenario, the real
`codesFlow_bot` intermittent empty-output incident (probabilistic, ~1/3 of
turns, content-independent) and drive all five stages Observe → Intervene →
Attribute → Repair → Verify so the pipeline selects the existing
`clear_stale_retry_state` repair-ladder rung and ends `SAFE_TO_REVIEW`.
DELIVERABLES:
- `examples/demo_c/__init__.py`, `examples/demo_c/scenario.py`,
  `examples/demo_c/run_demo.py` (mirrors demo_b's structure and CLI:
  `python -m examples.demo_c.run_demo`).
- No planner or repair-engine changes — the existing `clear_stale_retry_state`
  rule and ladder rung were reused as-is (see design notes above).
- This BOARD.md EPIC-002 section.
CONSTRAINTS: no new third-party deps; no data/cassette files; do NOT change the
behavior of demo_a, demo_b, trace/, replay/, attribution/.
ACCEPTANCE:
- `python -m examples.demo_c.run_demo` runs all five stages and prints
  `DECISION: SAFE_TO_REVIEW`, with `clear_stale_retry_state` selected.
- Baseline failure rate is ~1/3 (probabilistic, content-independent); the
  selected intervention drives it toward ~0; deterministic under the demo's
  fixed seed.
- Existing 33 tests still pass (no regression; t-003 adds no tests).
VERIFY (QA): in a hook-provisioned worktree, `python -m examples.demo_c.run_demo`
→ `SAFE_TO_REVIEW`; `pytest -q` → still ≥33 passed; `examples.demo_a` and
`examples.demo_b` run_demo unchanged (still `SAFE_TO_REVIEW`).
STATUS: DONE. `./.venv/bin/python -m examples.demo_c.run_demo`
prints `DECISION: SAFE_TO_REVIEW`; `clear_stale_retry_state` is top-ranked
(effect +0.35, 95% CI [+0.23, +0.47], excludes 0) and selected as the patch,
while `normalize_latency:claude_cli_invoke` and `model_swap` both show effect
+0.00 (inconclusive). Verify suite: original 33.00%→3.00%, variants
30.50%→3.00%, unrelated 5.00%→5.00% (no regression). Diagnose-arm baseline
failure rate 0.37 (75 runs, seed 42); theoretical/verify-suite baseline ~33%,
matching the ~1/3 target. `./.venv/bin/python -m pytest -q` → `33 passed`
(unchanged). Output confirmed byte-identical across two runs (fixed seed).
No planner/repair-engine change was required.
DONE. reviewer APPROVED, qa PASS.

## TASK t-004 — tests + docs for demo_c
OWNER: developer   DEPENDS: t-003   BRANCH: openclaw/t-004 (base openclaw/t-003)
OBJECTIVE: Cover demo_c with tests and document it, mirroring t-002's scope for
demo_b.
DELIVERABLES:
- `tests/test_demo_c.py` covering scenario construction, the end-to-end
  SAFE_TO_REVIEW pipeline, and that `clear_stale_retry_state` is selected.
- `docs/demo_c.md` describing the real incident reproduced, that the root
  cause is unconfirmed (suspected claude-cli resume session-state race), and
  that the selected fix is a retry/state-clear MITIGATION rather than a
  root-cause fix.
- README: add `examples/demo_c/` to the package layout; update the Status
  section.
ACCEPTANCE:
- Test count rises from 33 (new cases green); the original 33 still pass.
- README/docs match the implementation and honestly frame the mitigation vs.
  root-cause distinction.
VERIFY (QA): `pytest -q` → ≥34 passed including test_demo_c, in a
hook-provisioned worktree with real command output.
STATUS: DONE. `./.venv/bin/python -m pytest -q` → `37 passed` (33
original + 4 new in `tests/test_demo_c.py`, covering scenario construction, the
end-to-end SAFE_TO_REVIEW pipeline, and `clear_stale_retry_state` being
top-ranked and selected). `./.venv/bin/python -m examples.demo_c.run_demo`
still ends `DECISION: SAFE_TO_REVIEW`, unchanged, with `clear_stale_retry_state`
top-ranked (effect +0.35, 95% CI excludes 0). `./.venv/bin/python -m
examples.demo_a.run_demo` and `./.venv/bin/python -m examples.demo_b.run_demo`
both still end `DECISION: SAFE_TO_REVIEW` (no regression). Added
`docs/demo_c.md` (honestly framing the suspected-but-unconfirmed root cause
and the mitigation-vs-fix distinction) and updated README package layout +
Status. No files under `src/`, `examples/`, `trace/`, `replay/`, or
`attribution/` were touched.
DONE. reviewer APPROVED, qa PASS.
