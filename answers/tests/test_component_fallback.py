"""S4.1 component tests: the fallback inside the answer path — fires only on
total grammar misses, never overrides informed refusals, filters by as_of."""
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

FEE_MD = """# Fees

### Rate and Fee Schedule

Miscellaneous fees and charges:

| Item | Fee |
| --- | --- |
| Stop payment | $30.00 |
| Domestic wire | $25.00 |
"""


def _snap(snap_id, day, extra_pages=()):
    return Snapshot(snap_id, day, [
        Page("https://www.example.org/fees", "Fees", FEE_MD, f"{day}T00:00:00Z"),
        Page("https://www.example.org/plain", "Plain",
             "A plain page about the credit union's history and community work.",
             f"{day}T00:00:00Z"),
        *extra_pages,
    ])


class TestFallbackPath(unittest.TestCase):
    def _ks(self):
        ks = SOL.build()
        ks.ingest(_snap("F1_2026-09-28", "2026-09-28"))
        return ks

    def test_grammar_miss_quotes_published_row(self):
        # parse -> None: "stop payment" matches no family grammar
        a = self._ks().answer("What do you charge for a stop payment?")
        self.assertTrue(a.confident)
        self.assertIn("$30.00", a.text)
        self.assertEqual(a.sources[0].url, "https://www.example.org/fees")

    def test_fallback_is_deterministic(self):
        ks = self._ks()
        a1 = ks.answer("What do you charge for a stop payment?")
        a2 = ks.answer("What do you charge for a stop payment?")
        self.assertEqual(a1.text, a2.text)
        self.assertEqual(a1.sources[0].url, a2.sources[0].url)

    def test_gibberish_refuses_digit_free(self):
        a = self._ks().answer("What is the capital of France?")
        self.assertFalse(a.confident)
        self.assertNotRegex(a.text, r"\d")

    def test_informed_refusal_not_overridden(self):
        # the grammar PARSES this (loans family) and the site has no claims:
        # the refusal is informed — the fallback must never fire on it, even
        # though the index holds matching text with numbers
        ks = SOL.build()
        loanish = Page(
            "https://www.example.org/loan-prose", "Loan prose",
            "Members sometimes ask about 36 month personal loan rates around "
            "9.99% APR in our lending guides.",
            "2026-09-28T00:00:00Z",
        )
        ks.ingest(_snap("F2_2026-09-28", "2026-09-28", extra_pages=[loanish]))
        a = ks.answer("What is the APR on a 36-month personal loan?")
        self.assertFalse(a.confident)
        self.assertNotRegex(a.text, r"\d")

    def test_as_of_view_filters_fallback(self):
        ks = SOL.build()
        ks.ingest(_snap("F3_2026-03-01", "2026-03-01"))
        ks.ingest(Snapshot("F3_2026-09-28", "2026-09-28", [
            Page("https://www.example.org/plain", "Plain",
                 "A plain page about the credit union's history and community work.",
                 "2026-09-28T00:00:00Z"),
        ]))
        # view = latest: the fee page is gone from the site -> refuse
        a = ks.answer("What do you charge for a stop payment?")
        self.assertFalse(a.confident)
        # view = the old snapshot: the fee page existed then -> quote it
        a = ks.answer("What do you charge for a stop payment?", as_of="2026-03-01")
        self.assertTrue(a.confident)
        self.assertIn("$30.00", a.text)
        self.assertEqual(a.sources[0].snapshot_id, "F3_2026-03-01")


if __name__ == "__main__":
    unittest.main()
