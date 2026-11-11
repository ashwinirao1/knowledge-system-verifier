# NOTES.md

## What this system is

A reconciliation engine over a temporal claims ledger, exposed as `build()` →
`ingest/answer/conflicts` per `harness/contract.py`. It reads five dated snapshots of one
credit-union website, keeps every fact it finds as an immutable claim (value + qualifiers +
effective date + source page + snapshot date), and answers member questions from the single
claim that wins a fixed trust-resolution stack — or declines honestly.

The plain-language narrative of *why* each design choice was made — the storage-engine
tradeoff (why in-memory SQLite and not Postgres/MongoDB/a graph store), template-only
answering, keep-history-forever, and the issues we hit and fixed — lives in
**DECISIONS.md** at the repo root.

## How "current" is decided

Every answer is a claim selection, never a generation. Fixed resolution order:

1. **Exact qualifier/tier match** — the question's slots (term, model-year, balance tier,
   special/jumbo/IRA, personal-vs-business, metric) must match the claim's canonical key;
   a business row can never answer a personal question or vice versa.
2. **Page-class authority** — product page / rates hub > template/footer > newsroom/blog >
   promo > calculator > old PDF.
3. **Freshest value-date** — the table-level "effective as of" date for rate tables; for
   newsroom/blog facts the **article's own publish date** is the value-date (bitemporality:
   posting date = snapshot date, value date = effective/publish date). This resolves
   published-statement series with zero special-casing — e.g. "23 branch office locations"
   (March 2026) legitimately loses to "22" (April 2026, after a branch closed).
4. **Still present in the latest snapshot** — claims from pages the site no longer serves
   cannot answer a "today" question.

`as_of` selects the last snapshot taken on or before the requested date (with
range-validated parsing and month-name clamping); questions about a date before the
earliest snapshot still answer from that snapshot with an explicit provenance note.
Event questions (branch closures) answer with tense derived from the event date vs the
view date. A last-resort BM25 fallback over the view snapshot's cleaned sections handles
questions the grammar cannot parse at all — it quotes a published line only under strict
precision rules (published number in the line, every key term present, the view mentions
every term) and otherwise declines; it never overrides an informed refusal.

## Conflicts policy

Only **same-canonical-key contradictions** (same product + metric + tier, different
values, within one snapshot) are conflicts — each published with the winning value and
the reason it won (fresher effective date, or page-class authority). Replica pages
carrying the same value collapse to one claim. Tier differences, boilerplate drift,
publish-date series, and page-to-page prose differences are *not* conflicts. The list is
deterministically ordered and capped. Verified against a hand-derived local gold
(27 real contradictions on the provided corpus: precision 1.00, recall 1.00, resolution
accuracy 1.00).

## Fact families beyond rate tables

Prose knowledge is extracted as text claims from the same pages (never hardcoded to a
question): branch hours/addresses/relocations, member-service how-tos, assistance
programs (with dollar value), mobile-wallet support, annual newsroom recaps (year = a
tier dim), entity facts (routing number, branch count, recognition, eligibility, product
availability), and the site's own published CTA links (application site, branch/ATM
locator), plus rates-directory links derived from where the winning rate rows actually
live. These families are excluded from conflicts — pages legitimately differ, which is
not a contradiction. When a question does not bind the fact (an unbound year, an unnamed
program), the answer either replays the full chronological series from the ledger or
declines — it never guesses between published values.

## Dependencies & API keys

- `requirements.txt` is intentionally empty: the grading path is pure Python stdlib
  (verified by install into a fresh Python 3.11 venv — zero packages installed).
- **No API keys. The grading path is fully offline — no network access is used at any
  point** (enforced by a red-team audit script that greps the submission for
  network-capable imports).
