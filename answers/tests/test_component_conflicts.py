"""S0.4 component tests: conflicts generator (R5 precision rules)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "solution_under_test", Path(__file__).resolve().parent.parent / "solution.py"
)
SOL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SOL)

from contract import Page, Snapshot  # noqa: E402

RATES_MD = """Certificates

Special Certificates

| Certificate | Dividend Rate | Annual Percentage Yield (APY) | Min. to Earn |
| --- | --- | --- | --- |
{ROWS}

Rates are effective as of 09/01/2026 and are subject to change without notice.
"""


def snap(rows):
    md = RATES_MD.replace("{ROWS}", "\n".join(rows))
    return Snapshot("X_2026-09-01", "2026-09-01", [
        Page("https://www.example.org/rates", "Rates", md, "2026-09-01T00:00:00Z"),
    ])


class TestConflicts(unittest.TestCase):
    def _make(self, snapshots_repos):
        """snapshots_repos: [(url, page_type_rank_override NOT used, title, md)]"""
        ks = SOL.build()
        for s in snapshots_repos:
            ks.ingest(s)
        return ks

    def test_disagreeing_pages_same_key_yield_one_conflict_with_winner(self):
        promo = (
            "| Certificate | Dividend Rate | Annual Percentage Yield (APY) | Min. to Earn |\n"
            "| --- | --- | --- | --- |\n"
            "| 17 Month Fixed Certificate Special | 4.06% | 3.70%2 | $1,000 |\n"
        )
        rates = RATES_MD.replace("{ROWS}", "| 17 Month Fixed Certificate Special | 4.06% | 4.10%2 | $1,000 |")
        ks = self._make([
            Snapshot("X_2026-09-01", "2026-09-01", [
                Page("https://www.example.org/rates", "Rates", rates, "2026-09-01T00:00:00Z"),
                Page("https://www.example.org/promo/summer-special", "Summer Special", promo, "2026-09-01T00:00:00Z"),
            ]),
        ])
        conf = ks.conflicts()
        self.assertEqual(len(conf), 1)
        c = conf[0]
        self.assertEqual(c.resolution, "4.10%")
        self.assertEqual(c.values[0], "4.10%")
        self.assertIn("3.70%", c.values)
        self.assertIn("freshest", c.reason.lower())

    def test_conflict_reason_cites_the_transition(self):
        """S2.3: a key that ALSO moved between snapshots cites its history —
        previous value + the snapshot it held until — in the reason string."""
        old_rates = RATES_MD.replace("{ROWS}", "| 17 Month Fixed Certificate Special | 4.06% | 4.10%2 | $1,000 |")
        new_rates = RATES_MD.replace("{ROWS}", "| 17 Month Fixed Certificate Special | 4.06% | 4.20%2 | $1,000 |")
        promo = (
            "| Certificate | Dividend Rate | Annual Percentage Yield (APY) | Min. to Earn |\n"
            "| --- | --- | --- | --- |\n"
            "| 17 Month Fixed Certificate Special | 4.06% | 3.70%2 | $1,000 |\n"
        )
        ks = self._make([
            Snapshot("X_2026-05-01", "2026-05-01", [
                Page("https://www.example.org/rates", "Rates", old_rates, "2026-05-01T00:00:00Z"),
            ]),
            Snapshot("X_2026-09-01", "2026-09-01", [
                Page("https://www.example.org/rates", "Rates", new_rates, "2026-09-01T00:00:00Z"),
                Page("https://www.example.org/promo/summer-special", "Summer Special", promo, "2026-09-01T00:00:00Z"),
            ]),
        ])
        conf = ks.conflicts()
        self.assertEqual(len(conf), 1)
        self.assertIn("Previous value 4.10%", conf[0].reason)
        self.assertIn("2026-09-01", conf[0].reason)

    def test_replicas_same_value_no_conflict(self):
        ks = self._make([snap(["| 17 Month Fixed Certificate Special | 4.06% | 4.10%2 | $1,000 |"])])
        self.assertEqual(ks.conflicts(), [])

    def test_tier_differences_are_not_conflicts(self):
        ks = self._make([snap([
            "| 17 Month Fixed Certificate Special | 4.06% | 4.10%2 | $1,000 |",
            "| 17 Month Fixed Jumbo Certificate Special | 4.15% | 4.20%1 | $100,000 |",
        ])])
        self.assertEqual(ks.conflicts(), [])

    def test_fresher_effective_date_wins_reason_cites_it(self):
        md_a = RATES_MD.replace("{ROWS}", "| 17 Month Fixed Certificate Special | 4.06% | 4.10%2 | $1,000 |")
        md_b = (
            "| Certificate | Dividend Rate | Annual Percentage Yield (APY) | Min. to Earn |\n"
            "| --- | --- | --- | --- |\n"
            "| 17 Month Fixed Certificate Special | 4.06% | 4.15%2 | $1,000 |\n"
            "Rates are effective as of 10/15/2026 and are subject to change without notice.\n"
        )
        ks = self._make([
            Snapshot("X_2026-09-01", "2026-09-01", [
                Page("https://www.example.org/rates", "Rates", md_a, "2026-09-01T00:00:00Z"),
                Page("https://www.example.org/personal/certificates", "Certificates", md_b, "2026-09-01T00:00:00Z"),
            ]),
        ])
        conf = ks.conflicts()
        self.assertEqual(len(conf), 1)
        self.assertEqual(conf[0].resolution, "4.15%")  # fresher value date wins
        self.assertIn("2026-10-15", conf[0].reason)
        self.assertIn("freshest", conf[0].reason.lower())

    def test_prose_promo_line_conflicts_with_table(self):
        """The exact selftest-gold shape: sentences on promo pages vs the table."""
        promo_md = "# Promo\n\nSummer special: 6-month certificate APY 2.95% (offer ended 2025-09-30)\n"
        rates_md = "# Rates\n\nRegular Certificates\n\n| Certificate | Dividend Rate | Annual Percentage Yield (APY) | Min. to Earn |\n| --- | --- | --- | --- |\n| 6 Month | 3.37% | 3.50%1 | $1,000 |\n\nRates are effective as of 09/01/2026 and are subject to change without notice.\n"
        ks = self._make([
            Snapshot("X_2026-09-01", "2026-09-01", [
                Page("https://www.example.org/rates", "Rates", rates_md, "2026-09-01T00:00:00Z"),
                Page("https://www.example.org/promo/summer", "Promo", promo_md, "2026-09-01T00:00:00Z"),
            ]),
        ])
        conf = ks.conflicts()
        self.assertEqual(len(conf), 1)
        self.assertEqual(conf[0].resolution, "3.50%")
        self.assertEqual(conf[0].values, ["3.50%", "2.95%"])

    def test_empty_ledger_no_conflicts(self):
        ks = SOL.build()
        self.assertEqual(ks.conflicts(), [])

    def test_conflict_note_on_answers(self):
        promo = (
            "| Certificate | Dividend Rate | Annual Percentage Yield (APY) | Min. to Earn |\n"
            "| --- | --- | --- | --- |\n"
            "| 17 Month Fixed Certificate Special | 4.06% | 3.70%2 | $1,000 |\n"
        )
        rates = RATES_MD.replace("{ROWS}", "| 17 Month Fixed Certificate Special | 4.06% | 4.10%2 | $1,000 |")
        ks = self._make([
            Snapshot("X_2026-09-01", "2026-09-01", [
                Page("https://www.example.org/rates", "Rates", rates, "2026-09-01T00:00:00Z"),
                Page("https://www.example.org/promo/summer-special", "Summer Special", promo, "2026-09-01T00:00:00Z"),
            ]),
        ])
        a = ks.answer("What is the 17-month special certificate APY?")
        self.assertEqual(a.confident, True)
        self.assertIn("4.10%", a.text)
        self.assertIn("disagree", a.conflict_note or "")


if __name__ == "__main__":
    unittest.main()
