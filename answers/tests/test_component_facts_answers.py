"""S1.5 component tests: facts answers — links, program, service, wallet,
annual series — end to end over a synthetic snapshot."""
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

JOIN_MD = """# Ready to Become Dupaco's Newest Member?

[Become a member](https://join.dupaco.com/)

You can also access your money at [Shared Branches](https://www.dupaco.com/contact#dupaco-locator-widget_1769206785258) and ATMs nationwide.
"""

HOMETART_MD = """Dubuque, Iowa—Dupaco Credit Union is partnering with the Federal Home
Loan Bank (FHLB) of Des Moines to help first-time homebuyers take the leap into
homeownership through the Home$tart program. This initiative provides up to
$15,000 in assistance, applied as a credit toward down payment and closing costs
for eligible buyers."""

PRIVACY_MD = """You can review and change your personal information located in any
accounts you have created with Us by logging into your account and making the
desired changes. You may also call Dupaco at 800-373-7600, send us an email at
service@dupaco.com, or visit a Dupaco branch in person."""

PAYMENTS_MD = """Add your Dupaco debit and credit cards to your phone's Apple Pay,
Google Pay or Samsung Pay for fast, secure and contactless checkouts.

Yes! Add one—or both—of your Dupaco cards to Apple Pay, Google Pay or Samsung
Pay. You can even set one as your default for faster checkouts."""

VTO_2023_MD = """In 2023 alone:

- **294 Dupaco employees** used a new paid benefit in 2023 called Volunteer Time
  Off, allowing them to take time off during the workday.
- Dupaco employees served on **175** nonprofit boards and committees."""

VTO_2024_MD = """In 2024 alone:

- **256 Dupaco employees** used a paid benefit in 2024 called Volunteer Time
  Off (or VTO), allowing them to take time off during the workday.
- Dupaco employees served on **170** nonprofit boards and committees."""


def snap():
    return Snapshot("X_2026-10-01", "2026-10-01", [
        Page("https://www.dupaco-int-test.org/about/join", "Join", JOIN_MD, "2026-10-01T00:00:00Z"),
        Page("https://www.dupaco-int-test.org/newsroom/hometart", "Home$tart", HOMETART_MD, "2026-10-01T00:00:00Z"),
        Page("https://www.dupaco-int-test.org/digital-privacy-policy", "Privacy", PRIVACY_MD, "2026-10-01T00:00:00Z"),
        Page("https://www.dupaco-int-test.org/mobile-payments", "Mobile payments", PAYMENTS_MD, "2026-10-01T00:00:00Z"),
        Page("https://www.dupaco-int-test.org/newsroom/vto-2023", "VTO 2023", VTO_2023_MD, "2026-10-01T00:00:00Z"),
        Page("https://www.dupaco-int-test.org/newsroom/vto-2024", "VTO 2024", VTO_2024_MD, "2026-10-01T00:00:00Z"),
    ])


class TestFactsAnswers(unittest.TestCase):
    def setUp(self):
        self.ks = SOL.build()
        self.ks.ingest(snap())

    def test_join_link(self):
        a = self.ks.answer("How do I join Dupaco online?")
        self.assertTrue(a.confident)
        self.assertIn("join.dupaco.com", a.text)

    def test_locator_link(self):
        a = self.ks.answer("What's the URL for Dupaco's branch and ATM locator?")
        self.assertTrue(a.confident)
        self.assertIn("dupaco.com/contact", a.text)
        self.assertNotIn("branch-hours", a.text)

    def test_program_fact(self):
        a = self.ks.answer("What is Dupaco's Home$tart program?")
        self.assertTrue(a.confident)
        self.assertIn("15,000", a.text)
        self.assertIn("down payment and closing costs", a.text)

    def test_program_binding_blocks_unrelated_program(self):
        # the only program on file is Home$tart: another named program refuses
        a = self.ks.answer("What is Dupaco's Wildwood Farm program?")
        self.assertFalse(a.confident)
        self.assertNotIn("15,000", a.text)
        self.assertNotIn("Home$tart", a.text)

    def test_update_contact_channels(self):
        a = self.ks.answer("How can I update my contact information with Dupaco?")
        self.assertTrue(a.confident)
        self.assertIn("800-373-7600", a.text)
        self.assertNotIn("member number", a.text)

    def test_wallet_list_complete(self):
        a = self.ks.answer("Can I add my Dupaco debit and credit cards to a mobile wallet?")
        self.assertTrue(a.confident)
        for name in ("Apple Pay", "Google Pay", "Samsung Pay"):
            self.assertIn(name, a.text)

    def test_series_unbound_year_answers_chronologically(self):
        a = self.ks.answer("How many Dupaco employees used Volunteer Time Off last year?")
        self.assertTrue(a.confident)
        self.assertIn("294", a.text)
        self.assertIn("256", a.text)
        self.assertIn("2023", a.text)
        self.assertIn("2024", a.text)

    def test_series_bound_year_answers_only_that_year(self):
        a = self.ks.answer("How many Dupaco employees used Volunteer Time Off in 2024?")
        self.assertTrue(a.confident)
        self.assertIn("256", a.text)
        self.assertNotIn("294", a.text)

    def test_series_missing_year_refuses_digit_free(self):
        a = self.ks.answer("How many Dupaco employees used Volunteer Time Off in 2019?")
        self.assertFalse(a.confident)
        import re
        self.assertFalse(re.search(r"\d", a.text), a.text)


