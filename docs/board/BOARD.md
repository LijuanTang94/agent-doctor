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
| t-000 | developer | none    | openclaw/t-000  | IN PROGRESS |
| t-001 | developer | t-000   | openclaw/t-001  | TODO        |
| t-002 | developer | t-001   | openclaw/t-002  | TODO        |

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

## Process / discipline
- One task = one worktree = one branch (lowercase names).
- developer READY_FOR_REVIEW → reviewer APPROVED → qa PASS (with real command
  output) before a task is done. "developer says it works" is not done.
- Max 3 review rounds, then escalate the disagreement.
- No merge, no push to main. Terminus is a single open PR.
