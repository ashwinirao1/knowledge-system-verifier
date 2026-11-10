"""S1.2 component tests: loan answer path — auto model-year trap defence,
mortgage tiers, personal term, metric fallback."""
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

HUB = """# Rates

Auto & Motorcycle Loans

| Loan Program | Term | Annual Percentage Rate (As Low As) |
| --- | --- | --- |
| 2024-27 Model Year | 48 Months | 5.19% APR |
| 2024-27 Model Year | 60 Months | 5.39% APR |
| 2024-27 Model Year | 84 Months | 5.59% APR |
| 2017-20 Model Year | 60 Months | 6.34% APR |

Rates are effective as of 08/31/2026. All loans are subject to approval.

Home Loans - Purchase

| Program | Rate | Points | APR | *Payment Example |
| --- | --- | --- | --- | --- |
| Purchase: 30-Year Fixed Conventional $100,000 or less | 7.13% | 0 | 7.27% | $673.80 |
| Purchase: 30-Year Fixed Conventional $200,000 or less | 7.25% | 0 | 7.34% | $59.00 |
| Purchase: 15-Year Fixed Conventional | 6.75% | 0 | 6.88% | $1.00 |

Rates are effective as of 09/25/2026. Rates may be as low as quoted rates.

Personal Loan

| Term | APR (As Low As) |
| --- | --- |
| 24 Months | 9.99% |
| 36 Months | 10.49% |

Rates are effective as of 05/01/2026. All loans are subject to approval.
"""

# a stale promo copy of the auto sheet: a DIFFERENT model range covering the
# asked years, at lower page rank — the trap shape from the real corpus
PROMO = """Switch & Earn

Auto Loans

| Loan Program | Term | Annual Percentage Rate (As Low As) |
| --- | --- | --- |
| 2023-26 Model Year | 60 Months | 5.34% APR |
| 2023-26 Model Year | 84 Months | 5.54% APR |

Rates are effective as of 1/1/2026. All loans are subject to approval.
"""


def snap():
    return Snapshot("X_2026-10-01", "2026-10-01", [
        Page("https://www.example.org/rates", "Rates", HUB, "2026-10-01T00:00:00Z"),
        Page("https://www.example.org/switch-and-earn", "Switch & Earn", PROMO,
             "2026-10-01T00:00:00Z"),
    ])


class TestLoanAnswers(unittest.TestCase):
    def setUp(self):
        self.ks = SOL.build()
        self.ks.ingest(snap())

    def test_auto_model_year_prefers_the_rate_sheet_rows(self):
        a = self.ks.answer("What's the APR for a 60-month auto loan on a 2025 model-year vehicle?")
        self.assertIn("5.39%", a.text)
        self.assertNotIn("5.34%", a.text)
        self.assertNotIn("5.54%", a.text)

    def test_auto_84_month_2024(self):
        a = self.ks.answer("What's the APR for an 84-month auto loan on a 2024 vehicle?")
        self.assertIn("5.59%", a.text)
        self.assertNotIn("5.54%", a.text)
        self.assertNotIn("6.34%", a.text)

    def test_personal_term_row(self):
        a = self.ks.answer("What is the APR on a 36-month personal loan?")
        self.assertIn("10.49%", a.text)
        self.assertNotIn("9.99%", a.text)

    def test_mortgage_30_year_tiers(self):
        a = self.ks.answer("Can you tell me the interest rate for a 30-year mortgage?")
        self.assertIn("7.13%", a.text)
        self.assertIn("7.25%", a.text)
        self.assertNotIn("6.75%", a.text)  # 15-year tier must not leak into 30y question
        self.assertIn("$100,000", a.text)

    def test_mortgage_generic_leads_with_smallest_amount_tier(self):
        a = self.ks.answer("What are the mortgage rates right now?")
        first = a.text.split(";")[0]
        self.assertIn("$100,000", first)
        self.assertIn("7.13%", a.text)

    def test_metric_fallback_when_family_publishes_only_that_metric(self):
        # auto tables publish "Annual Percentage Rate", slots may ask for "rate"
        a = self.ks.answer("What is the interest rate on a 60-month auto loan for a 2025 model-year vehicle?")
        self.assertIn("5.39%", a.text)

    def test_unknown_family_refuses_digit_free(self):
        a = self.ks.answer("What is the APR on a dirigible loan?")
        self.assertFalse(a.confident)
        self.assertNotRegex(a.text, r"\d")

    def test_deterministic_repeat(self):
        q = "What's the APR for a 60-month auto loan on a 2025 model-year vehicle?"
        self.assertEqual(self.ks.answer(q).text, self.ks.answer(q).text)


class TestStaleSiblingTrustResolution(unittest.TestCase):
    """The promo copy stays live in the snapshot: the leading rank wins per term."""

    def setUp(self):
        self.ks = SOL.build()
        self.ks.ingest(snap())

    def test_covering_range_resolved_to_higher_rank_page(self):
        a = self.ks.answer("What's the APR for a 60-month auto loan on a 2026 model-year vehicle?")
        # 2024-27 (hub, rank-leads) covers 2026; the 2023-26 promo row must lose
        self.assertIn("5.39%", a.text)
        self.assertNotIn("5.34%", a.text)


if __name__ == "__main__":
    unittest.main()
