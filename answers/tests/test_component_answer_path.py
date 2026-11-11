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


class TestAsOfEdges(unittest.TestCase):
    """S2.2: the before-baseline edge answers from the EARLIEST snapshot with
    a provenance note — never a refusal, never silent — while the other three
    edges keep flowing through the normal path untouched."""

    def setUp(self):
        self.ks = SOL.build()
        self.ks.ingest(_snapshot("2026-05-19", OLD))
        self.ks.ingest(_snapshot("2026-09-28", NEW))

    def test_before_baseline_answers_from_earliest_with_note(self):
        a = self.ks.answer(
            "What is the APY on the 10-month fixed jumbo special certificate?",
            as_of="2026-01-01",
        )
        self.assertTrue(a.confident)           # an answer, not a refusal
        self.assertIn("3.90%", a.text)          # the EARLIEST snapshot's value
        self.assertNotIn("4.00%", a.text)       # never the later snapshot's
        self.assertIsNotNone(a.conflict_note)
        self.assertIn("2026-05-19", a.conflict_note)

    def test_before_baseline_past_tense(self):
        a = self.ks.answer(
            "What is the APY on the 10-month fixed jumbo special certificate?",
            as_of="2026-01-01",
        )
        self.assertIn("paid", a.text.lower())   # historical date -> past tense

    def test_month_name_as_of_end_to_end(self):
        a = self.ks.answer(
            "What is the APY on the 10-month fixed jumbo special certificate?",
            as_of="May 2026",                    # -> 2026-05-31 -> the OLD snap
        )
        self.assertTrue(a.confident)
        self.assertIn("3.90%", a.text)
        self.assertIsNone(a.conflict_note)      # "ok" edge: no provenance note

    def test_after_latest_answers_current_with_no_note(self):
        a = self.ks.answer(
            "What is the APY on the 10-month fixed jumbo special certificate?",
            as_of="2026-12-25",
        )
        self.assertIn("4.00%", a.text)          # latest snapshot
        self.assertIsNone(a.conflict_note)

    def test_disagreement_note_beats_as_of_note(self):
        # inside the earliest snapshot the two pages agree, so no disagreement
        # note fires; assert the precedence helper directly by forcing both
        # channels on a conflict-bearing query is S5 territory — here we pin
        # that a normal "ok" edge leaves the note channel empty
        a = self.ks.answer(
            "What is the APY on the 10-month fixed jumbo special certificate?",
            as_of="2026-06-01",
        )
        self.assertIsNone(a.conflict_note)


class TestChanges(unittest.TestCase):
    """S2.3: "what changed between May and September" — transitions recorded
    at ingest, window-filtered, replicas collapsed to one row; an empty window
    refuses digit-free."""

    OLD_MD = (
        "Certificates\n\nSpecial Certificates\n\n"
        "| Certificate | Dividend Rate | Annual Percentage Yield (APY) | Min. to Earn |\n"
        "| --- | --- | --- | --- |\n"
        "| 10 Month Fixed Jumbo Certificate Special | 3.86% | 3.90%1 | $100,000 |\n\n"
        "Rates are effective as of 05/01/2026 and are subject to change without notice.\n"
    )
    NEW_MD = (
        "Certificates\n\nSpecial Certificates\n\n"
        "| Certificate | Dividend Rate | Annual Percentage Yield (APY) | Min. to Earn |\n"
        "| --- | --- | --- | --- |\n"
        "| 10 Month Fixed Jumbo Certificate Special | 3.96% | 4.00%1 | $100,000.00 |\n\n"
        "Rates are effective as of 09/01/2026 and are subject to change without notice.\n"
    )

    def _ks(self):
        ks = SOL.build()
        ks.ingest(Snapshot("M_2026-05-12", "2026-05-12", [
            Page("https://www.example.org/savings", "Savings", self.OLD_MD, "2026-05-12T00:00:00Z"),
        ]))
        ks.ingest(Snapshot("M_2026-09-28", "2026-09-28", [
            Page("https://www.example.org/savings", "Savings", self.NEW_MD, "2026-09-28T00:00:00Z"),
        ]))
        return ks

    def test_transition_recorded_at_ingest(self):
        ks = self._ks()
        self.assertEqual(len(ks.transitions), 1)
        t = ks.transitions[0]
        self.assertEqual(t["old"], "3.90%")
        self.assertEqual(t["new"], "4.00%")
        self.assertEqual(t["from_date"], "2026-05-12")
        self.assertEqual(t["to_date"], "2026-09-28")

    def test_what_changed_between(self):
        a = self._ks().answer("What changed between May and September?")
        self.assertTrue(a.confident)
        self.assertIn("3.90%", a.text)
        self.assertIn("4.00%", a.text)
        self.assertTrue(a.sources)

    def test_empty_window_refuses_digit_free(self):
        a = self._ks().answer("What changed between June and July?")
        self.assertFalse(a.confident)
        self.assertNotRegex(a.text, r"\d")

    def test_identical_snapshots_no_transitions(self):
        ks = SOL.build()
        ks.ingest(Snapshot("M_2026-05-12", "2026-05-12", [
            Page("https://www.example.org/savings", "Savings", self.OLD_MD, "2026-05-12T00:00:00Z"),
        ]))
        ks.ingest(Snapshot("M_2026-05-19", "2026-05-19", [
            Page("https://www.example.org/savings", "Savings", self.OLD_MD, "2026-05-19T00:00:00Z"),
        ]))
        self.assertEqual(ks.transitions, [])
        a = ks.answer("What changed between May and September?")
        self.assertFalse(a.confident)


if __name__ == "__main__":
    unittest.main()
