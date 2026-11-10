#!/usr/bin/env python3
"""Profile the ingest phase: where do the seconds go?

Ingest is the batch build job (parse -> classify -> extract claims -> index),
run once per system lifetime. Its budget is 30 minutes; the answering path's
budget is 60 seconds per question, and it stays fast BECAUSE ingest did the
work upfront. Use this tool before optimizing anything:

    python3 tools/profile_ingest.py            # phase breakdown
    python3 tools/profile_ingest.py --profile  # + cProfile hotspots

Reading the output honestly: the interesting question is never "is ingest
fast in absolute terms?" but "how much of its budget does it use, and is any
of this on the serving path?" (It is not.) A batch job using 2% of its budget
does not need optimizing; profile again only when the corpus grows an order
of magnitude or ingest starts mattering operationally.
"""
from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE.parent / "harness"))
sys.path.insert(0, str(HERE.parent / "answers"))

from run_eval import load_snapshots, load_submission  # noqa: E402

INGEST_BUDGET_S = 30 * 60


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", action="store_true", help="also print cProfile hotspots")
    args = ap.parse_args()

    t0 = time.time()
    snaps = load_snapshots(ROOT / "snapshots")
    t1 = time.time()
    ks = load_submission(ROOT / "answers")
    t2 = time.time()

    if args.profile:
        pr = cProfile.Profile()
        pr.enable()
    for s in snaps:
        ks.ingest(s)
    if args.profile:
        pr.disable()
    t3 = time.time()

    pages = sum(len(s.pages) for s in snaps)
    ingest = t3 - t2
    print(f"pages ingested              : {pages:,}")
    print(f"load snapshots from disk    : {t1 - t0:7.1f}s")
    print(f"load submission module      : {t2 - t1:7.1f}s")
    print(f"actual ingest (extract+index): {ingest:6.1f}s")
    print(f"ingest budget               : {INGEST_BUDGET_S}s -> "
          f"{100 * ingest / INGEST_BUDGET_S:.1f}% used")
    if args.profile:
        out = io.StringIO()
        pstats.Stats(pr, stream=out).sort_stats("cumulative").print_stats(20)
        print("\ncProfile hotspots (cumulative):")
        print(out.getvalue())


if __name__ == "__main__":
    main()
