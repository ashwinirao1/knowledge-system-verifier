"""S1.3 unit tests: card table grammar — standard vs intro APR, ranges."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cards as C  # noqa: E402
import tables  # noqa: E402


def tabs_of(md: str):
    return tables.parse_tables(md.replace("\\r\\n", "\n"))


class TestParseApr(unittest.TestCase):
    def test_range_en_dash(self):
        self.assertEqual(C.parse_apr("12.50% – 19.50%2"), (12.50, 19.50))

    def test_range_hyphen(self):
        self.assertEqual(C.parse_apr("15.50% - 21.00%1"), (15.50, 21.00))

    def test_single_value_with_footnote(self):
        self.assertEqual(C.parse_apr("20.5%1"), (20.5, None))

    def test_not_a_rate(self):
        self.assertEqual(C.parse_apr("n/a"), (None, None))


class TestCanonicalCard(unittest.TestCase):
    def test_business_before_personal(self):
        # "Platinum Visa" inside "Business Platinum Visa" must not mis-alias
        self.assertEqual(C.canonical_card("Business Platinum Visa"),
                         ("business_platinum_visa", "Business Platinum Visa"))

    def test_heading_fallback(self):
        self.assertEqual(C.canonical_card("Rewards Visa"),
                         ("rewards_visa", "Rewards Visa"))

    def test_unrelated_rows_rejected(self):
        self.assertIsNone(C.canonical_card("Bronze Card"))


class TestCardTableExtraction(unittest.TestCase):
    HUB_MD = """Platinum Visa

| Card Type | APR |
| --- | --- |
| Introductory Balance Transfer Rate | 2.90%1 |
| Platinum Visa Rate | 12.50% – 19.50%2 |

Rates are effective as of 01/02/2026. All loans are subject to approval.

Rewards Visa

| Card Type | APR |
| --- | --- |
| Standard | 15.50% – 21.00%1 |

Rates are effective as of 01/02/2026. All loans are subject to approval.
"""
    BUSINESS_MD = """Business Rewards Visa

| Card Type | APR |
| --- | --- |
| Business Rewards Visa | 20.5%1 |

Rates are effective as of 1/1/2026 and are subject to change without notice.
"""

    def test_intro_row_flagged(self):
        tabs = tabs_of(self.HUB_MD)
        claims = C.extract_cards(tabs[0])
        intro = [c for c in claims if c["tier_dims"]["rate_period"] == "intro"]
        self.assertEqual(len(intro), 1)
        self.assertEqual(intro[0]["value"], 2.90)
        self.assertEqual(intro[0]["tier_dims"]["card"], "platinum_visa")

    def test_standard_range_keeps_high_bound(self):
        tabs = tabs_of(self.HUB_MD)
        claims = C.extract_cards(tabs[0])
        std = [c for c in claims if c["tier_dims"]["rate_period"] is None
               and c["tier_dims"]["card"] == "platinum_visa"]
        self.assertEqual(std[0]["value"], 12.50)
        self.assertEqual(std[0]["tier_dims"]["apr_high"], 19.50)

    def test_heading_resolves_product_of_generic_row(self):
        tabs = tabs_of(self.HUB_MD)
        claims = C.extract_cards(tabs[1])
        rewards = [c for c in claims if c["tier_dims"]["card"] == "rewards_visa"]
        self.assertEqual(len(rewards), 1)
        self.assertEqual(rewards[0]["value"], 15.50)

    def test_single_digit_effective_date(self):
        tabs = tabs_of(self.BUSINESS_MD)
        claims = C.extract_cards(tabs[0])
        self.assertEqual(claims[0]["effective_date"], "2026-01-01")

    def test_foreign_tables_ignored(self):
        md = """Savings

| Account Type | Balance Tier | Dividend Rate | APY |
| --- | --- | --- | --- |
| Share Savings | $25,000+ | 0.20% | 0.20% |
"""
        self.assertEqual(C.extract_cards(tabs_of(md)[0]), [])


if __name__ == "__main__":
    unittest.main()
