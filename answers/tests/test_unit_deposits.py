"""S1.1 unit tests: deposit balance-tier parser + row grammar."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import deposits as D  # noqa: E402


class TestBalanceTier(unittest.TestCase):
    def test_open_ended_tier(self):
        self.assertEqual(D.parse_balance_tier("$25,000+"), (25000.0, None, "$25,000+"))

    def test_bounded_tier_with_en_dash_and_cents(self):
        lo, hi, _ = D.parse_balance_tier("$10,000 – $24,999.99")
        self.assertEqual((lo, hi), (10000.0, 24999.99))

    def test_bounded_tier_without_spaces(self):
        lo, hi, _ = D.parse_balance_tier("$250,000-$1,000,000")
        self.assertEqual((lo, hi), (250000.0, 1000000.0))

    def test_dash_only_means_not_tiered(self):
        lo, hi, _ = D.parse_balance_tier("—")
        self.assertEqual((lo, hi), (None, None))

    def test_single_value_tier(self):
        lo, hi, _ = D.parse_balance_tier("$12,000")
        self.assertEqual((lo, hi), (12000.0, 12000.0))


class TestTieredTableExtraction(unittest.TestCase):
    TABLE = """Share Savings

| Account Type | Balance Tier | Dividend Rate | Annual Percentage Yield (APY)1 | Min. to Open | Min. to Earn |
| --- | --- | --- | --- | --- | --- |
| Share Savings | $25,000+ | 0.20% | 0.20%1 | $25.00 | $25,000.00 |
| Share Savings | $10,000 – $24,999.99 | 0.15% | 0.15%1 | $25.00 | $10,000.00 |

Rates are effective as of 06/15/2026 and are subject to change without notice.
"""

    def test_extracts_both_metrics_per_row(self):
        tabs = __import__("tables").parse_tables(self.TABLE)
        claims = D.extract_deposits(tabs[0])
        metrics = {c["metric"] for c in claims}
        self.assertEqual(metrics, {"apy", "dividend_rate"})

    def test_product_and_tier_dims(self):
        tabs = __import__("tables").parse_tables(self.TABLE)
        claims = [c for c in D.extract_deposits(tabs[0]) if c["tier_dims"]["tier_low"] == 10000.0]
        self.assertEqual(len(claims), 2)
        d = claims[0]["tier_dims"]
        self.assertEqual(d["product"], "share_savings")
        self.assertEqual(d["tier_high"], 24999.99)
        self.assertEqual(claims[0]["value"], 0.15)

    def test_effective_date_carried(self):
        tabs = __import__("tables").parse_tables(self.TABLE)
        claims = D.extract_deposits(tabs[0])
        self.assertTrue(all(c["effective_date"] == "2026-06-15" for c in claims))

    def test_certificate_tables_ignored(self):
        cert_table = """Special Certificates

| Certificate | Dividend Rate | Annual Percentage Yield (APY) | Min. to Earn |
| --- | --- | --- | --- |
| 17 Month Fixed Certificate Special | 4.06% | 4.10%2 | $1,000.00 |
"""
        tabs = __import__("tables").parse_tables(cert_table)
        self.assertEqual(D.extract_deposits(tabs[0]), [])

    def test_non_tier_header_ignored(self):
        t = """Loans

| Loan Program | Term | APR |
| --- | --- | --- |
| 2024-27 Model Year | 48 Months | 5.19% |
"""
        tabs = __import__("tables").parse_tables(t)
        self.assertEqual(D.extract_deposits(tabs[0]), [])


class TestPromoColumns(unittest.TestCase):
    """The intro/after-promo columns must fork into distinct rate periods, not
    two values for one key (R5 — realistic trap from the real corpus)."""

    TABLE = """Achieve Money Market

| Account Type | Balance Tier | Dividend Rate for 1st 6 Months | Annual Percentage Yield (APY)* for 1st 6 Months | Dividend Rate After Promotional Period | APY* After Promotional Period | Min. to Open | Min. to Earn |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Achieve Money Market | $25,000-$99,999.99 | 4.00% | 3.66% | 3.20% | 3.25% | $25,000 | $25,000 |
"""

    def test_intro_columns_get_intro_period(self):
        tabs = __import__("tables").parse_tables(self.TABLE)
        claims = D.extract_deposits(tabs[0])
        intro = [c for c in claims if c["tier_dims"]["rate_period"] == "intro"]
        self.assertEqual({c["value"] for c in intro}, {4.00, 3.66})

    def test_after_promo_columns_count_as_standard(self):
        tabs = __import__("tables").parse_tables(self.TABLE)
        claims = D.extract_deposits(tabs[0])
        std = [c for c in claims if c["tier_dims"]["rate_period"] is None]
        self.assertEqual({c["value"] for c in std}, {3.20, 3.25})

    def test_no_duplicate_claims(self):
        tabs = __import__("tables").parse_tables(self.TABLE)
        claims = D.extract_deposits(tabs[0])
        self.assertEqual(len(claims), 4)  # 2 metrics x 2 periods


class TestProductAliases(unittest.TestCase):
    def test_business_variant_alias(self):
        ident = D.canonical_product("Business 1st Rate Checking")
        self.assertEqual(ident, ("first_rate_checking", "1st Rate Checking"))

    def test_apostrophe_variants(self):
        for label in ("Investor's Choice Money Market", "Investor’s Choice Money Market"):
            ident = D.canonical_product(label)
            self.assertEqual(ident, ("investors_choice_mm", "Investor's Choice Money Market"))

    def test_unknown_rows_skipped(self):
        self.assertIsNone(D.canonical_product("Gold Star Checking"))


if __name__ == "__main__":
    unittest.main()
