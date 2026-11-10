"""S0.2 unit tests: certificate row-grammar (tier_dims extraction)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import certificates as C  # noqa: E402


def make_table(rows, section="Special Certificates", headers=("Certificate", "Dividend Rate", "Annual Percentage Yield (APY)", "Min. to Earn")):
    body = ["| " + " | ".join(headers) + " |", "| --- | --- | --- | --- |"]
    body += ["| " + " | ".join(r) + " |" for r in rows]
    text = section + "\n\n" + "\n".join(body)
    tabs = __import__("tables").parse_tables(text)
    return tabs[0]


class TestRowGrammar(unittest.TestCase):
    def test_plain_special_row(self):
        tab = make_table([["17 Month Fixed Certificate Special", "4.06%", "4.10%2", "$1,000.00"]])
        claims = C.extract_certificates(tab)
        apy = [cl for cl in claims if cl["metric"] == "apy"]
        self.assertEqual(len(apy), 1)
        dims = apy[0]["tier_dims"]
        self.assertEqual(dims["term_months"], 17)
        self.assertFalse(dims["jumbo"])
        self.assertTrue(dims["special"])

    def test_jumbo_special_row(self):
        tab = make_table([["17 Month Fixed Jumbo Certificate Special", "4.15%", "4.20%1", "$100,000.00"]])
        apy = [c for c in C.extract_certificates(tab) if c["metric"] == "apy"][0]
        self.assertTrue(apy["tier_dims"]["jumbo"])
        self.assertEqual(apy["min_earn"], 100000.0)

    def test_footnote_marker_stripped_from_value(self):
        tab = make_table([["17 Month Fixed Certificate Special", "4.06%", "4.10%2", "$1,000.00"]])
        apy = [c for c in C.extract_certificates(tab) if c["metric"] == "apy"][0]
        self.assertEqual(apy["value"], 4.10)

    def test_ira_row_gets_flavor(self):
        tab = make_table(
            [["Roth: 17 Month Fixed Special", "3.81%", "3.85%2", "$1,000"]],
            section="Special IRAs",
        )
        apy = [c for c in C.extract_certificates(tab) if c["metric"] == "apy"][0]
        self.assertEqual(apy["tier_dims"]["ira_type"], "roth")

    def test_bare_term_row_needs_cert_section(self):
        tab = make_table([["60 Month", "1.79%", "1.80%1", "$1,000.00"]], section="Regular Certificates")
        apy = [c for c in C.extract_certificates(tab) if c["metric"] == "apy"][0]
        self.assertEqual(apy["tier_dims"]["term_months"], 60)
        self.assertFalse(apy["tier_dims"]["special"])

    def test_non_cert_row_skipped(self):
        tab = make_table([["Share Savings", "$25,000+", "0.20%", "1.0%"]], section="Share Savings")
        self.assertEqual(C.extract_certificates(tab), [])

    def test_both_metrics_extracted_as_separate_claims(self):
        tab = make_table([["17 Month Fixed Certificate Special", "4.06%", "4.10%2", "$1,000.00"]])
        metrics = {c["metric"] for c in C.extract_certificates(tab)}
        self.assertEqual(metrics, {"apy", "dividend_rate"})

    def test_quote_is_row_source(self):
        tab = make_table([["17 Month Fixed Certificate Special", "4.06%", "4.10%2", "$1,000.00"]])
        cl = C.extract_certificates(tab)[0]
        self.assertIn("17 Month Fixed Certificate Special", cl["quote"])


class TestProseExtractor(unittest.TestCase):
    def test_plain_sentence_form(self):
        claims = C.extract_prose_certificates("6-month certificate APY: 2.95%")
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["tier_dims"]["term_months"], 6)
        self.assertEqual(claims[0]["value"], 2.95)
        self.assertFalse(claims[0]["tier_dims"]["special"])

    def test_promo_sentence_with_leading_words(self):
        claims = C.extract_prose_certificates(
            "Summer special: 6-month certificate APY 2.95% (offer ended 2025-09-30)"
        )
        self.assertEqual(len(claims), 1)
        # "Summer special:" must NOT fork the key into a special variant
        self.assertFalse(claims[0]["tier_dims"]["special"])

    def test_table_rows_not_double_parsed_as_prose(self):
        line = "| 6 Month | 3.37% | 3.50%1 | $1,000 |"
        self.assertEqual(C.extract_prose_certificates(line), [])

    def test_non_cert_lines_skipped(self):
        self.assertEqual(C.extract_prose_certificates("Lost debit card replacement fee: $2.50"), [])


if __name__ == "__main__":
    unittest.main()
