"""S4.1 unit tests: the BM25 fallback — tokenizer, key-term rule, quote
selection, determinism, and the precision-first guards."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fallback as FB  # noqa: E402


class TestTokenize(unittest.TestCase):
    def test_plural_fold_and_stopwords(self):
        toks = FB.tokenize("What are the fees for members?")
        self.assertEqual(toks, ["fee", "member"])

    def test_single_chars_dropped(self):
        toks = FB.tokenize("Rate on a 7/1 ARM?")
        self.assertNotIn("7", toks)
        self.assertNotIn("1", toks)
        self.assertIn("arm", toks)

    def test_ss_words_not_folded(self):
        self.assertEqual(FB._fold("less"), "less")  # ss preserved
        self.assertEqual(FB._fold("address"), "address")

    def test_deterministic(self):
        t = "How much is the wire transfer fee for members?"
        self.assertEqual(FB.tokenize(t), FB.tokenize(t))


def _index(pages):
    idx = FB.FallbackIndex()
    for snap, url, title, text in pages:
        idx.add_page(snap, url, title, text)
    return idx


class TestQuoteRules(unittest.TestCase):
    SNAP = "S_2026-09-28"

    def _idx(self):
        return _index([
            (self.SNAP, "https://x.org/fees", "Fees",
             "### Rate and Fee Schedule\n\n"
             "Miscellaneous fees and charges:\n\n"
             "| Stop payment | $30.00 |\n"
             "| Domestic wire | $25.00 |\n"
             "We value your membership every day.\n"),
            (self.SNAP, "https://x.org/blog", "Blog",
             "We stopped payment apps. Our members love it.\n"),
        ])

    def test_table_line_quoted_with_number(self):
        hit = self._idx().best(self.SNAP, "What do you charge for a stop payment?")
        self.assertIsNotNone(hit)
        sentence, url, _quote = hit
        self.assertIn("$30.00", sentence)
        self.assertIn("Stop payment", sentence)
        self.assertEqual(url, "https://x.org/fees")

    def test_blob_unit_never_quoted(self):
        # a >280-char table blob must not become the quote even when it
        # matches everything (R1: a blob carries other fees' numbers)
        blob = "| Fee table | " + " | ".join([f"item{i} $5.00" for i in range(40)])
        idx = _index([
            (self.SNAP, "https://x.org/fees", "Fees", f"### Fees\n\n{blob}\n"),
        ])
        hit = idx.best(self.SNAP, "What is the widget1 widget2 fee?")
        self.assertIsNone(hit)

    def test_unit_without_number_refuses(self):
        idx = _index([
            (self.SNAP, "https://x.org/fees", "Fees",
             "Stop payment requests are accepted at any branch office.\n"),
        ])
        self.assertIsNone(idx.best(self.SNAP, "What is the stop payment fee?"))

    def test_single_term_query_refuses(self):
        idx = self._idx()
        self.assertIsNone(idx.best(self.SNAP, "Tell me about overdrafts."))

    def test_unknown_product_name_vetoes(self):
        # the view never mentions 'hologram' — any quote would attribute some
        # other fee's number to it (R1: no fabricated attribution)
        idx = self._idx()
        self.assertIsNone(idx.best(self.SNAP, "What is the hologram fee?"))

    def test_as_of_view_filters_sections(self):
        idx = _index([
            ("OLD_2026-03-01", "https://x.org/old", "Old",
             "### Fees\n\nFees and charges:\n\n| Stop payment | $25.00 |\n"),
            ("NEW_2026-09-28", "https://x.org/new", "New",
             "Plain text without the old table at all.\n"),
        ])
        self.assertIsNotNone(idx.best("OLD_2026-03-01", "What is the stop payment fee?"))
        self.assertIsNone(idx.best("NEW_2026-09-28", "What is the stop payment fee?"))

    def test_deterministic_ranking(self):
        idx = self._idx()
        a = idx.best(self.SNAP, "What do you charge for a stop payment?")
        b = idx.best(self.SNAP, "What do you charge for a stop payment?")
        self.assertEqual(a, b)

    def test_ask_verbs_not_required_in_quote(self):
        # 'charge' is ask-side; the quote needs the key nouns only
        idx = _index([
            (self.SNAP, "https://x.org/fees", "Fees",
             "### Fees\n\nStop payment fee $30.00 per item. Other charges may apply.\n"),
        ])
        hit = idx.best(self.SNAP, "How much do you charge for stop payments?")
        self.assertIsNotNone(hit)
        self.assertIn("$30.00", hit[0])


if __name__ == "__main__":
    unittest.main()
