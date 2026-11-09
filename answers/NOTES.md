# NOTES.md (stub — finalized at S6.2)

## What this system is

A reconciliation engine over a temporal claims ledger, exposed as `build()` →
`ingest/answer/conflicts` per `harness/contract.py`. It reads five dated snapshots of one
credit-union website, keeps every fact it finds as an immutable claim (value + qualifiers +
effective date + source page + snapshot date), and answers member questions from the single
claim that wins a fixed trust-resolution stack — or declines honestly.

## How "current" is decided (being built at S0.2/S0.3 — final text due S6.2)

Fixed order: exact qualifier/tier match → page-class authority (product page / rates hub >
template/footer > newsroom/blog > promo > calculator > old PDF) → freshest table-level
"effective as of" date → still present in the latest snapshot. `as_of` selects the last
snapshot taken on or before the requested date.

## Conflicts policy (being built at S0.4/S5)

Only same-canonical-key contradictions (same product+metric+tier with different values),
deduplicated across replica pages, with the winning value and the reason it won. Tier
differences and boilerplate drift are not conflicts.

## Dependencies & API keys

- `requirements.txt` is intentionally empty: the grading path is pure Python stdlib.
- **No API keys. The grading path is fully offline — no network access is used at any point.**
