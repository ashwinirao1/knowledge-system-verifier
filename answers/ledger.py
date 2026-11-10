"""Temporal claims ledger (S0.2): SQLite in-memory store with provenance.

Ingest deduplicates REPLICAS (same content hash inside one snapshot — e.g. the
same sheet rendered on the rates hub and the product page) by counting them,
but never discards a DISTINCT value: every state the website has ever shown
stays in the ledger. `as_of` reads pick the snapshot, and answers read only
the rows of the selected snapshot (R2: queries only; no model calls).
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

_SCHEMA = """
CREATE TABLE claims (
    id            INTEGER PRIMARY KEY,
    product       TEXT NOT NULL,
    metric        TEXT NOT NULL,
    tier_dims     TEXT NOT NULL,          -- canonical JSON of idempotency dims
    value         REAL NOT NULL,
    value_text    TEXT NOT NULL,
    min_earn      REAL,
    effective_date TEXT,                   -- value date (page-declared)
    page_url      TEXT NOT NULL,
    page_type     TEXT NOT NULL,
    page_rank     REAL NOT NULL,
    snapshot_id   TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    quote         TEXT,
    content_hash  TEXT NOT NULL,
    replicas      INTEGER NOT NULL DEFAULT 1,
    source_urls   TEXT NOT NULL
);
CREATE INDEX idx_claims_key ON claims(product, metric, snapshot_id);
CREATE INDEX idx_claims_snap ON claims(snapshot_id);
CREATE TABLE snapshots (
    snapshot_id TEXT PRIMARY KEY,
    taken_on    TEXT NOT NULL
);
"""


@dataclass
class Claim:
    product: str
    metric: str
    tier_dims: dict
    value: float
    value_text: str
    min_earn: float | None
    effective_date: str | None
    page_url: str
    page_type: str
    page_rank: float
    snapshot_id: str
    snapshot_date: str
    quote: str | None
    replicas: int
    source_urls: list

    def rep(self) -> str:  # canonical value text used in answers/templates
        return self.value_text


class Ledger:
    def __init__(self) -> None:
        # check_same_thread=False: the harness builds the system on one thread and
        # answers on the eval pool's thread. Usage is strictly serialized
        # (max_workers=1), so sharing the connection is safe and deterministic.
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.executescript(_SCHEMA)

    # ------------------------------------------------------------------ writes
    def add_snapshot(self, snapshot_id: str, taken_on: str) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO snapshots(snapshot_id, taken_on) VALUES (?, ?)",
            (snapshot_id, taken_on),
        )
        self.db.commit()

    def add_claim(
        self, *, product: str, metric: str, tier_dims: dict, value_text: str, value: float,
        min_earn: float | None, effective_date: str | None, page_url: str, page_type: str,
        page_rank: float, snapshot_id: str, snapshot_date: str, quote: str | None,
        content_hash: str,
    ) -> None:
        cur = self.db.execute(
            "SELECT id, replicas, source_urls, page_rank, quote FROM claims "
            "WHERE content_hash = ? AND snapshot_id = ? AND product = ? AND metric = ?",
            (content_hash, snapshot_id, product, metric),
        )
        row = cur.fetchone()
        if row:
            claim_id, replicas, urls_json, old_rank, old_quote = row
            urls = json.loads(urls_json)
            added = page_url not in urls
            if added:
                urls = (urls + [page_url])[:10]
            # replica merge upgrades provenance: the ledger keeps the most
            # authoritative rendering of the fact (R5 + trust stack ordering).
            if page_rank > old_rank:
                self.db.execute(
                    "UPDATE claims SET replicas = ?, source_urls = ?, page_rank = ?,"
                    " quote = ? WHERE id = ?",
                    (replicas + (1 if added else 0), json.dumps(urls), page_rank, quote, claim_id),
                )
            else:
                self.db.execute(
                    "UPDATE claims SET replicas = ?, source_urls = ? WHERE id = ?",
                    (replicas + (1 if added else 0), json.dumps(urls), claim_id),
                )
        else:
            self.db.execute(
                "INSERT INTO claims(product, metric, tier_dims, value, value_text, min_earn,"
                " effective_date, page_url, page_type, page_rank, snapshot_id, snapshot_date,"
                " quote, content_hash, replicas, source_urls)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)",
                (
                    product, metric, json.dumps(tier_dims, sort_keys=True), value, value_text,
                    min_earn, effective_date, page_url, page_type, page_rank,
                    snapshot_id, snapshot_date, quote, content_hash, json.dumps([page_url]),
                ),
            )
        self.db.commit()

    # ------------------------------------------------------------------- reads
    def snapshot_dates(self) -> dict[str, str]:
        return dict(self.db.execute("SELECT snapshot_id, taken_on FROM snapshots").fetchall())

    def all_claims_snapshot(self, snapshot_id: str, product: str, metric: str) -> list[Claim]:
        rows = self.db.execute(
            "SELECT * FROM claims WHERE snapshot_id = ? AND product = ? AND metric = ?",
            (snapshot_id, product, metric),
        ).fetchall()
        return [self._to_claim(r) for r in rows]

    def values_seen(self, product: str, metric: str, tier_dims: dict) -> set[str]:
        """Distinct canonical values ever published for a key (conflict material)."""
        return {
            row[0]
            for row in self.db.execute(
                "SELECT value_text FROM claims WHERE product=? AND metric=? AND tier_dims=?",
                (product, metric, json.dumps(tier_dims, sort_keys=True)),
            ).fetchall()
        }

    def _to_claim(self, row) -> Claim:
        return Claim(
            product=row[1], metric=row[2], tier_dims=json.loads(row[3]), value=row[4],
            value_text=row[5], min_earn=row[6], effective_date=row[7], page_url=row[8],
            page_type=row[9], page_rank=row[10], snapshot_id=row[11], snapshot_date=row[12],
            quote=row[13], replicas=row[15], source_urls=json.loads(row[16]),
        )
