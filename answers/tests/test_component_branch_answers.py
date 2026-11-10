"""S1.4 component tests: branch answers — lobby/drive-up hours, address,
Hy-Vee alternatives, schedules-differ question."""
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

HOURS_A = """Newest Learning Lab

Branch hours are:

**Lobby**

Monday-Thursday: 8:30 a.m.-5 p.m.

Friday: 8:30 a.m.-6 p.m.

Saturday: 8:30 a.m.-12:30 p.m.

Sunday: Closed

**Drive-up**

Monday-Friday: 8 a.m.-6 p.m.

Saturday: 8 a.m.-1 p.m.

Sunday: ATM only
"""

HOURS_B = """Expanded branch

The Platteville Dupaco branch is located at 1100 E. Business Highway 151.

Branch hours are:

**Lobby** Monday-Thursday: 8:30 a.m.-5 p.m.

Friday: 8:30 a.m.-5:30 p.m.

Saturday: 9 a.m.-noon

Sunday: Closed

**Drive-up** Monday-Friday: 8 a.m.-6 p.m.

Saturday: 9 a.m.-noon

Sunday: ATM only
"""

LOCATOR = """### Dupaco Credit Union

Dupaco Branch

11375 Oldenburg Ln., Galena, IL, 61036

Closed
"""

NOTICE = """Dupaco has made the decision not to renew its lease at the branch
inside the South Locust St. Hy-Vee store. Members who frequent the Hy-Vee branch
already can access the same services at Dupaco full-service branches at Key West
and Sycamore Street.
"""


def snap():
    return Snapshot("X_2026-10-01", "2026-10-01", [
        Page("https://www.example.org/lab", "Learning Lab", HOURS_A, "2026-10-01T00:00:00Z"),
        Page("https://www.example.org/expanded", "Expanded Branch", HOURS_B, "2026-10-01T00:00:00Z"),
        Page("https://www.example.org/contact", "Contact", LOCATOR, "2026-10-01T00:00:00Z"),
        Page("https://www.example.org/news", "News", NOTICE, "2026-10-01T00:00:00Z"),
    ])


class TestBranchAnswers(unittest.TestCase):
    def setUp(self):
        self.ks = SOL.build()
        self.ks.ingest(snap())

    def test_general_lobby_hours(self):
        a = self.ks.answer("What are Dupaco's general lobby hours?")
        self.assertIn("8:30", a.text)
        self.assertIn("vary", a.text.lower())

    def test_lobby_hours_do_not_demand_a_zip(self):
        a = self.ks.answer("What are your lobby hours?")
        self.assertIn("8:30", a.text)
        self.assertNotIn("ZIP code", a.text)

    def test_drive_up_hours(self):
        a = self.ks.answer("What are the drive-up hours?")
        self.assertIn("8 a.m.", a.text)
        self.assertIn("6 p.m.", a.text)

    def test_specific_branch_address(self):
        a = self.ks.answer("What is the address of the Galena Branch?")
        self.assertIn("11375 Oldenburg", a.text)
        self.assertIn("61036", a.text)
        self.assertNotIn("unable to find", a.text.lower())

    def test_hyvee_alternatives_named(self):
        a = self.ks.answer("Where can Hy-Vee branch members go for full-service banking?")
        self.assertIn("Key West", a.text)
        self.assertIn("Sycamore", a.text)
        self.assertNotIn("CO-OP Shared Branch", a.text)

    def test_branches_differ_answered_no(self):
        a = self.ks.answer("Do all Dupaco branches keep the same lobby hours?")
        self.assertTrue(a.text.startswith("No"))
        self.assertIn("12:30", a.text)
        self.assertIn("noon", a.text)

    def test_named_branch_not_on_file_refuses_digit_free(self):
        """Hours for a branch that is not on file must not be filled with
        other branches' schedules (that would fabricate a fact for it)."""
        a = self.ks.answer("Can you give me the lobby hours for the Mullan Avenue branch?")
        self.assertFalse(a.confident)
        self.assertNotRegex(a.text, r"\d")
        self.assertNotIn("Platteville", a.text)

    def test_named_branch_on_file_answers_it(self):
        a = self.ks.answer("Can you give me the lobby hours for the Platteville branch?")
        self.assertTrue(a.confident)
        self.assertIn("9 a.m.", a.text)
        self.assertIn("noon", a.text)
        self.assertNotIn("12:30", a.text)  # other branches' schedule must not leak

    def test_deterministic_repeat(self):
        q = "What are the drive-up hours?"
        self.assertEqual(self.ks.answer(q).text, self.ks.answer(q).text)


if __name__ == "__main__":
    unittest.main()
