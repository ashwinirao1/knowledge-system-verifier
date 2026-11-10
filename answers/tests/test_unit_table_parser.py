"""S0.2 unit tests: markdown table parser + table-level effective-date discipline.

The date rule is the subtle part: the corpus repeats "Rates are effective as
of" inside footnotes that FOLLOW the table; only the statement line that
STARTS with the phrase (after markdown emphasis) is the table's date.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tables as T  # noqa: E402

CERTS = """Certificates

Special Certificates

| Certificate | Dividend Rate | Annual Percentage Yield (APY) | Min. to Earn |
| --- | --- | --- | --- |
| 17 Month Fixed Jumbo Certificate Special | 4.15% | 4.20%1 | $100,000.00 |
| 17 Month Fixed Certificate Special | 4.06% | 4.10%2 | $1,000.00 |

Rates are effective as of 09/01/2026 and are subject to change without notice.

1Fixed Jumbo Term Certificate Special Rate: Minimum amount required to open any
2Rates are effective as of 03/03/2026 inside a footnote sentence.
"""


class TestTableParser(unittest.TestCase):
    def test_parses_rows_and_headers(self):
        tabs = T.parse_tables(CERTS)
        self.assertEqual(len(tabs), 1)
        tab = tabs[0]
        self.assertEqual(tab.headers[0], "Certificate")
        self.assertEqual(len(tab.rows), 2)
        self.assertEqual(tab.rows[0][0], "17 Month Fixed Jumbo Certificate Special")

    def test_effective_date_is_table_level_not_footnote(self):
        tab = T.parse_tables(CERTS)[0]
        self.assertEqual(tab.effective_date, "2026-09-01")  # NOT 2026-03-03 (footnote)

    def test_bold_effective_date_variant(self):
        text = "| A | B |\n| - | - |\n| 17 Month | 4.10% |\n\n**Rates are effective as of 03/03/2026 and are subject to change without notice.**\n"
        tab = T.parse_tables(text)[0]
        self.assertEqual(tab.effective_date, "2026-03-03")

    def test_no_effective_date_returns_none(self):
        text = "| A | B |\n| - | - |\n| x | y |\n"
        tab = T.parse_tables(text)[0]
        self.assertIsNone(tab.effective_date)

    def test_section_is_nearest_heading_line(self):
        tab = T.parse_tables(CERTS)[0]
        self.assertEqual(tab.section, "Special Certificates")

    def test_does_not_steal_next_tables_date(self):
        """When two tables are back-to-back the first must not take the second's date."""
        text = (
            "| Term | APY |\n| - | - |\n| 17 Month | 4.10% |\n\n"
            "| Term | APY |\n| - | - |\n| 60 Month | 1.80% |\n\n"
            "Rates are effective as of 06/02/2026 and are subject to change without notice.\n"
        )
        tabs = T.parse_tables(text)
        self.assertEqual(len(tabs), 2)
        self.assertIsNone(tabs[0].effective_date)
        self.assertEqual(tabs[1].effective_date, "2026-06-02")

    def test_raw_rows_keep_quote_provenance(self):
        tab = T.parse_tables(CERTS)[0]
        self.assertIn("4.10%2", tab.raw_rows[1])


if __name__ == "__main__":
    unittest.main()
