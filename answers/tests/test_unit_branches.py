"""S1.4 unit tests: branch prose extractors — hours blocks, locator addresses,
relocation notices."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import branches as B  # noqa: E402

HOURS_MD = """The Platteville Dupaco branch is located at 1100 E. Business Highway 151.

Branch hours are:

**Lobby** Monday-Thursday: 8:30 a.m.–5 p.m.

Friday: 8:30 a.m.–5:30 p.m.

Saturday: 9 a.m.–noon

Sunday: Closed

**Drive-up** Monday-Friday: 8 a.m.–6 p.m.

Saturday: 9 a.m.–noon

Sunday: ATM only
"""

LOCATOR_MD = """### Dupaco Credit Union

Dupaco Branch

11375 Oldenburg Ln., Galena, IL, 61036

Closed

Drive Up Window · 24-hour ATM

### Dupaco ATM @ Fareway

Surcharge-Free ATM

2050 JFK Rd., Dubuque, IA, 52001
"""

NOTICE_MD = """“Members who frequent the Hy-Vee branch already can access the same
services at Dupaco full-service branches at Key West and Sycamore Street,” said Hearn.
"""


class TestHoursBlocks(unittest.TestCase):
    def test_lobby_and_drive_up_both_captured(self):
        claims = B.extract_branch_hours(HOURS_MD)
        channels = {c["tier_dims"]["channel"] for c in claims}
        self.assertEqual(channels, {"lobby", "drive_up"})

    def test_inline_first_entry(self):
        claims = B.extract_branch_hours(HOURS_MD)
        lobby = next(c for c in claims if c["tier_dims"]["channel"] == "lobby")
        self.assertIn("Monday-Thursday: 8:30 a.m.", lobby["tier_dims"]["schedule"])

    def test_branch_name_trimmed(self):
        claims = B.extract_branch_hours(HOURS_MD)
        lobby = next(c for c in claims if c["tier_dims"]["channel"] == "lobby")
        self.assertEqual(lobby["tier_dims"]["branch"], "platteville")

    def test_open_ended_pan_days_normalized(self):
        claims = B.extract_branch_hours(HOURS_MD)
        lobby = next(c for c in claims if c["tier_dims"]["channel"] == "lobby")
        self.assertIn("Monday-Thursday", lobby["tier_dims"]["schedule"])
        self.assertNotIn("–", lobby["tier_dims"]["schedule"])

    def test_prose_without_anchor_is_ignored(self):
        md = """Some page

**Lobby**

Monday: 8:30 a.m.-5 p.m.
"""
        self.assertEqual(B.extract_branch_hours(md), [])


class TestLocatorAddresses(unittest.TestCase):
    def test_branch_address_parsed_with_zip(self):
        claims = B.extract_branch_addresses(LOCATOR_MD)
        galena = [c for c in claims if c["tier_dims"]["city"] == "galena"]
        self.assertEqual(len(galena), 1)
        d = galena[0]["tier_dims"]
        self.assertEqual(d["zip"], "61036")
        self.assertEqual(d["state"], "IL")
        self.assertIn("11375 Oldenburg", d["address_display"])

    def test_atm_blocks_are_not_branches(self):
        claims = B.extract_branch_addresses(LOCATOR_MD)
        self.assertEqual(len(claims), 1)  # JFK Rd. is an ATM listing


class TestNotices(unittest.TestCase):
    def test_hyvee_alternatives(self):
        claims = B.extract_branch_notices(NOTICE_MD)
        self.assertEqual(len(claims), 1)
        alts = claims[0]["tier_dims"]["alternatives"]
        self.assertEqual(alts, "Key West and Sycamore Street")

    def test_no_hyvee_no_notice(self):
        self.assertEqual(B.extract_branch_notices("Nothing here."), [])


class TestBranchEvents(unittest.TestCase):
    """S2.3: dated branch events from prose — the closure announcement shape.
    value_text keeps the site's own rendering ("March 31, 2026"); event_date
    is the ISO form for temporal logic."""

    ANNOUNCEMENT = (
        "Dupaco has made the decision not to renew its lease at the branch "
        "inside the South Locust St. Hy-Vee store in Dubuque.\n\n"
        "This location will close March 31, 2026. All Dupaco Hy-Vee branch "
        "employees will remain with the credit union.\n"
    )

    def test_closure_event_extracted(self):
        evs = B.extract_branch_events(self.ANNOUNCEMENT)
        self.assertEqual(len(evs), 1)
        d = evs[0]["tier_dims"]
        self.assertEqual(d["kind"], "branch_event")
        self.assertEqual(d["subject"], "hyvee_locust")
        self.assertEqual(d["event"], "close")
        self.assertEqual(d["event_date"], "2026-03-31")
        self.assertEqual(evs[0]["value_text"], "March 31, 2026")

    def test_duplicate_statement_counts_once(self):
        evs = B.extract_branch_events(self.ANNOUNCEMENT + self.ANNOUNCEMENT)
        self.assertEqual(len(evs), 1)

    def test_no_subject_no_event(self):
        # a closure sentence with no recognizable branch on the page binds to
        # nothing — we never invent a subject
        self.assertEqual(B.extract_branch_events("This location will close March 31, 2026."), [])

    def test_no_event_no_claims(self):
        self.assertEqual(B.extract_branch_events("The Hy-Vee branch is open."), [])


if __name__ == "__main__":
    unittest.main()
