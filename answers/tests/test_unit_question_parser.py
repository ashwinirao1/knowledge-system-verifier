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


class TestChangeEventGrammar(unittest.TestCase):
    """S2.3: event and 'what changed' question grammar."""

    def test_when_does_branch_close_is_an_event(self):
        s = Q.parse_question("When does the Hy-Vee branch close?")
        self.assertEqual(s["family"], "branch")
        self.assertEqual(s["mode"], "event_when")
        self.assertEqual(s["branch_subject"], "hyvee")

    def test_still_open_is_event_status(self):
        s = Q.parse_question("Is the Hy-Vee branch still open today (October 2026)?")
        self.assertEqual(s["mode"], "event_status")
        self.assertEqual(s["branch_subject"], "hyvee")

    def test_hours_questions_are_not_hijacked(self):
        self.assertEqual(
            Q.parse_question("What are the hours for the Mullan Avenue branch?")["mode"],
            "hours_lobby",
        )
        self.assertEqual(
            Q.parse_question("Is the branch closed on Sunday?")["mode"],
            "hours_lobby",
        )

    def test_changes_between_months(self):
        s = Q.parse_question("What changed between May and September?")
        self.assertEqual(s["family"], "changes")
        self.assertEqual(s["window_from"], (None, 5))
        self.assertEqual(s["window_to"], (None, 9))
        self.assertEqual(s["label_from"], "May")
        self.assertEqual(s["label_to"], "September")

    def test_changes_since_month(self):
        s = Q.parse_question("What changed since June?")
        self.assertEqual(s["window_from"], (None, 6))
        self.assertIsNone(s["window_to"])

    def test_changes_iso_window(self):
        s = Q.parse_question("What rates changed between 2026-05 and 2026-09?")
        self.assertEqual(s["family"], "changes")
        self.assertEqual((s["window_from"], s["window_to"]), ((2026, 5), (2026, 9)))

    def test_changes_without_window_is_widest(self):
        s = Q.parse_question("What changed?")
        self.assertEqual(s["family"], "changes")
        self.assertIsNone(s["window_from"])
        self.assertIsNone(s["window_to"])

    def test_other_families_unchanged(self):
        # the changes trigger must not swallow other families' questions
        self.assertEqual(Q.parse_question("How many employees used VTO last year?")["family"], "facts")
        self.assertIsNone(Q.parse_question("What is the capital of France?") or None)


if __name__ == "__main__":
    unittest.main()
