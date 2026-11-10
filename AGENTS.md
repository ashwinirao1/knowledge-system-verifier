# AGENTS.md — Operating Ruleset for Every Agent Working in This Repo

> Applies to the lead agent **and** every subagent spawned here. Subagents start with fresh
> context, so any subagent prompt must include: *"Read AGENTS.md at the repo root before acting."*
> The task source of truth is **PLAN.md** (tracer-bullet increments T0–T6). Project overview:
> **README.md** (assignment) and **SETUP.md** (setup/how-to-run).

---

## 1. What this repo is (60-second orientation)

Hackathon submission for "Build a knowledge system that knows what's true *now*" — five snapshots
of one credit-union website that contradict each other; we publish `answers/solution.py` exposing
`build()` → `ingest(snapshot)` / `answer(question, as_of=None)` / `conflicts()`, shaped exactly per
`harness/contract.py`. **Nothing is renamed.**

Architecture (decided, see PLAN.md section 9 decision log): an **append-only temporal claims ledger**
(website-as-settlement-file, reconciliation-engine mindset) + a **trust-resolution stack** +
a **deterministic BM25 fallback** through the same stack, with **template-only answer synthesis**.
No LLM, no network, in the grading path.

## 2. Absolute rules (assignment section 8 + event-specific)

**Never modify or commit to:** `harness/`, `eval/`, `starter/`, `README.md`,
`Knowledge-Hackathon-Assignment.pdf`. Grading uses the organizers' own copy of the harness — edits
there do nothing and look like cheating. `starter/` is reference-only.

| Rule | Detail |
|---|---|
| No live calls | Answer **only** from the provided snapshots. No agent or subagent ever fetches the credit union's website. |
| Latency | Every `answer` call ≤ 60 s; whole ingest ≤ 30 min. |
| Offline grading | The grading path must not need network, API keys, or heavy dependencies. |
| No data redistribution | The snapshots are a real credit union's site, shared for this event only. Before the repo is ever pushed to GitHub, `.gitignore` must exclude `snapshots/`, `snapshots_zip/`, `results/`, caches. The credit-union page data and derived corpora never get pushed anywhere. |
| No hardcoding | No question→answer lookup tables; organizers grade reworded hidden questions. |
| Contract fidelity | Don't copy `harness/contract.py` into `answers/` and rename dataclasses; import it like `starter/solution.py` does so the scorer's `to_answer()` accepts our objects. |

## 3. Engineering rules (the R1–R5 quality bar)

Trace every change to one of these; violations are instant-fix red flags:

- **R1 Trap immunity** — the answer synthesizer emits **only the selected claim value(s)**: no
  ranges, no historical context, no "both pages say", no extra numbers in refusal text
  (**refusals are digit-free**, and `confident=False`).
- **R2 Speed** — all answering is index lookups (SQLite dict/BM25). No model calls at answer time.
  Warm the index at the end of the last `ingest`, not on first question.
- **R3 Determinism** — same question re-asked / paraphrased → identical numbers. Canonical number
  formatting; stable ordering; no randomness, no timestamps in answer text.
- **R4 Offline safety** — pure Python (stdlib-first); any dependency must be pure-python, pinned,
  and torch-class is forbidden; no keys needed anywhere.
- **R5 Conflict precision** — conflicts are only **same canonical key + different values** with a
  stated winner + reason. Tier/entity differences and boilerplate drift are NOT conflicts.
  Replicas (same fact on many pages, e.g. the corporate footer) count once.

**Trust-resolution stack (fixed order):** exact qualifier/tier match → page-class authority
(product page ≈ rates hub > template/footer > newsroom/blog > promo > calculator > old PDF) →
freshest table-level effective date → still present in latest snapshot.

**Canonical key = idempotency key:** (product, metric, tier dimensions). Bitemporality everywhere:
snapshot date = posting date; page-declared "effective as of" = value date.

## 4. Workflow: tracer-bullet increments

- Work **only** from PLAN.md stories (T0–T6, section 6). If work isn't a task in a story, either it's
  out of scope or the plan needs a new task — update PLAN.md **first**, then build.
- Every increment must leave the system runnable end-to-end. Do not commit broad restructures
  without a passing public eval.
- **Every push runs the GHA pipeline** (`.github/workflows/ci.yml`): the three test tiers
  (unit / component / integration on committed synthetic data only), ruff, coverage → SonarQube,
  bandit + pip-audit + gitleaks (OWASP: SAST, vulnerable deps, secret scan), the data-leak guard,
  and the eval regression gate. Push = green CI; story done = Eval Ledger row. The full public
  eval runs locally after each story (corpus is local-only) and is recorded by hand.
- **After every story**: run the public eval and append a row to the Eval Ledger (PLAN.md section 7) —
  even if the score dipped; the ledger is honest.
- Standard eval commands (from repo root):

  ```bash
  python harness/run_eval.py --submission answers --eval eval/public_eval.jsonl
  python harness/run_eval.py --submission answers --eval eval/public_eval.jsonl \
      --conflicts-gold harness/selftest/conflicts_gold.json
  ```

- Tests: stdlib `unittest` is fine; one test module per extractor family
  (`answers/tests/test_<family>.py`). Extractor changes always ship with tests.
- Python 3.11 is the grading target (3.9+ must keep working for local kit runs).

## 5. Code & commit hygiene

- Layout: `answers/` (submission — `solution.py`, `requirements.txt`, `NOTES.md`), `answers/tests/`,
  local dev tooling in `tools/` (analysis notebooks/scripts live here, never in `answers/`),
  docs at root.
- Commits: small, message prefix by story id — `S0.2: table parser for certificates`.
- Do not commit: `results/` / `results_ci/`, `.venv/`, `.DS_Store`, unpacked snapshots, snapshot zips, any
  generated ledger DB if it contains page text.
- Keep submission folder lean: graders plug `answers/` straight into their scorer.

## 6. Subagent policy

- **Allowed:** corpus exploration/verification, extractor validation sweeps, building paraphrase
  test fixtures (Story T3.3), building the local conflicts gold (S5.2), page-class auditing.
- **Forbidden for subagents:** modifying anything under harness/eval/starter, touching the contract
  template, pushing branches, running anything networked.
- Every subagent prompt must include: (a) "read AGENTS.md first", (b) the story id + Done-when,
  (c) the exact paths it may write to (e.g. `tools/`, `answers/tests/`), (d) the reminder that the
  snapshots are not to be redistributed.
- The lead agent commits; subagent output is reviewed against section 3 red flags before merge.

## 7. Definition of Done (mirrors PLAN.md section 8)

- Story DoD: task acceptance criteria met, eval row appended, no regressions on previously-passing
  questions, tests added for the touched extractor family.
- Release DoD: PLAN.md section 10 submission checklist fully green (fresh-clone run in clean Python 3.11,
  `NOTES.md` final, no data in repo).

## 8. Talking rules (how agents communicate changes)

- Report scores with category breakdown, not just the final number (`by_category` is in every report).
- Quote the failing question id + trap hit when an item regresses.
- Never overstate readiness: "passes public eval" ≠ "passes hidden eval" (hidden set has real
  paraphrase groups, more as_of/edge cases, a conflicts gold, and likely LLM-judged free-text).
