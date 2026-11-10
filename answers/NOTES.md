# NOTES.md (stub — finalized at S6.2)

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

## How "current" is decided (being built at S0.2/S0.3 — final text due S6.2)

Fixed order: exact qualifier/tier match → page-class authority (product page / rates hub >
template/footer > newsroom/blog > promo > calculator > old PDF) → freshest table-level
"effective as of" date → still present in the latest snapshot. `as_of` selects the last
snapshot taken on or before the requested date.

## Conflicts policy (being built at S0.4/S5)

Only same-canonical-key contradictions (same product+metric+tier with different values),
deduplicated across replica pages, with the winning value and the reason it won. Tier
differences and boilerplate drift are not conflicts.

## Fact families beyond rate tables (S1.4/S1.5)

Prose knowledge is extracted as text claims from the same pages (never hardcoded to a
question): branch hours/addresses/relocations, member-service how-tos, assistance
programs (with dollar value), mobile-wallet support, annual newsroom recaps (year = a
tier dim), and the site's own published CTA links (application site, branch/ATM locator),
plus rates-directory links derived from where the winning rate rows actually live. These
families are excluded from conflicts — pages legitimately differ, which is not a
contradiction. When a question does not bind the fact (an unbound year, an unnamed
program), the answer either replays the full chronological series from the ledger or
declines — it never guesses between published values.

## Dependencies & API keys

- `requirements.txt` is intentionally empty: the grading path is pure Python stdlib.
- **No API keys. The grading path is fully offline — no network access is used at any point.**
