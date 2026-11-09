# Dupaco Current-Truth Assistant

## What this system does

Answers credit-union member questions ("What's the 6-month certificate APY?", "How much is a
lost debit card?", "What were your mortgage rates in May 2026?") using **only** five dated
snapshots of the credit union's own website. Snapshots disagree with each other, and old and
stale versions of the same pages coexist. The system:

- **ingest(snapshot)** — reads every download (oldest first), stores each fact it finds as a
  typed, append-only claim (product, metric, tier, value, effective date, source page, snapshot),
  deduplicating the same claim repeated across pages.
- **answer(question, as_of=None)** — parses the question into a claim key, filters claims to the
  website state as of that date (default: the latest snapshot), adjudicates between conflicting
  copies with a trust stack (tier exact-match → page authority → freshest effective date →
  still-present), and answers with exactly one value, its qualifier, and a source. When the
  website doesn't say, it declines clearly and states no numbers.
- **conflicts()** — reports every place the website contradicts itself on the same fact, which
  value we believe, and why (newer page, authoritative rates page vs. stale promotional page).

A deterministic BM25 fallback covers question wording the rule parser doesn't recognize, routed
through the same adjudication stack. The system is fully offline and deterministic.

## Contract

`solution.py` (in this repo, folder `answers/`) exposes `build()` → object with the three methods
above, shaped exactly as `harness/contract.py` requires. Nothing is renamed.

## Rules we follow (from the assignment)

- Answer **only** from the provided snapshots — no live website calls.
- Every `answer` call finishes within 60 s; ingest finishes within 30 min.
- Graded offline in a clean Python 3.11 environment — this repo needs **no API keys and no
  network** at grading time.
- We do not redistribute the snapshot or eval data; the repo contains code and notes only.
- We never modify `harness/` or `eval/` (grading uses the organizers' own copy).

## Setup

1. Get the participant kit (this repo **is** the kit) — the first eval run unpacks the snapshot zips in
   `snapshots_zip/` into `snapshots/`.
2. Python 3.11 (3.9+ works for local runs):

   ```bash
   python3.11 -m venv .venv && source .venv/bin/activate
   pip install -r answers/requirements.txt
   ```

3. Run the public eval from the repo root:

   ```bash
   python harness/run_eval.py --submission answers --eval eval/public_eval.jsonl
   ```

4. Optional: score conflicts locally against a gold file:

   ```bash
   python harness/run_eval.py --submission answers --eval eval/public_eval.jsonl \
     --conflicts-gold harness/selftest/conflicts_gold.json
   ```

5. Local checks — the same gates CI runs on every push:

   ```bash
   python -m unittest discover -s answers/tests -t answers/tests -v    # unit + component + integration tiers
   python tools/data_leak_guard.py                                     # corpus stays out of git
   python tools/eval_gate.py --report results_ci/selftest/report.json \
        --baseline answers/tests/baseline_selftest.json                # eval regression gate
   ```

   The full public eval needs the local corpus (which is never committed): run it after every
   story and record the result in `PLAN.md` §7 (the Eval Ledger).

## Status

Current score, per-increment progress, and the delivery plan live in **[PLAN.md](PLAN.md)**
(tracer-bullet delivery: T0 → T6, with the Eval Ledger as the scoreboard of record). Agent
work rules live in **[AGENTS.md](AGENTS.md)**.
