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


class TestEntityGrammar(unittest.TestCase):
    """S2.4: entity-fact question grammar."""

    def test_how_many_branches(self):
        s = Q.parse_question("How many branches does Dupaco have?")
        self.assertEqual(s["family"], "facts")
        self.assertEqual(s["mode"], "entity")
        self.assertEqual(s["entity"], "branch_count")

    def test_routing_number_direct_and_replay(self):
        for q in ("What is Dupaco's routing number?",
                  "Can you repeat the routing number?"):
            s = Q.parse_question(q)
            self.assertEqual(s["entity"], "routing_number", q)

    def test_forbes(self):
        s = Q.parse_question("What recognition has Dupaco received from Forbes?")
        self.assertEqual(s["entity"], "forbes_recognition")

    def test_eligibility_beats_join_link(self):
        # "who is eligible ... become a member" asks for the RULE, not the URL
        s = Q.parse_question("Who is eligible to become a Dupaco member?")
        self.assertEqual(s["mode"], "entity")
        self.assertEqual(s["entity"], "membership_eligibility")

    def test_student_loan_non_adjacent(self):
        s = Q.parse_question("I'm a student going to a new university - do you have any loan options with flexibility?")
        self.assertEqual(s["entity"], "student_loan")

    def test_vto_series_still_wins_over_branch_count(self):
        s = Q.parse_question("How many employees used VTO last year?")
        self.assertEqual(s["mode"], "series")


class TestCertificateSynonyms(unittest.TestCase):
    """S3.1: share certificate = CD; term-anchored bare 'special'. The hidden
    eval rewords product nouns — the certificate family must catch its
    everyday synonyms without over-triggering on unrelated 'special'."""

    def test_bare_cd(self):
        for q, term in (("What is the APY on a 12-month CD?", 12),
                        ("What are today's CD rates?", None),
                        ("Do you offer CDs?", None)):
            s = Q.parse_question(q)
            self.assertEqual(s["family"], "certificate", q)
            self.assertEqual(s["term_months"], term, q)

    def test_cd_with_ira(self):
        s = Q.parse_question("Do you offer CDs and IRAs?")
        self.assertEqual(s["family"], "certificate")
        self.assertTrue(s["ira"])

    def test_term_anchored_special_without_cert_noun(self):
        s = Q.parse_question("What is the current rate on the 17-month special?")
        self.assertEqual(s["family"], "certificate")
        self.assertEqual(s["term_months"], 17)
        self.assertTrue(s["special"])

    def test_term_anchored_jumbo_special(self):
        s = Q.parse_question("What does the 10-month jumbo special pay?")
        self.assertEqual(s["family"], "certificate")
        self.assertEqual(s["term_months"], 10)
        self.assertTrue(s["special"])
        self.assertTrue(s["jumbo"])

    def test_bare_special_does_not_trigger_certificate(self):
        # no term anchor → not a certificate question (no over-trigger)
        self.assertNotEqual(
            Q.parse_question("Are there any special requirements to open an account?")["family"],
            "certificate",
        )
        self.assertIsNone(Q.parse_question("What special offers do you have for new members?"))

    def test_share_certificate_still_parses(self):
        s = Q.parse_question("What is the rate on a 12-month share certificate?")
        self.assertEqual(s["family"], "certificate")
        self.assertEqual(s["term_months"] , 12)

    def test_cd_rates_link_reaches_facts_link_path(self):
        # documented facts case the pre-S3.1 cert regex could not reach
        s = Q.parse_question("Where is the CD rates link?")
        self.assertEqual(s["family"], "facts")
        self.assertEqual(s["mode"], "link")
        self.assertEqual(s["link_family"], "certificate")


