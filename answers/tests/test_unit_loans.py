"""S1.2 unit tests: loan row grammar — auto model-year tiers, mortgage labels,
personal term rows, amount tiers."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import loans as L  # noqa: E402
import tables  # noqa: E402


def rows_for(md: str):
    return tables.parse_tables(md.replace("\\r\\n", "\n"))


class TestModelYearDims(unittest.TestCase):
    def test_range_aggregates_short_digits(self):
        self.assertEqual(
            L._auto_dims("2024-27 Model Year"),
            {"model_from": 2024.0, "model_to": 2027.0, "model_older": False},
        )

    def test_older_open_ended(self):
        dims = L._auto_dims("2016 Model Year (and older)")
        self.assertEqual((dims["model_from"], dims["model_to"]), (None, 2016.0))
        self.assertTrue(dims["model_older"])

    def test_plain_label_not_a_model_row(self):
        self.assertIsNone(L._auto_dims("48 Months"))

    def test_leading_label_descending_years(self):
        """'Model Year 2026-23' publishes the years descending — canonical
        dims must be ascending (2023 through 2026), matching the same span
        written digits-first elsewhere."""
        self.assertEqual(
            L._auto_dims("Model Year 2026-23"),
            {"model_from": 2023.0, "model_to": 2026.0, "model_older": False},
        )

    def test_leading_label_two_year_span(self):
        self.assertEqual(
            L._auto_dims("Model Year 2022-21"),
            {"model_from": 2021.0, "model_to": 2022.0, "model_older": False},
        )


class TestMortgageLabels(unittest.TestCase):
    def test_purchase_with_amount(self):
        d = L._mortgage_dims("Purchase: 30-Year Fixed Conventional $832,750 or less")
        self.assertEqual(d["purpose"], "purchase")
        self.assertEqual(d["term_years"], 30)
        self.assertEqual(d["amount_up_to"], 832750.0)

    def test_refinance_without_amount(self):
        d = L._mortgage_dims("Refinance: 15-Year Fixed")
        self.assertEqual(d["purpose"], "refinance")
        self.assertIsNone(d["amount_up_to"])

    def test_relief_row_is_not_a_tier(self):
        self.assertIsNone(
            L._mortgage_dims("Mortgage Rate Relief Program for qualified Borrowers ***")
        )


class TestAutoTable(unittest.TestCase):
    MD = """Auto & Motorcycle Loans

| Loan Program | Term | Annual Percentage Rate (As Low As) |
| --- | --- | --- |
| 2024-27 Model Year | 48 Months | 5.19% APR1 |
| 2024-27 Model Year | 60 Months | 5.39% APR1 |
| 2016 Model Year (and older) | 48 Months | 8.59% APR1 |

Rates are effective as of 08/31/2026. All loans are subject to approval.
"""

    def test_model_rows_get_term_and_family(self):
        tabs = rows_for(self.MD)
        claims = L.extract_loans(tabs[0])
        sixty = [c for c in claims if c["tier_dims"].get("term_months") == 60]
        self.assertEqual(len(sixty), 1)
        d = sixty[0]["tier_dims"]
        self.assertEqual(d["family"], "auto")
        self.assertEqual((d["model_from"], d["model_to"]), (2024.0, 2027.0))
        self.assertEqual(sixty[0]["value"], 5.39)
        self.assertEqual(sixty[0]["effective_date"], "2026-08-31")

    def test_each_row_one_metric(self):
        tabs = rows_for(self.MD)
        claims = L.extract_loans(tabs[0])
        keys = {(c["tier_dims"].get("model_from"), c["tier_dims"].get("term_months"))
                for c in claims}
        self.assertEqual(len(keys), 3)

    def test_deposit_header_tables_do_not_leak_into_loans(self):
        md = """Savings

| Account Type | Balance Tier | Dividend Rate | Annual Percentage Yield (APY) |
| --- | --- | --- | --- |
| Share Savings | $25,000+ | 0.20% | 0.20% |
"""
        tabs = rows_for(md)
        self.assertEqual(L.extract_loans(tabs[0]), [])


class TestMortgageTable(unittest.TestCase):
    MD = """Home Loans - Purchase

| Program | Rate | Points | APR | *Payment Example |
| --- | --- | --- | --- | --- |
| Purchase: 30-Year Fixed Conventional $100,000 or less | 7.13% | 0 | 7.27% | $673.80 |
| Purchase: 15-Year Fixed Conventional | 6.75% | 0 | 6.88% | $1,327.36 |
"""
    STALE = """Home Loans

| Term | Rate | Points | APR | *Payment Example |
| --- | --- | --- | --- | --- |
| Purchase: 30-Year Fixed Conventional $100,000 or less | 6.000% | 0.00% | 6.037% | $816.73 |
"""

    def test_rate_and_apr_pair_per_tier(self):
        tabs = rows_for(self.MD)
        claims = L.extract_loans(tabs[0])
        metrics = {(c["tier_dims"]["term_years"], c["metric"]) for c in claims}
        self.assertIn((30, "rate"), metrics)
        self.assertIn((30, "apr"), metrics)
        self.assertEqual(len([c for c in claims if c["metric"] == "points"]), 0)

    def test_purpose_from_label_not_section(self):
        """A stale purchase sheet under a bare 'Home Loans' heading must land in
        the same canonical keys as the rate-sheet rows it competes with."""
        tabs = rows_for(self.STALE)
        claims = L.extract_loans(tabs[0])
        self.assertEqual(len(claims), 2)  # rate + APR
        self.assertEqual(claims[0]["tier_dims"]["family"], "mortgage_purchase")


class TestTermRows(unittest.TestCase):
    def test_personal_term_rows(self):
        md = """Personal Loan

| Term | APR (As Low As) |
| --- | --- |
| 24 Months | 9.99%1 |
| 36 Months | 10.49%1 |
"""
        tabs = rows_for(md)
        claims = L.extract_loans(tabs[0])
        values = {c["tier_dims"]["term_months"]: c["value"] for c in claims}
        self.assertEqual(values, {24: 9.99, 36: 10.49})
        self.assertTrue(all(c["tier_dims"]["family"] == "personal" for c in claims))

    def test_amount_tier_rows(self):
        md = """Home Improvement Loans

| Loan Amount | Term | APR (As Low As) |
| --- | --- | --- |
| $10,000.00 – $20,000.00 | 120 Months | 8.50%1 |
"""
        tabs = rows_for(md)
        claims = L.extract_loans(tabs[0])
        self.assertEqual(len(claims), 1)
        d = claims[0]["tier_dims"]
        self.assertEqual(d["family"], "home_improvement")
        self.assertEqual(d["term_months"], 120)
        self.assertEqual(d["amount_low"], 10000.0)


if __name__ == "__main__":
    unittest.main()
