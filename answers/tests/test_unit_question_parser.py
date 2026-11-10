"""S0.3 unit tests: question parser slots (rule grammar)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import question as Q  # noqa: E402


class TestQuestionParser(unittest.TestCase):
    def test_cert_question_slots(self):
        s = Q.parse_question("What is the APY on Dupaco's 17-month special certificate?")
        self.assertEqual(s["term_months"], 17)
        self.assertTrue(s["special"])
        self.assertIsNone(s["jumbo"])
        self.assertEqual(s["metric"], "apy")

    def test_jumbo_phrase(self):
        s = Q.parse_question("What is the current rate on the 10-month fixed jumbo special certificate?")
        self.assertEqual(s["term_months"], 10)
        self.assertTrue(s["jumbo"])
        self.assertTrue(s["special"])

    def test_explicit_regular(self):
        s = Q.parse_question("What's the rate on the regular 60-month certificate?")
        self.assertEqual(s["term_months"], 60)
        self.assertFalse(s["special"])

    def test_word_number_term(self):
        s = Q.parse_question("What does the seventeen month special certificate pay?")
        self.assertEqual(s["term_months"], 17)

    def test_dividend_rate_metric(self):
        s = Q.parse_question("What is the dividend rate on the 17-month special certificate?")
        self.assertEqual(s["metric"], "dividend_rate")

    def test_business_question_flagged(self):
        s = Q.parse_question("What is the business certificate special rate?")
        self.assertEqual(s["member"], "business")

    def test_mortgage_question_not_cert(self):
        self.assertIsNone(Q.parse_question("What is your rate on a 7/1 adjustable-rate mortgage?"))

    def test_topic_without_term_is_still_cert(self):
        s = Q.parse_question("What are the current certificate rates?")
        self.assertIsNotNone(s)
        self.assertIsNone(s["term_months"])

    def test_as_of_normalize_iso(self):
        self.assertEqual(__import__("trust").parse_as_of("2026-05-06"), "2026-05-06")

    def test_as_of_month_name_clamps_to_month_end(self):
        self.assertEqual(__import__("trust").parse_as_of("May 2026"), "2026-05-31")

    def test_as_of_none(self):
        self.assertIsNone(__import__("trust").parse_as_of(None))


if __name__ == "__main__":
    unittest.main()
