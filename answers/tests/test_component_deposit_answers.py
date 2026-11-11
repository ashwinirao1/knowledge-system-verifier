"""S1.1 component tests: deposit answer path (tiers, highest, do-any, list-all)."""
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

RATES_MD = """# Rates

Share Savings

| Account Type | Balance Tier | Dividend Rate | Annual Percentage Yield (APY) | Min. to Open | Min. to Earn |
| --- | --- | --- | --- | --- | --- |
| Share Savings | $25,000+ | 0.20% | 0.20% | $25.00 | $25,000.00 |
| Share Savings | $10,000 – $24,999.99 | 0.15% | 0.15% | $25.00 | $10,000.00 |
| Share Savings | $2,500 – $9,999.99 | 0.10% | 0.10% | $25.00 | $2,500.00 |
| Share Savings | $100 – $2,499.99 | 0.10% | 0.10% | $25.00 | $100.00 |
| Share Savings | $0 – $99.99 | 0.00% | 0.00% | $25.00 | $0.00 |

Rates are effective as of 06/15/2026 and are subject to change without notice.

Free Checking

| Account Type | Balance Tier | Dividend Rate | Annual Percentage Yield (APY) | Min. to Open | Min. to Earn |
| --- | --- | --- | --- | --- | --- |
| Free Checking | — | 0.00% | 0.00% | $0.00 | — |

Rates are effective as of 06/02/2026 and are subject to change without notice.

Checking Accounts

1st Rate Checking

| Account Type | Balance Tier | Dividend Rate | Annual Percentage Yield (APY) | Min. to Open | Min. to Earn |
| --- | --- | --- | --- | --- | --- |
| 1st Rate Checking | $100,000+ | 0.10% | 0.10% | — | $100,000.00 |
| 1st Rate Checking | $25,000 – $99,999.99 | 0.10% | 0.10% | — | $25,000.00 |
| 1st Rate Checking | $5,000 – $24,999.99 | 2.47% | 2.50% | — | $5,000.00 |
| 1st Rate Checking | $0.01 – $4,999.99 | 0.00% | 0.00% | $0.00 | $0.01 |

Rates are effective as of 06/02/2026 and are subject to change without notice.
"""


def snap():
    return Snapshot("X_2026-09-01", "2026-09-01", [
        Page("https://www.example.org/rates", "Rates", RATES_MD, "2026-09-01T00:00:00Z"),
    ])


class TestDepositAnswers(unittest.TestCase):
    def setUp(self):
        self.ks = SOL.build()
        self.ks.ingest(snap())

    def test_tier_query_exact_tier_only(self):
        a = self.ks.answer("What dividend rate do I earn on Share Savings with a balance between $10,000 and $24,999?")
        self.assertTrue(a.confident)
        self.assertIn("0.15%", a.text)
        # neighbouring tiers must not leak (0.30%/0.40% trap class)
        self.assertNotIn("0.20%", a.text)
        self.assertNotIn("0.10%", a.text)

    def test_highest_query(self):
        a = self.ks.answer("What is the highest Share Savings APY?")
        self.assertIn("0.20%", a.text)
        self.assertIn("$25,000 and up", a.text)

    def test_do_any_negative_never_repeats_the_queried_value(self):
        a = self.ks.answer("Do any Dupaco savings tiers pay 0.35% APY?")
        self.assertIn("No.", a.text)
        self.assertIn("0.20%", a.text)
        self.assertNotIn("0.35%", a.text)

    def test_do_any_positive_names_the_tier(self):
        a = self.ks.answer("Do any Dupaco savings tiers pay 0.15% APY?")
        self.assertIn("Yes", a.text)
        self.assertIn("0.15%", a.text)
        self.assertIn("$10,000 – $24,999.99", a.text)

    def test_list_all_checking_tiers(self):
        a = self.ks.answer("Provide current checking account interest rates")
        self.assertIn("2.50%", a.text)
        self.assertIn("Free Checking", a.text)
        self.assertIn("1st Rate Checking", a.text)

    def test_generic_savings_maps_to_share_savings(self):
        a = self.ks.answer("What is the current savings rate?")
        self.assertIn("Share Savings", a.text)
        self.assertNotIn("1st Rate Checking", a.text)

    def test_deterministic_repeat(self):
        q = "What is the highest Share Savings APY?"
        self.assertEqual(self.ks.answer(q).text, self.ks.answer(q).text)

    def test_testd_unknown_product_refuses_digit_free(self):
        a = self.ks.answer("What is the rate on the Golden Accordion account?")
        self.assertFalse(a.confident)
        self.assertNotRegex(a.text, r"\d")


class TestBusinessEntityResolution(unittest.TestCase):
    """S3.2: personal vs business rows resolve by member (page-level
    classification), and business rows carry the site's own qualified
    product names. Bright Savings vs 'Jump Start' discipline: a product
    the corpus never mentions must refuse digit-free, never cross-bind."""

    BIZ_MD = """# Business Rates

Business Share Savings

| Account Type | Balance Tier | Dividend Rate | Annual Percentage Yield (APY)1 | Min. to Open | Min. to Earn |
| --- | --- | --- | --- | --- | --- |
| Share Savings | $100,000+ | 0.20% | 0.20%1 | $25.00 | $100,000.00 |
| Share Savings | $0.01 – $99.99 | 0.00% | 0.00%1 | $25.00 | $5.00 |

Rates are effective as of 06/25/2026 and are subject to change without notice.
"""

    def _ks(self):
        ks = SOL.build()
        ks.ingest(Snapshot("B_2026-09-01", "2026-09-01", [
            Page("https://www.example.org/rates", "Rates", RATES_MD, "2026-09-01T00:00:00Z"),
            Page("https://www.example.org/business/rates", "Business Rates", self.BIZ_MD,
                 "2026-09-01T00:00:00Z"),
        ]))
        return ks

    def test_business_savings_uses_business_rows_and_site_name(self):
        a = self._ks().answer("What are the business savings rates?")
        self.assertTrue(a.confident)
        self.assertIn("Business Share Savings", a.text)
        self.assertIn("0.20%", a.text)

    def test_personal_savings_never_shows_business_rows(self):
        a = self._ks().answer("What is the rate on Share Savings?")
        self.assertTrue(a.confident)
        self.assertIn("Share Savings", a.text)
        self.assertNotIn("Business Share Savings", a.text)

    def test_business_tier_set_is_distinct(self):
        # the business table has a $0.01–$99.99 tier; the personal one starts at $0
        a = self._ks().answer("What are the business savings rates?")
        self.assertIn("$100,000 and up", a.text)

    def test_unknown_product_refuses_never_cross_binds(self):
        a = self._ks().answer("What is the rate on the Jump Start account?")
        self.assertFalse(a.confident)
        self.assertNotIn("Bright Savings", a.text)  # no cross-entity binding
        self.assertNotRegex(a.text, r"\d")


if __name__ == "__main__":
    unittest.main()
