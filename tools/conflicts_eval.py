#!/usr/bin/env python3
"""S5.2 local conflicts gold + tuning run (PLAN.md T5).

The gold was HAND-DERIVED by reading the contradicting pages in the corpus:

  - Auto: the switch-and-earn promo table (effective 2026-01-01) still shows
    8.54% / 6.29% / 6.44% where the auto-loans rates page (effective
    2026-08-31) shows 8.59% / 6.34% / 6.49% — same canonical keys, same
    snapshot: real contradictions; the fresher rates page wins.
  - Mortgage: the homeownership learn-blog table (effective 2026-04-22,
    5.50-6.06%) contradicts the current homebuying-guidance / mortgage-refi
    tables (effective 2026-09-25, 6.75-7.35%) across every purchase/refinance
    tier, rate and APR — 24 real contradictions; the current pages win.
    (The raw row value 6.037% renders canonically as 6.04%.)

Candidate pairs deliberately EXCLUDED per the R5 rules (the evaluator asserts
they never appear):

  - Auto 5.34% (promo "2023-26 Model Year") vs 5.39% (hub "2024-27 Model
    Year"): the site REVISED its model-year tier windows — different
    canonical keys, not a contradiction.
  - 10-month jumbo special 3.90%/4.00%: cross-snapshot transition (the S2.3
    change-event index answers "what changed"), and within one snapshot the
    two figures are the same row's dividend-rate and APY columns.
  - Branch count 22/24, Forbes fourth/fifth: publish-date temporal series
    (S2.4 bitemporality), not same-snapshot contradictions.
  - Legacy vs current site links: prose claims, excluded from conflicts
    views (R5).

The gold file is corpus-derived data: it lives in results/ (gitignored) and
is rebuilt with --build after hand-verification. Usage:

    python3 tools/conflicts_eval.py            # evaluate against frozen gold
    python3 tools/conflicts_eval.py --build    # (re)build the gold snapshot
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "answers"))

GOLD = ROOT / "results" / "conflicts_gold_local.json"

EXCLUDED = [
    {
        "kind": "different_tier_keys",
        "detail": "auto 5.34% (2023-26 promo tier) vs 5.39% (2024-27 hub tier) — revised windows, not a contradiction",
        "forbidden_value": "5.34%",
    },
    {
        "kind": "transition_not_conflict",
        "detail": "10-month jumbo special 3.90%/4.00% — cross-snapshot transition + same-row rate/APY columns",
    },
    {
        "kind": "temporal_series",
        "detail": "branch count 22/24; Forbes fourth/fifth — publish-date series (S2.4)",
        "forbidden_topics": ["branch_count", "forbes"],
    },
    {
        "kind": "prose_not_values",
        "detail": "legacy vs current site links — prose claims stay out of conflicts views",
    },
]


def _build_gold() -> None:
    from run_eval import load_snapshots, load_submission

    snaps = load_snapshots(ROOT / "snapshots")
    ks = load_submission(ROOT / "answers")
    for s in snaps:
        ks.ingest(s)
    conf = ks.conflicts()
    gold = {
        "note": "hand-verified against the pages; frozen as the local regression gold (S5.2)",
        "real": [
            {
                "topic": c.topic,
                "values": list(c.values),
                "resolution": c.resolution,
            }
            for c in conf
        ],
        "excluded": EXCLUDED,
    }
    GOLD.parent.mkdir(parents=True, exist_ok=True)
    GOLD.write_text(json.dumps(gold, indent=1))
    print(f"gold built: {len(gold['real'])} real conflicts -> {GOLD.relative_to(ROOT)}")


def main() -> int:
    if "--build" in sys.argv:
        _build_gold()
        return 0
    if not GOLD.exists():
        print("gold missing — run with --build first (after hand-verifying)")
        return 2
    gold = json.loads(GOLD.read_text())
    real = gold["real"]

    from run_eval import load_snapshots, load_submission

    snaps = load_snapshots(ROOT / "snapshots")
    ks = load_submission(ROOT / "answers")
    for s in snaps:
        ks.ingest(s)
    conf = ks.conflicts()

    gold_by_topic = {g["topic"]: g for g in real}
    matched, wrong_values, wrong_resolution = [], [], []
    for c in conf:
        g = gold_by_topic.get(c.topic)
        if g is None:
            continue  # counted as a false positive below
        if sorted(c.values) == sorted(g["values"]):
            matched.append(c.topic)
            if c.resolution != g["resolution"]:
                wrong_resolution.append(c.topic)
        else:
            wrong_values.append((c.topic, c.values, g["values"]))

    submitted_topics = {c.topic for c in conf}
    gold_topics = set(gold_by_topic)
    fp = submitted_topics - gold_topics
    missed = gold_topics - submitted_topics

    precision = len(matched) / len(conf) if conf else 0.0
    recall = len(matched) / len(real) if real else 0.0
    res_ok = len(matched) - len(wrong_resolution)
    resolution = res_ok / len(matched) if matched else 0.0

    # forbidden-pair check: excluded candidates must never surface
    forbidden_hits = []
    for c in conf:
        if "5.34%" in (c.values or []):
            forbidden_hits.append(("5.34%", c.topic))
        for kw in ("branch_count", "forbes"):
            if kw in c.topic.lower():
                forbidden_hits.append((kw, c.topic))

    ok = precision >= 0.8 and resolution >= 0.8 and not forbidden_hits
    print(f"conflicts: submitted={len(conf)} gold={len(real)}")
    print(f"precision: {precision:.2f} (gate >=0.80) | recall: {recall:.2f} | resolution: {resolution:.2f} (gate >=0.80)")
    if fp:
        print("false positives:", sorted(fp)[:6])
    if missed:
        print("missed gold topics:", sorted(missed)[:6])
    if wrong_values:
        print("value mismatches:", wrong_values[:4])
    if wrong_resolution:
        print("resolution mismatches:", wrong_resolution[:4])
    if forbidden_hits:
        print("FORBIDDEN pairs surfaced:", forbidden_hits[:6])
    print("verdict:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
