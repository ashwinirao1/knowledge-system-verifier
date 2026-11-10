"""S1.3 component tests: card answers — four-card list, standard-vs-intro."""
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

HUB_CARDS = """# Credit Cards

Platinum Visa

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

BUSINESS_CARDS = """Business Credit Cards

Business Platinum Visa

| Card Type | APR |
| --- | --- |
| Business Platinum Visa | 15.50%1 |

Rates are effective as of 01/01/2026 and are subject to change without notice.

Business Rewards Visa

| Card Type | APR |
| --- | --- |
| Business Rewards Visa | 20.5%1 |

Rates are effective as of 01/01/2026 and are subject to change without notice.
"""


def snap():
    return Snapshot("X_2026-10-01", "2026-10-01", [
        Page("https://www.example.org/rates", "Rates", HUB_CARDS, "2026-10-01T00:00:00Z"),
        Page("https://www.example.org/business-credit-cards", "Business Credit Cards",
             BUSINESS_CARDS, "2026-10-01T00:00:00Z"),
    ])


class TestCardAnswers(unittest.TestCase):
    def setUp(self):
        self.ks = SOL.build()
        self.ks.ingest(snap())

    def test_four_card_list(self):
        a = self.ks.answer("What credit cards do you offer and what are their APRs?")
        for needle in ("Platinum Visa", "Rewards Visa", "Business Platinum", "Business Rewards"):
            self.assertIn(needle, a.text)
        self.assertIn("12.50%", a.text)
        self.assertIn("20.50%", a.text)

    def test_intro_rate_labelled_as_intro(self):
        a = self.ks.answer("What credit cards do you offer and what are their APRs?")
        self.assertIn("2.90%", a.text)
        self.assertIn("intro", a.text.lower())

    def test_standard_apr_never_confused_with_intro(self):
        a = self.ks.answer("What is the standard purchase APR on the Dupaco Platinum Visa?")
        self.assertIn("12.50%", a.text)
        # the intro value may appear but only as the clearly-labelled caveat
        self.assertNotIn("9.9%", a.text)
        self.assertLess(a.text.index("12.50%"), a.text.find("2.90%"))

    def test_rates_for_the_credit_cards(self):
        a = self.ks.answer("I would like to know the rates for the credit cards")
        self.assertIn("12.50%", a.text)
        self.assertIn("15.50%", a.text)

    def test_business_only_question(self):
        a = self.ks.answer("What are the APRs on your business credit cards?")
        self.assertIn("Business Platinum Visa", a.text)
        self.assertIn("15.50%", a.text)
        self.assertNotIn("2.90%", a.text)  # intro is a personal-card offer

    def test_unknown_card_refuses_digit_free(self):
        a = self.ks.answer("What is the APR on the Titanium Amethyst card?")
        self.assertFalse(a.confident)
        self.assertNotRegex(a.text, r"\d")

    def test_deterministic_repeat(self):
        q = "What credit cards do you offer and what are their APRs?"
        self.assertEqual(self.ks.answer(q).text, self.ks.answer(q).text)


if __name__ == "__main__":
    unittest.main()