class TestEntityFactAnswers(unittest.TestCase):
    """S2.4: the "who/what is Dupaco" fact class end-to-end. The count and
    Forbes answers resolve via the trust stack on publish dates — freshest
    published statement wins, no special-casing."""

    COUNT_MARCH_MD = (
        "March 10, 2026\n\nSome article body about financial stress.\n\n"
        "ABOUT DUPACO: It has over 600 employees and 23 branch office locations."
    )
    COUNT_APRIL_MD = (
        "April 23, 2026\n\nSome article body about homebuying.\n\n"
        "ABOUT DUPACO: It has over 600 employees and 22 branch office locations."
    )
    FORBES_2023_MD = (
        "July 18, 2023\n\nNational business magazine Forbes again named "
        "Dupaco one of the top-rated credit unions in America. It was the "
        "fourth time Forbes recognized Dupaco."
    )
    FORBES_2024_MD = (
        "June 18, 2024\n\nNational business magazine Forbes again named "
        "Dupaco one of the top-rated credit unions in America. This was the "
        "fifth time Forbes recognized Dupaco."
    )
    ROUTING_MD = (
        "You'll need Dupaco's routing number (273974581) and your checking "
        "account number to set up direct deposit."
    )
    ELIG_MD = (
        "You can find us in Iowa, Illinois and Wisconsin. And if you're "
        "road-tripping, you can also access your money at shared branches.\n\n"
        "You're Eligible to Join If Any of These Sound Like You\n\n"
        "- You live or work within our [charter area](https://maps.example.org/area.jpg).\n"
    )
    STUDENT_MD = (
        "Student Loans & Refinancing\n\nWhether you need to fill the funding "
        "gap for college, we have flexible options to help.\n\n#### Flexible "
        "Repayment\n\nDefer full payments while in school.\n\n#### Keep More "
        "Money\n\nBenefit from $0 origination fees, no prepayment penalties, "
        "and favorable rates."
    )

    def _ks(self):
        ks = SOL.build()
        ks.ingest(Snapshot("E_2026-09-28", "2026-09-28", [
            Page("https://www.dupaco-int-test.org/newsroom/march", "March",
                 self.COUNT_MARCH_MD, "2026-09-28T00:00:00Z"),
            Page("https://www.dupaco-int-test.org/newsroom/april", "April",
                 self.COUNT_APRIL_MD, "2026-09-28T00:00:00Z"),
            Page("https://www.dupaco-int-test.org/newsroom/forbes-2023", "Forbes 2023",
                 self.FORBES_2023_MD, "2026-09-28T00:00:00Z"),
            Page("https://www.dupaco-int-test.org/newsroom/forbes-2024", "Forbes 2024",
                 self.FORBES_2024_MD, "2026-09-28T00:00:00Z"),
            Page("https://www.dupaco-int-test.org/checking", "Checking",
                 self.ROUTING_MD, "2026-09-28T00:00:00Z"),
            Page("https://www.dupaco-int-test.org/about/join", "Join",
                 self.ELIG_MD, "2026-09-28T00:00:00Z"),
            Page("https://www.dupaco-int-test.org/student-loans", "Student loans",
                 self.STUDENT_MD, "2026-09-28T00:00:00Z"),
        ]))
        return ks

    def test_routing_number(self):
        a = self._ks().answer("What is Dupaco's routing number?")
        self.assertTrue(a.confident)
        self.assertIn("273974581", a.text)

    def test_routing_number_replay(self):
        a = self._ks().answer("Can you repeat the routing number?")
        self.assertTrue(a.confident)
        self.assertIn("273974581", a.text)

    def test_branch_count_freshest_publish_date_wins(self):
        # the 22-vs-23 dup-073 shape: two boilerplate statements, the April one
        # is fresher (the Hy-Vee branch closed March 31 in the real corpus)
        a = self._ks().answer("How many branches does Dupaco have?")
        self.assertTrue(a.confident)
        self.assertIn("22", a.text)
        self.assertNotIn("23", a.text)

    def test_forbes_freshest_ordinal_wins(self):
        a = self._ks().answer("What recognition has Dupaco received from Forbes?")
        self.assertTrue(a.confident)
        self.assertIn("fifth", a.text)
        self.assertNotIn("fourth", a.text)

    def test_membership_eligibility_states(self):
        a = self._ks().answer("Who is eligible to become a Dupaco member?")
        self.assertTrue(a.confident)
        for st in ("Iowa", "Illinois", "Wisconsin"):
            self.assertIn(st, a.text)

    def test_student_loan_options(self):
        a = self._ks().answer("I'm a student going to a new university - do you have any loan options with flexibility?")
        self.assertTrue(a.confident)
        self.assertIn("student loan", a.text.lower())

    def test_missing_entity_refuses_digit_free(self):
        ks = SOL.build()
        ks.ingest(Snapshot("E2_2026-09-28", "2026-09-28", [
            Page("https://www.dupaco-int-test.org/plain", "Plain",
                 "A plain page about savings.", "2026-09-28T00:00:00Z"),
        ]))
        a = ks.answer("What is Dupaco's routing number?")
        self.assertFalse(a.confident)
        self.assertNotRegex(a.text, r"\d")


class TestFactsStaysOutOfConflicts(unittest.TestCase):
    def test_no_facts_conflicts(self):
        ks = SOL.build()
        ks.ingest(snap())
        conflicts = ks.conflicts()
        for c in conflicts:
            self.assertNotIn("Apple Pay", " | ".join(c.values or []))
            self.assertNotIn("join.dupaco.com", c.topic or "")


if __name__ == "__main__":
    unittest.main()
