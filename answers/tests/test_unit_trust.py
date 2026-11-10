"""S2.2 unit tests: the temporal family — as_of parsing and snapshot clamping.

The four as_of edges (story S2.2) must each behave predictably:
  between pulls -> newest snapshot published by that date;
  inside a long gap between crawls -> the older of the neighbours;
  after the latest snapshot -> the latest;
  before the baseline -> the EARLIEST snapshot + "before_baseline" status
  (the caller adds a provenance note; never a silent refusal).
Input parsing: ISO YYYY-MM-DD required; month names tolerated (full and
abbreviated, clamped to month end); anything else -> None = "now".
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import trust as TR  # noqa: E402

# mirrors the real corpus cadence: baseline, quick recrawl, monthly, then an
# ~11-week gap before the latest rebaseline
SNAP_DATES = {
    "01_2026-05-12_baseline": "2026-05-12",
    "02_2026-05-19_recrawl": "2026-05-19",
    "03_2026-06-09_recrawl": "2026-06-09",
    "04_2026-08-27_rebaseline": "2026-08-27",
    "05_2026-09-28_latest": "2026-09-28",
}


class TestParseAsOf(unittest.TestCase):
    def test_iso_passthrough(self):
        self.assertEqual(TR.parse_as_of("2026-05-31"), "2026-05-31")

    def test_none_and_empty_mean_now(self):
        self.assertIsNone(TR.parse_as_of(None))
        self.assertIsNone(TR.parse_as_of(""))
        self.assertIsNone(TR.parse_as_of("   "))

    def test_full_month_name_clamps_to_month_end(self):
        self.assertEqual(TR.parse_as_of("May 2026"), "2026-05-31")
        self.assertEqual(TR.parse_as_of("February 2024"), "2024-02-29")  # leap

    def test_abbreviated_month_names(self):
        self.assertEqual(TR.parse_as_of("jun 2026"), "2026-06-30")
        self.assertEqual(TR.parse_as_of("Sept 2026"), "2026-09-30")
        self.assertEqual(TR.parse_as_of("Dec 2025"), "2025-12-31")

    def test_unparseable_returns_none(self):
        # garbage, and the site's slash format: the harness contract is ISO;
        # unknown input falls back to "now" rather than guessing a date
        self.assertIsNone(TR.parse_as_of("banana"))
        self.assertIsNone(TR.parse_as_of("05/31/2026"))
        self.assertIsNone(TR.parse_as_of("Maya 2026"))
        self.assertIsNone(TR.parse_as_of("2026-13-01"))


class TestClampSnapshotEdges(unittest.TestCase):
    def test_none_means_latest(self):
        snap, status = TR.clamp_snapshot(SNAP_DATES, None)
        self.assertEqual(snap, "05_2026-09-28_latest")
        self.assertEqual(status, "now")

    def test_between_pulls_takes_the_older_neighbour(self):
        # 05-15 sits between baseline (05-12) and recrawl (05-19)
        snap, status = TR.clamp_snapshot(SNAP_DATES, "2026-05-15")
        self.assertEqual(snap, "01_2026-05-12_baseline")
        self.assertEqual(status, "ok")

    def test_exact_boundary_is_inclusive(self):
        snap, _ = TR.clamp_snapshot(SNAP_DATES, "2026-05-19")
        self.assertEqual(snap, "02_2026-05-19_recrawl")

    def test_public_eval_edge_0531(self):
        # the dup-006 edge: 05-31 -> the 05-19 recrawl
        snap, status = TR.clamp_snapshot(SNAP_DATES, "2026-05-31")
        self.assertEqual(snap, "02_2026-05-19_recrawl")
        self.assertEqual(status, "ok")

    def test_inside_the_long_gap_takes_the_older_side(self):
        # 07-01 sits in the ~11-week gap between 06-09 and 08-27
        snap, status = TR.clamp_snapshot(SNAP_DATES, "2026-07-01")
        self.assertEqual(snap, "03_2026-06-09_recrawl")
        self.assertEqual(status, "ok")

    def test_after_latest_takes_the_latest(self):
        snap, status = TR.clamp_snapshot(SNAP_DATES, "2026-12-25")
        self.assertEqual(snap, "05_2026-09-28_latest")
        self.assertEqual(status, "ok")

    def test_before_baseline_takes_earliest_with_status(self):
        snap, status = TR.clamp_snapshot(SNAP_DATES, "2026-01-01")
        self.assertEqual(snap, "01_2026-05-12_baseline")
        self.assertEqual(status, "before_baseline")

    def test_empty_ledger(self):
        snap, status = TR.clamp_snapshot({}, None)
        self.assertIsNone(snap)
        self.assertEqual(status, "none")

    def test_snapshot_id_as_of_still_none_before_baseline(self):
        # the low-level selector keeps its contract: None = "nothing eligible";
        # only clamp_snapshot implements the earliest+note edge
        self.assertIsNone(TR.snapshot_id_as_of(SNAP_DATES, "2026-01-01"))


if __name__ == "__main__":
    unittest.main()
