"""S0.3 component tests: the answer path (snapshot select → trust → template)."""
import re
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

import question as Q  # noqa: E402
import trust as TR  # noqa: E402
from contract import Page, Snapshot  # noqa: E402


def _snapshot(day, certs_lines):
    md = (
        "Certificates\n\nSpecial Certificates\n\n"
        "| Certificate | Dividend Rate | Annual Percentage Yield (APY) | Min. to Earn |\n"
        "| --- | --- | --- | --- |\n" + "\n".join(certs_lines) + "\n\n"
        "Rates are effective as of 2026-01-01 and are subject to change without notice.\n"
    )
    return Snapshot(f"NT_{day}", day, [
        Page("https://www.example.org/rates", "Rates", md, f"{day}T00:00:00Z"),
        Page("https://www.example.org/personal/savings-account", "Certificates",
             md, f"{day}T00:00:00Z"),
    ])


OLD = ["| 10 Month Fixed Jumbo Certificate Special | 3.86% | 3.90%1 | $100,000 |"]
NEW = [
    "| 17 Month Fixed Jumbo Certificate Special | 4.15% | 4.20%1 | $100,000.00 |",
    "| 17 Month Fixed Certificate Special | 4.06% | 4.10%2 | $1,000.00 |",
    "| 10 Month Fixed Jumbo Certificate Special | 3.96% | 4.00%1 | $100,000.00 |",
]


class TestAnswerPath(unittest.TestCase):
    def setUp(self):
        self.ks = SOL.build()
        self.ks.ingest(_snapshot("2026-05-19", OLD))
        self.ks.ingest(_snapshot("2026-09-28", NEW))

    def test_current_17month_special_states_both_variants(self):
        a = self.ks.answer("What is the APY on the 17-month special certificate?")
        self.assertTrue(a.confident)
        self.assertIn("4.10%", a.text)
        self.assertIn("4.20%", a.text)
        self.assertIn("$1,000 minimum", a.text)
        self.assertTrue(a.sources)

    def test_simple_single_claim(self):
        a = self.ks.answer("What is the rate on the 17-month jumbo special certificate?")
        self.assertIn("4.20%", a.text)
        self.assertNotIn("4.10%", a.text)

    def test_as_of_clamps_to_historical_snapshot(self):
        a = self.ks.answer(
            "What was the rate on the 10-month fixed jumbo special certificate as of May 2026?",
            as_of="2026-05-31",
        )
        self.assertIn("3.90%", a.text)
        self.assertNotIn("4.00%", a.text)
        # past as_of → past tense; nothing from the NEW snapshot may leak in (R1)
        self.assertNotIn("pays", a.text)

    def test_refusal_digit_free_when_family_unknown(self):
        a = self.ks.answer("What is your rate on the 7/1 adjustable-rate mortgage?")
        self.assertFalse(a.confident)
        self.assertIsNone(re.search(r"\d", a.text))
        self.assertIsNotNone(re.search(r"(isn't covered|please contact)", a.text, re.I))

    def test_refusal_when_tier_absent_in_history(self):
        a = self.ks.answer("What rate does the 42-month certificate pay?")
        self.assertFalse(a.confident)
        self.assertIsNone(re.search(r"\d", a.text))

    def test_deterministic_repeat(self):
        q = "What is the APY on the 17-month special certificate?"
        self.assertEqual(self.ks.answer(q).text, self.ks.answer(q).text)

    def test_paraphrases_same_values(self):
        t1 = self.ks.answer("What is the APY on the 17-month special certificate?").text
        t2 = self.ks.answer("what is the 17 month special certificate apy?").text
        self.assertEqual(t1, t2)

    def test_conflicts_path_exists_but_empty_pre_s04(self):
        self.assertEqual(self.ks.conflicts(), [])

    def test_question_parser_and_trust_hooks(self):
        s = Q.parse_question("What rate is the 17-month jumbo special certificate?")
        self.assertEqual(s["term_months"], 17)
        self.assertTrue(s["jumbo"])
        self.assertEqual(TR.parse_as_of("2026-05-31"), "2026-05-31")


if __name__ == "__main__":
    unittest.main()