class TestParaphraseGrammar(unittest.TestCase):
    """S3.3: trigger extensions found by the paraphrase self-benchmark
    (78 hand-reworded variants of the public items; 100% same-claim)."""

    def test_tier_balance_is_between(self):
        s = Q.parse_question("What dividend rate do I get on Share Savings if my balance is between $10,000 and $24,999?")
        self.assertEqual(s["mode"], "tier")
        self.assertEqual(s["tier"], (10000.0, 24999.0))

    def test_tier_bounds_with_and(self):
        s = Q.parse_question("Share Savings pays what dividend rate on a $10,000 to $24,999 balance?")
        self.assertEqual(s["tier"], (10000.0, 24999.0))

    def test_branch_count_total_number_of(self):
        s = Q.parse_question("What's the total number of Dupaco branches?")
        self.assertEqual((s["family"], s["mode"], s.get("entity")), ("facts", "entity", "branch_count"))

    def test_phone_number_of_branch_does_not_count(self):
        # "number of" must be quantified — a phone number is not a count
        s = Q.parse_question("What's the phone number of the Dubuque branch?")
        self.assertNotEqual((s or {}).get("entity"), "branch_count")

    def test_event_when_closure_date(self):
        s = Q.parse_question("What's the closure date for the Hy-Vee branch?")
        self.assertEqual(s["mode"], "event_when")
        self.assertEqual(s["branch_subject"], "hyvee")  # tempered capture

    def test_event_when_is_closing(self):
        s = Q.parse_question("When is the Hy-Vee branch closing?")
        self.assertEqual(s["mode"], "event_when")
        self.assertEqual(s["branch_subject"], "hyvee")

    def test_event_status_open_as_of(self):
        s = Q.parse_question("Is the Hy-Vee branch open as of October 2026?")
        self.assertEqual(s["mode"], "event_status")

    def test_event_status_stay_open_location(self):
        s = Q.parse_question("Did the Hy-Vee location stay open in October 2026?")
        self.assertEqual(s["mode"], "event_status")
        self.assertEqual(s["branch_subject"], "hyvee")

    def test_branch_open_on_weekday_is_hours_not_status(self):
        s = Q.parse_question("Is the Hy-Vee branch open on Sundays?")
        self.assertEqual(s["mode"], "hours_lobby")

    def test_branch_on_street_is_named_branch(self):
        s = Q.parse_question("What are the lobby hours for a branch on Mullan Avenue?")
        self.assertEqual(s["family"], "branch")
        self.assertEqual(s["mode"], "hours_lobby")
        self.assertEqual(s["branch_name"], "mullan avenue")

    def test_link_which_page_lists_cd_rates(self):
        s = Q.parse_question("Which page lists your CD rates?")
        self.assertEqual(s["mode"], "link")
        self.assertEqual(s["link_family"], "certificate")

    def test_link_where_on_your_site_locator(self):
        s = Q.parse_question("Where on your site is the branch and ATM locator?")
        self.assertEqual(s["link_role"], "branch_atm_locator")

    def test_highest_top_and_the_most(self):
        for q in ("What's the top APY on Share Savings, and at what balance?",
                  "Which Share Savings balance tier earns the most?"):
            self.assertEqual(Q.parse_question(q)["mode"], "highest", q)

    def test_wallet_named_wallets_without_wallet_word(self):
        s = Q.parse_question("Does Dupaco support adding debit and credit cards to Apple Pay, Google Pay or Samsung Pay?")
        self.assertEqual((s["family"], s["mode"]), ("facts", "wallet"))

    def test_eligibility_what_do_i_need(self):
        s = Q.parse_question("What do I need to be eligible for Dupaco membership?")
        self.assertEqual(s["entity"], "membership_eligibility")

    def test_eligibility_can_anyone_join(self):
        s = Q.parse_question("Can anyone join Dupaco, or do you have to live in the charter area?")
        self.assertEqual(s["entity"], "membership_eligibility")

    def test_students_plural(self):
        s = Q.parse_question("Do you have loan options for students heading to college?")
        self.assertEqual(s["entity"], "student_loan")

    def test_link_ask_beats_eligibility(self):
        # S3.4 group-split fix: an explicit link/url/page ask wants the URL,
        # even when the sentence also contains "become a (Dupaco) member"
        s = Q.parse_question("What's the link to become a Dupaco member online?")
        self.assertEqual((s["family"], s["mode"], s["link_role"]),
                         ("facts", "link", "join_application"))

    def test_eligibility_without_link_ask_still_the_rule(self):
        # regression guard for the link-ask exception above
        s = Q.parse_question("Who is eligible to become a Dupaco member?")
        self.assertEqual((s["mode"], s["entity"]),
                         ("entity", "membership_eligibility"))

    def test_all_same_every_dupaco_branch(self):
        # S3.4 group-split fix: "every <words> branch" is the same-hours ask
        s = Q.parse_question("Are lobby hours the same at every Dupaco branch?")
        self.assertEqual(s["mode"], "hours_same")


if __name__ == "__main__":
    unittest.main()
