#!/usr/bin/env python3
"""S0.6 eval regression gate: compare a run_eval report.json against the committed baseline.

Fails (exit 1) when any tracked metric regresses beyond tolerance. This is what makes
"evals in CI" a red/green signal rather than a report nobody reads — one eval path (the
harness's run_eval), one scoreboard (the committed baseline), zero drift.

Usage:
    python tools/eval_gate.py \
        --report results_ci/selftest/report.json \
        --baseline answers/tests/baseline_selftest.json [--tolerance 0.0001]
"""
import argparse
import json
import sys
from pathlib import Path


def _compare(name, now, base, tol, fails):
    if now is None:
        return  # metric absent (e.g. conflicts gold not passed) — nothing to gate
    if base is None:
        return  # metric absent in the committed baseline — not yet tracked
    if now < base - tol:
        fails.append(
            f"REGRESSION {name}: baseline={base} now={now} (drop={round(base - now, 4)})"
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True, help="stack report.json from run_eval.py")
    ap.add_argument("--baseline", required=True, help="committed baseline JSON (subset)")
    ap.add_argument("--tolerance", type=float, default=0.0001, help="allowed float drift")
    ap.add_argument("--max-errors", type=int, default=0, help="max tolerated question errors/timeouts")
    ap.add_argument("--max-ingest-s", type=float, default=120.0, help="max ingest seconds (synthetic corpus)")
    args = ap.parse_args()

    report = json.loads(Path(args.report).read_text())
    base = json.loads(Path(args.baseline).read_text())
    fails: list = []

    # invariants first (crash-free, fast, ingest bounded)
    if report.get("errors", 0) > args.max_errors:
        fails.append(f"HARD LIMIT errors/timeouts: {report['errors']} > {args.max_errors}")
    if report.get("ingest_over_limit") is True:
        fails.append("HARD LIMIT ingest_over_limit=true")
    _compare("ingest_seconds", report.get("ingest_seconds"), base.get("ingest_seconds"),
             max(args.tolerance, 5.0), fails)  # ingest is not exactly float-stable; allow small headroom

    # pillars
    _compare("qa_score", report.get("qa_score"), base.get("qa_score"), args.tolerance, fails)
    _compare("final_score", report.get("final_score"), base.get("final_score"), args.tolerance, fails)
    _compare("consistency", (report.get("consistency") or {}).get("score"),
             (base.get("consistency") or {}).get("score"), args.tolerance, fails)
    _compare("speed", (report.get("speed") or {}).get("score"),
             (base.get("speed") or {}).get("score"), args.tolerance, fails)
    _compare("conflicts.f1", (report.get("conflicts") or {}).get("f1"),
             (base.get("conflicts") or {}).get("f1"), args.tolerance, fails)
    _compare("conflicts.resolution_accuracy", (report.get("conflicts") or {}).get("resolution_accuracy"),
             (base.get("conflicts") or {}).get("resolution_accuracy"), args.tolerance, fails)

    # per-category regression (no category may get worse)
    now_cat = report.get("by_category") or {}
    for cat, b in (base.get("by_category") or {}).items():
        n = now_cat.get(cat, {}).get("score")
        _compare(f"category[{cat}]", n, b.get("score"), args.tolerance, fails)
        if b.get("n") and now_cat.get(cat, {}).get("n") != b["n"]:
            fails.append(f"HARD LIMIT category[{cat}] question count changed: {b['n']} -> {now_cat.get(cat, {}).get('n')}")

    if fails:
        print(f"eval gate FAILED ({len(fails)}):", file=sys.stderr)
        for f in fails:
            print("  " + f, file=sys.stderr)
        return 1

    print(
        "eval gate OK: "
        f"qa={report.get('qa_score')} final={report.get('final_score')} "
        f"errors={report.get('errors')} ingest={report.get('ingest_seconds')}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
