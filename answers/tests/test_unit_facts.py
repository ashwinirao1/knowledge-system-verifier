"""S1.5 unit tests: facts extractors — site links, programs, services,
wallet support, annual series."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import facts as F  # noqa: E402

JOIN_MD = """# Ready to Become Dupaco's Newest Member?

[Become a member](https://join.dupaco.com/)

[Continue my application](https://join.dupaco.com/login)

You can find us in Iowa, Illinois and Wisconsin. And if you're road-tripping,
you can also access your money at [Shared Branches](https://www.dupaco.com/contact#dupaco-locator-widget_1769206785258) and ATMs nationwide.

[Become a member](https://www.dupaco.com/about/join)
"""

HOMETART_MD = """Dubuque, Iowa—Dupaco Credit Union is partnering with the Federal Home
Loan Bank (FHLB) of Des Moines to help first-time homebuyers take the leap into
homeownership through the Home$tart program. This initiative provides up to
$15,000 in assistance, applied as a credit toward down payment and closing costs
for eligible buyers beginning their homeownership journey."""

PRIVACY_MD = """You can review and change your personal information located in any
accounts you have created with Us by logging into your account and making the
desired changes. You may also call Dupaco at 800-373-7600, send us an email at
service@dupaco.com, or visit a Dupaco branch in person to request access to or
correct any personal information that you have provided to us."""

PAYMENTS_MD = """# Leave your cards at home—your phone's got this

Add your Dupaco debit and credit cards to your phone's Apple Pay, Google Pay or
Samsung Pay for fast, secure and contactless checkouts.

Yes! Add one—or both—of your Dupaco cards to Apple Pay, Google Pay or Samsung
Pay. You can even set one as your default for faster checkouts."""

VTO_2023_MD = """In 2023 alone:

- Nearly **700 Dupaco employees** volunteered 7,260 hours (that's 10.4 hours
  per team member!).
- Dupaco employees served on **175** nonprofit boards and committees.
- **294 Dupaco employees** used a new paid benefit in 2023 called Volunteer
  Time Off, allowing them to take time off during the workday."""

VTO_2024_MD = """In 2024 alone:

- Dupaco's 602 employees volunteered a total of **6,187 hours.**
- Dupaco employees served on **170** nonprofit boards and committees
- **256 Dupaco employees** used a paid benefit in 2024 called Volunteer Time
  Off (or VTO), allowing them to take time off during the workday."""


class TestSiteLinks(unittest.TestCase):
    def test_join_cta_captured_clean(self):
        claims = F.extract_site_links(JOIN_MD)
        joins = [c for c in claims if c["tier_dims"]["role"] == "join_application"]
        self.assertEqual({c["tier_dims"]["url"] for c in joins}, {"https://join.dupaco.com/"})

    def test_login_path_is_not_the_join_answer(self):
        claims = F.extract_site_links(JOIN_MD)
        self.assertNotIn(
            "https://join.dupaco.com/login",
            {c["tier_dims"]["url"] for c in claims},
        )

    def test_locator_cta_query_fragment_stripped(self):
        claims = F.extract_site_links(JOIN_MD)
        locators = [c for c in claims if c["tier_dims"]["role"] == "branch_atm_locator"]
        self.assertEqual(
            {c["tier_dims"]["url"] for c in locators},
            {"https://www.dupaco.com/contact"},
        )

    def test_marketing_nav_join_link_ignored(self):
        # "Become a member" -> /about/join is navigation, not the application CTA
        claims = F.extract_site_links(JOIN_MD)
        self.assertNotIn("https://www.dupaco.com/about/join",
                         {c["tier_dims"]["url"] for c in claims})

    def test_unrelated_anchor_ignored(self):
        self.assertEqual(
            F.extract_site_links("[Fee-free ATM networks](https://www.dupaco.com/contact)"),
            [],
        )


class TestPrograms(unittest.TestCase):
    def test_hometart_value_and_dims(self):
        claims = F.extract_programs(HOMETART_MD)
        self.assertEqual(len(claims), 1)
        d = claims[0]["tier_dims"]
        self.assertEqual(d["program"], "home$tart")
        self.assertEqual(claims[0]["value"], 15000.0)
        self.assertEqual(claims[0]["value_text"], "15000")
        self.assertEqual(d["sponsor"], "fhlb")
        self.assertEqual(d["purpose"], "down payment and closing costs")
        self.assertEqual(d["audience"], "eligible buyers")

    def test_no_program_sentence_no_claim(self):
        self.assertEqual(F.extract_programs("Some unrelated marketing copy."), [])


class TestServices(unittest.TestCase):
    def test_channels_captured(self):
        claims = F.extract_services(PRIVACY_MD)
        self.assertEqual(len(claims), 1)
        d = claims[0]["tier_dims"]
        self.assertEqual(d["kind"], "service")
        self.assertTrue(d["login"])
        self.assertEqual(d["phone"], "800-373-7600")
        self.assertEqual(d["email"], "service@dupaco.com")
        self.assertTrue(d["branch"])

    def test_no_channels_no_claim(self):
        self.assertEqual(
            F.extract_services("You can review our privacy notice at your leisure."),
            [],
        )


class TestWallets(unittest.TestCase):
    def test_three_wallets_plus_default(self):
        claims = F.extract_wallets(PAYMENTS_MD)
        self.assertEqual(len(claims), 1)
        d = claims[0]["tier_dims"]
        self.assertEqual(
            d["wallets"].split("|"),
            ["Apple Pay", "Google Pay", "Samsung Pay"],
        )
        self.assertTrue(d["default_ok"])
        self.assertEqual(d["cards"], "debit and credit cards")

    def test_dims_stay_scalar(self):
        # wallets must be a string: nested lists break claim hashing in the ledger
        claims = F.extract_wallets(PAYMENTS_MD)
        for v in claims[0]["tier_dims"].values():
            self.assertNotIsInstance(v, (list, dict, tuple))

    def test_no_wallet_page(self):
        self.assertEqual(F.extract_wallets("No wallet mention here at all."), [])


class TestAnnualSeries(unittest.TestCase):
    def test_vto_2023(self):
        claims = F.extract_annual_series(VTO_2023_MD)
        vto = next(c for c in claims if c["tier_dims"]["series"] == "employees_vto")
        self.assertEqual(vto["tier_dims"]["year"], 2023)
        self.assertEqual(vto["value_text"], "294")

    def test_vto_2024_is_a_different_year(self):
        claims = F.extract_annual_series(VTO_2024_MD)
        vto = next(c for c in claims if c["tier_dims"]["series"] == "employees_vto")
        self.assertEqual(vto["value_text"], "256")

    def test_hours_and_boards(self):
        claims = F.extract_annual_series(VTO_2023_MD)
        series = {c["tier_dims"]["series"]: c["value_text"] for c in claims}
        self.assertEqual(series["volunteer_hours"], "7260")
        self.assertEqual(series["board_seats"], "175")

    def test_no_recap_no_claim(self):
        self.assertEqual(F.extract_annual_series("Nothing recapped here."), [])


class TestGates(unittest.TestCase):
    def test_extractor_short_circuits_on_empty_pages(self):
        self.assertEqual(F.extract_facts("A plain product page about savings rates."), [])


class TestEntityFacts(unittest.TestCase):
    """S2.4: the "who/what is Dupaco" fact class — routing number, branch
    count, Forbes ordinal, membership eligibility, student-loan product facts.
    Newsroom facts carry the article's publish date as their effective_date
    (bitemporal value-date)."""

    ROUTING_MD = (
        "Ask your employer if they offer direct deposit. You'll need Dupaco's "
        "routing number (273974581) and your checking account number."
    )

    COUNT_OLD_MD = (
        "March 10, 2026\n\nSome article body.\n\nABOUT DUPACO: It has over "
        "600 employees and 23 branch office locations."
    )
    COUNT_NEW_MD = (
        "April 23, 2026\n\nSome article body.\n\nABOUT DUPACO: It has over "
        "600 employees and 22 branch office locations."
    )
    COUNT_NODATE_MD = "It has over 600 employees and 23 branch office locations."

    FORBES_OLD_MD = (
        "July 18, 2023\n\nNational business magazine Forbes again named "
        "Dupaco one of the top-rated credit unions in America. It was the "
        "fourth time Forbes recognized Dupaco."
    )
    FORBES_NEW_MD = (
        "June 18, 2024\n\nNational business magazine Forbes again named "
        "Dupaco one of the top-rated credit unions in America. This was the "
        "fifth time Forbes recognized Dupaco."
    )

    JOIN_ELIG_MD = (
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

    def test_routing_number(self):
        claims = F.extract_entity_facts(self.ROUTING_MD)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["tier_dims"]["entity"], "routing_number")
        self.assertEqual(claims[0]["value_text"], "273974581")

    def test_branch_count_carries_publish_date(self):
        claims = F.extract_entity_facts(self.COUNT_NEW_MD)
        self.assertEqual(claims[0]["tier_dims"]["entity"], "branch_count")
        self.assertEqual(claims[0]["value_text"], "22")
        self.assertEqual(claims[0]["effective_date"], "2026-04-23")

    def test_branch_count_without_date_has_none(self):
        claims = F.extract_entity_facts(self.COUNT_NODATE_MD)
        self.assertEqual(claims[0]["value_text"], "23")
        self.assertIsNone(claims[0]["effective_date"])

    def test_forbes_ordinal(self):
        claims = F.extract_entity_facts(self.FORBES_NEW_MD)
        self.assertEqual(claims[0]["tier_dims"]["entity"], "forbes_recognition")
        self.assertEqual(claims[0]["value_text"], "fifth")
        self.assertEqual(claims[0]["effective_date"], "2024-06-18")

    def test_eligibility_with_link_markup(self):
        claims = F.extract_entity_facts(self.JOIN_ELIG_MD)
        self.assertEqual(claims[0]["tier_dims"]["entity"], "membership_eligibility")
        self.assertEqual(claims[0]["tier_dims"]["states"], "Iowa, Illinois and Wisconsin")

    def test_student_loan_product_fact(self):
        claims = F.extract_entity_facts(self.STUDENT_MD)
        self.assertEqual(claims[0]["tier_dims"]["entity"], "student_loan")
        self.assertIn("student loan", claims[0]["value_text"])

    def test_negatives(self):
        self.assertEqual(F.extract_entity_facts("The Hy-Vee branch will close March 31, 2026."), [])
        self.assertEqual(F.extract_entity_facts("Forbes is a magazine."), [])
        self.assertEqual(F.extract_entity_facts("Loans are subject to approval."), [])


if __name__ == "__main__":
    unittest.main()
