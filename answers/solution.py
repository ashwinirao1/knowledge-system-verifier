"""
answers/solution.py — temporal claims ledger + trust-resolution stack.

Contract (harness/contract.py, nothing renamed):
    build() -> object with ingest(Snapshot) / answer(question, as_of) / conflicts()

Ingest (S0.2): per page: clean -> classify -> markdown tables -> certificate
family claims -> ledger (SQLite in memory). Bitemporal: snapshot date = posting
date; page-declared "Rates are effective as of MM/DD/YYYY" = value date.
Replicas dedup by content hash per snapshot; every distinct published value is
retained across snapshots (never overwritten — that's staleness history).

Answer (S0.3): parse question -> pick snapshot (as_of clamps to taken_on <=
as_of) -> filter claims in that snapshot -> trust stack (tier match, page-class
authority, freshest effective date) -> template synthesis. Refusals are
digit-free and confident=False (R1); answering is pure lookups (R2); fully
deterministic (R3); stdlib only, offline (R4).
"""
import sys
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE.parent),):
    if _p not in sys.path:
        sys.path.insert(0, _p)
_REPO = next(
    d for d in _HERE.parents
    if (d / "harness" / "contract.py").exists()
)
_harness = str(_REPO / "harness")
if _harness not in sys.path:
    sys.path.insert(0, _harness)
_answers = str(_HERE)
if _answers not in sys.path:
    sys.path.insert(0, _answers)

import hashlib  # noqa: E402
import json  # noqa: E402

import certificates as certificates_mod  # noqa: E402
import classify as classify_mod  # noqa: E402
import cleaning as cleaning_mod  # noqa: E402
import ledger as ledger_mod  # noqa: E402
import question as question_mod  # noqa: E402
import synthesize as synth  # noqa: E402
import tables as tables_mod  # noqa: E402
import trust as trust_mod  # noqa: E402
from contract import Answer, Snapshot, Source  # noqa: E402

PRODUCT = "certificate"


def _content_hash(product: str, metric: str, tier_dims: dict, value_text: str, eff: str | None) -> str:
    """Idempotency key (AGENTS §3): canonical key + value + value-date."""
    key = json.dumps([
        product, metric,
        json.dumps(tier_dims, sort_keys=True),
        value_text, eff,
    ], sort_keys=True)
    return hashlib.sha1(key.encode(), usedforsecurity=False).hexdigest()


class CurrentTruth:
    """Reconciliation engine over the temporal claims ledger."""

    def __init__(self) -> None:
        self.ledger = ledger_mod.Ledger()
        self.pages_seen = 0

    # ------------------------------------------------------------------ contract
    def ingest(self, snapshot: Snapshot) -> None:
        """Called once per snapshot, oldest first."""
        snap_id = snapshot.snapshot_id
        snap_date = snapshot.taken_on
        self.ledger.add_snapshot(snap_id, snap_date)
        for page in snapshot.pages:
            self._ingest_page(page, snap_id, snap_date)

    def _ingest_page(self, page, snap_id: str, snap_date: str) -> None:
        self.pages_seen += 1
        page_type, rank = classify_mod.classify(page.url, page.title)
        text = cleaning_mod.clean(page.markdown or "")
        if not text:
            return
        for tab in tables_mod.parse_tables(text):
            for claim in certificates_mod.extract_certificates(tab):
                self._store_claim(claim, page, page_type, rank, snap_id, snap_date)

    def _store_claim(self, claim: dict, page, page_type: str, rank: float,
                     snap_id: str, snap_date: str) -> None:
        dims = claim["tier_dims"]
        # membership segment is part of the canonical key: a business-certificate
        # row can never absorb (or compete with) a personal one by accident (R5).
        member = "business" if classify_mod.is_business(page.url, page.title) else "personal"
        dims = {**dims, "member": member}
        value = claim["value"]
        metric = claim["metric"]
        value_text = f"{value:.2f}%"
        eff = claim.get("effective_date")
        content_hash = _content_hash(PRODUCT, metric, dims, value_text, eff)
        self.ledger.add_claim(
            product=PRODUCT, metric=metric, tier_dims=dims, value=value,
            value_text=value_text, min_earn=claim.get("min_earn"),
            effective_date=eff, page_url=page.url, page_type=page_type,
            page_rank=rank, snapshot_id=snap_id, snapshot_date=snap_date,
            quote=claim.get("quote"), content_hash=content_hash,
        )

    def answer(self, question: str, as_of: Optional[str] = None) -> Answer:
        slots = question_mod.parse_question(question)
        if not slots:
            text, _ = synth.refusal()
            return Answer(text=text, sources=[], confident=False, conflict_note=None)
        as_of_iso = trust_mod.parse_as_of(as_of)
        snap_id = trust_mod.snapshot_id_as_of(self.ledger.snapshot_dates(), as_of_iso)
        if snap_id is None:
            text, _ = synth.refusal()
            return Answer(text=text, sources=[], confident=False, conflict_note=None)
        claims = self.ledger.all_claims_snapshot(snap_id, PRODUCT, slots["metric"])
        # tier filter: exact dims we know, leave unspecified dims open
        kept = []
        for c in claims:
            d = c.tier_dims
            if slots["term_months"] is not None and d["term_months"] != slots["term_months"]:
                continue
            if slots["special"] is not None and bool(d.get("special")) != slots["special"]:
                continue
            if slots["jumbo"] is not None and bool(d.get("jumbo")) != slots["jumbo"]:
                continue
            is_ira = d.get("ira_type") is not None or bool(d.get("ira")) is True
            if not slots["ira"] and is_ira:
                continue
            if d.get("member", "personal") != slots.get("member", "personal"):
                continue
            kept.append(c)
        if not kept:
            text, _ = synth.refusal()
            return Answer(text=text, sources=[], confident=False, conflict_note=None)
        winners = trust_mod.pick_winners(kept)
        if slots["jumbo"] is None:
            # question didn't disambiguate jumbo: state both special variants
            ordered = sorted(winners.values(), key=lambda c: (c.tier_dims["jumbo"], -c.tier_dims["term_months"]))
        else:
            ordered = sorted(winners.values(), key=lambda c: (-c.tier_dims["term_months"], c.tier_dims["jumbo"]))
        present_tense = as_of_iso is None or snap_id == trust_mod.snapshot_id_as_of(self.ledger.snapshot_dates(), None)
        text = synth.cert_answer(ordered, present_tense=present_tense)
        src = ordered[0]
        return Answer(
            text=text,
            sources=[Source(url=src.page_url, snapshot_id=snap_id, quote=src.quote)],
            confident=True,
            conflict_note=None,
        )

    def conflicts(self) -> list:
        """S0.4 arrives later; the path must exist and stay honest until then."""
        return []


def build():
    return CurrentTruth()
