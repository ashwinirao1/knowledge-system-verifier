"""S0.2 component tests: ledger replica dedup + provenance + snapshot registry."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ledger as L  # noqa: E402


def claim_kwargs(**over):
    base = dict(
        product="certificate", metric="apy", tier_dims={"term_months": 17, "jumbo": False, "special": True, "ira_type": None},
        value=4.10, value_text="4.10%", min_earn=1000.0, effective_date="2026-09-01",
        page_url="https://x.example/personal/a", page_type="product_page", page_rank=100,
        snapshot_id="s1", snapshot_date="2026-09-28", quote="| 17 Month | 4.10% |",
        content_hash="h1",
    )
    base.update(over)
    return base


class TestReplicaDedup(unittest.TestCase):
    def setUp(self):
        self.led = L.Ledger()

    def test_same_hash_counts_once_within_snapshot(self):
        self.led.add_snapshot("s1", "2026-09-28")
        self.led.add_claim(**claim_kwargs())          # product page first
        self.led.add_claim(**claim_kwargs(page_url="https://x.example/rates", page_rank=95))
        rows = self.led.all_claims_snapshot("s1", "certificate", "apy")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].replicas, 2)
        self.assertIn("https://x.example/rates", rows[0].source_urls)

    def test_replica_merge_upgrades_authority(self):
        self.led.add_snapshot("s1", "2026-09-28")
        # low-authority rendering arrives first
        self.led.add_claim(**claim_kwargs(page_url="https://x.example/rates", page_rank=95))
        # product page replica arrives later and must BECOME the winner row
        self.led.add_claim(**claim_kwargs(page_url="https://x.example/personal/a", page_rank=100, quote="| 17 Month | 4.10%1 |"))
        rank, quote = self.led.db.execute("SELECT page_rank, quote FROM claims").fetchone()
        self.assertEqual(rank, 100.0)
        self.assertIn("4.10%1", quote)


class TestDistinctValues(unittest.TestCase):
    def setUp(self):
        self.led = L.Ledger()
        self.led.add_snapshot("s1", "2026-05-19")
        self.led.add_snapshot("s2", "2026-09-28")

    def test_same_key_two_snapshots_two_rows(self):
        self.led.add_claim(**claim_kwargs())
        self.led.add_claim(**claim_kwargs(snapshot_id="s2", snapshot_date="2026-09-28", page_url="u2"))
        self.assertEqual(len(self.led.all_claims_snapshot("s1", "certificate", "apy")), 1)
        self.assertEqual(len(self.led.all_claims_snapshot("s2", "certificate", "apy")), 1)

    def test_values_seen_spans_snapshots(self):
        self.led.add_claim(**claim_kwargs())
        self.led.add_claim(**claim_kwargs(
            snapshot_id="s2", snapshot_date="2026-09-28", value=4.00, value_text="4.00%",
            content_hash="h2", page_url="u2",
        ))
        self.assertEqual(self.led.values_seen("certificate", "apy", claim_kwargs()["tier_dims"]), {"4.10%", "4.00%"})

    def test_snapshot_dates_roundtrip(self):
        self.led.add_snapshot("s1", "2026-05-19")
        self.assertEqual(
            self.led.snapshot_dates(), {"s1": "2026-05-19", "s2": "2026-09-28"}
        )


if __name__ == "__main__":
    unittest.main()
