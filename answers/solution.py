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
from __future__ import annotations

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
import conflicts as conflicts_mod  # noqa: E402
import deposits as deposits_mod  # noqa: E402
import ledger as ledger_mod  # noqa: E402
import loans as loans_mod  # noqa: E402
import question as question_mod  # noqa: E402
import synthesize as synth  # noqa: E402
import tables as tables_mod  # noqa: E402
import trust as trust_mod  # noqa: E402
from contract import Answer, Snapshot, Source  # noqa: E402

PRODUCT = "certificate"
DEPOSIT_PRODUCT = "deposit"
LOAN_PRODUCT = "loans"


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
            for claim in deposits_mod.extract_deposits(tab):
                self._store_deposit_claim(claim, page, page_type, rank, snap_id, snap_date)
            for claim in loans_mod.extract_loans(tab):
                self._store_loan_claim(claim, page, page_type, rank, snap_id, snap_date)
        for claim in certificates_mod.extract_prose_certificates(text):
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

    def _store_deposit_claim(self, claim: dict, page, page_type: str, rank: float,
                             snap_id: str, snap_date: str) -> None:
        dims = {**claim["tier_dims"]}
        # membership segment is part of the canonical key here too: business
        # Share Savings rows are distinct facts from personal ones (R5).
        member = "business" if classify_mod.is_business(page.url, page.title) else "personal"
        dims = {**dims, "member": member}
        value = claim["value"]
        metric = claim["metric"]
        value_text = f"{value:.2f}%"
        eff = claim.get("effective_date")
        content_hash = _content_hash(DEPOSIT_PRODUCT, metric, dims, value_text, eff)
        self.ledger.add_claim(
            product=DEPOSIT_PRODUCT, metric=metric, tier_dims=dims, value=value,
            value_text=value_text, min_earn=claim.get("min_earn"),
            effective_date=eff, page_url=page.url, page_type=page_type,
            page_rank=rank, snapshot_id=snap_id, snapshot_date=snap_date,
            quote=claim.get("quote"), content_hash=content_hash,
        )

    def _store_loan_claim(self, claim: dict, page, page_type: str, rank: float,
                          snap_id: str, snap_date: str) -> None:
        dims = {**claim["tier_dims"]}
        # membership segment is part of the canonical key here as well.
        member = "business" if classify_mod.is_business(page.url, page.title) else "personal"
        dims = {**dims, "member": member}
        value = claim["value"]
        metric = claim["metric"]
        value_text = f"{value:.2f}%"
        eff = claim.get("effective_date")
        content_hash = _content_hash(LOAN_PRODUCT, metric, dims, value_text, eff)
        self.ledger.add_claim(
            product=LOAN_PRODUCT, metric=metric, tier_dims=dims, value=value,
            value_text=value_text, min_earn=None,
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
        if slots["family"] == "deposit":
            return self._answer_deposit(slots, snap_id, as_of_iso)
        if slots["family"] == "loans":
            return self._answer_loans(slots, snap_id, as_of_iso)
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
        # conflict_note only when sources genuinely disagreed IN THIS VIEW (R5):
        # same canonical key, >1 distinct surviving VALUE in the snapshot.
        note = None
        groups: dict[tuple, set] = {}
        for c in kept:
            groups.setdefault(trust_key(c), set()).add(c.value_text)
        if any(len(v) > 1 for v in groups.values()):
            note = synth.DISAGREEMENT_NOTE
        return Answer(
            text=text,
            sources=[Source(url=src.page_url, snapshot_id=snap_id, quote=src.quote)],
            confident=True,
            conflict_note=note,
        )

    def _answer_deposit(self, slots: dict, snap_id: str, as_of_iso: str | None) -> Answer:
        """Deposit-family answer: product(s) → tier/mode → trust → template."""
        ledger = self.ledger
        claims = ledger.all_claims_snapshot(snap_id, DEPOSIT_PRODUCT, slots["metric"])
        prods = set(slots["products"])
        kept = []
        for c in claims:
            d = c.tier_dims
            if d.get("product") not in prods:
                continue
            if d.get("member", "personal") != slots.get("member", "personal"):
                continue
            kept.append(c)
        if not kept:
            text, _ = synth.refusal()
            return Answer(text=text, sources=[], confident=False, conflict_note=None)
        winners = trust_mod.pick_winners(kept)
        chosen = list(winners.values())
        mode = slots["mode"]

        if mode == "tier":
            lo, hi = slots["tier"]
            mid = (lo + (hi if hi is not None else lo)) / 2.0
            chosen = [
                c for c in chosen
                if c.tier_dims.get("tier_low") is not None
                and c.tier_dims["tier_low"] <= mid
                and (c.tier_dims.get("tier_high") is None or mid <= c.tier_dims["tier_high"])
            ]
            if not chosen:
                text, _ = synth.refusal()
                return Answer(text=text, sources=[], confident=False, conflict_note=None)
            text = synth.deposit_answer(chosen, slots["metric"], present_tense=self._present(snap_id, as_of_iso))
        elif mode == "highest":
            chosen = sorted(chosen, key=lambda c: (-c.value, c.tier_dims.get("tier_low") or 0.0))[:1]
            text = synth.deposit_highest(chosen[0], slots["metric"], present_tense=self._present(snap_id, as_of_iso))
        elif mode == "do_any":
            target = slots["hypo"]
            hits = [c for c in chosen if abs(c.value - target) < 1e-9]
            if hits:
                text = synth.deposit_do_any_yes(hits, slots["metric"], present_tense=self._present(snap_id, as_of_iso))
                chosen = hits
            else:
                top = sorted(chosen, key=lambda c: (-c.value, c.tier_dims.get("tier_low") or 0.0))[0]
                text = synth.deposit_do_any_no(top, slots["metric"], present_tense=self._present(snap_id, as_of_iso))
                chosen = [top]
        else:  # list_all — every tier of every matched product (R1: all are claims)
            text = synth.deposit_answer(chosen, slots["metric"], present_tense=self._present(snap_id, as_of_iso))

        src = sorted(chosen, key=lambda c: (-c.page_rank, c.page_url))[0]
        # conflict_note only when sources genuinely disagreed IN THIS VIEW (R5)
        note = None
        groups: dict[tuple, set] = {}
        for c in kept:
            groups.setdefault(trust_key(c), set()).add(c.value_text)
        if any(len(v) > 1 for v in groups.values()):
            note = synth.DISAGREEMENT_NOTE
        return Answer(
            text=text,
            sources=[Source(url=src.page_url, snapshot_id=snap_id, quote=src.quote)],
            confident=True,
            conflict_note=note,
        )

    # ----------------------------------------------------------------- loans
    _LOAN_METRIC_FALLBACK = {"rate": "apr", "apr": "rate"}

    def _answer_loans(self, slots: dict, snap_id: str, as_of_iso: str | None) -> Answer:
        """Loan-family answer: family → term/model filters → trust → template.

        Stale sibling tables (promo / calculator / blog copies of the rate
        sheets stay live in the latest snapshot) resolve by page-class rank:
        canonical-key winners collapse, and model-year questions collapse the
        covering ranges by rank so the rate-sheet row beats any promo table.
        """
        fam = slots["loan_family"]
        if fam == "mortgage":
            # generic "mortgage" asks the purchase sheet; refinance only when asked
            ledger_fams = ("mortgage_refi",) if slots.get("refinance") else ("mortgage_purchase",)
        elif fam == "home_equity":
            ledger_fams = ("heloc", "home_equity_fixed")
        else:
            ledger_fams = (fam,)

        kept = []
        for met in (slots["metric"], self._LOAN_METRIC_FALLBACK.get(slots["metric"])):
            if met is None:
                continue
            claims = self.ledger.all_claims_snapshot(snap_id, LOAN_PRODUCT, met)
            kept = self._filter_loan_claims(claims, slots, ledger_fams)
            if kept:
                break
        if not kept:
            text, _ = synth.refusal()
            return Answer(text=text, sources=[], confident=False, conflict_note=None)

        winners = list(trust_mod.pick_winners(kept).values())
        model_year = slots.get("model_year")
        if model_year is not None and any(
            "model_from" in w.tier_dims or "model_to" in w.tier_dims for w in winners
        ):
            # several model-year ranges can cover the asked year ("2024-27" on
            # the rate sheet, "2023–26" on a stale promo page): collapse each
            # term to the rank-authoritative statement.
            best: dict[tuple, object] = {}
            for c in sorted(
                winners,
                key=lambda c: (c.page_rank, c.effective_date or "", c.snapshot_date),
                reverse=True,
            ):
                d = c.tier_dims
                sem = (
                    d.get("family"), d.get("term_months"), d.get("metric"),
                    d.get("member"),
                )
                best.setdefault(sem, c)
            winners = list(best.values())

        ordered = self._order_loan_claims(winners, slots)
        text = synth.loan_answer(ordered, slots, present_tense=self._present(snap_id, as_of_iso))

        src = sorted(ordered, key=lambda c: (-c.page_rank, c.page_url))[0]
        note = None
        groups: dict[tuple, set] = {}
        for c in kept:
            groups.setdefault(trust_key(c), set()).add(c.value_text)
        if any(len(v) > 1 for v in groups.values()):
            note = synth.DISAGREEMENT_NOTE
        return Answer(
            text=text,
            sources=[Source(url=src.page_url, snapshot_id=snap_id, quote=src.quote)],
            confident=True,
            conflict_note=note,
        )

    def _filter_loan_claims(self, claims: list, slots: dict, ledger_fams: tuple) -> list:
        fams = set(ledger_fams)
        term_m = slots.get("term_months")
        term_y = slots.get("term_years")
        model_year = slots.get("model_year")
        member = slots.get("member", "personal")
        kept = []
        for c in claims:
            d = c.tier_dims
            if d.get("family") not in fams:
                continue
            if d.get("member", "personal") != member:
                continue
            if term_m is not None and d.get("term_months") != term_m:
                continue
            if term_y is not None and d.get("term_years") != term_y:
                continue
            if model_year is not None:
                if d.get("model_older"):
                    if model_year > d.get("model_to", 10**9):
                        continue
                elif d.get("model_from") is not None or d.get("model_to") is not None:
                    if not (d["model_from"] <= model_year <= d["model_to"]):
                        continue
            kept.append(c)
        return kept

    def _order_loan_claims(self, winners: list, slots: dict) -> list:
        fam = slots["loan_family"]
        if fam == "mortgage":
            # amount tiers ascending so the smallest loan ledes; terms 30 → 20 → 15
            return sorted(
                winners,
                key=lambda c: (
                    -(c.tier_dims.get("term_years") or 0),
                    c.tier_dims.get("amount_up_to") or 10**12,
                    c.tier_dims.get("model_from") or 0,
                ),
            )
        return sorted(
            winners,
            key=lambda c: (
                c.tier_dims.get("term_months") or 0,
                c.tier_dims.get("model_from") or 0,
                c.tier_dims.get("term_years") or 0,
                c.tier_dims.get("amount_up_to") or 0,
            ),
        )

    def _present(self, snap_id: str, as_of_iso: str | None) -> bool:
        return as_of_iso is None or snap_id == trust_mod.snapshot_id_as_of(self.ledger.snapshot_dates(), None)

    def conflicts(self) -> list:
        """Every contradiction the site shows now: same key, different values."""
        return conflicts_mod.generate(self)


def trust_key(c) -> tuple:
    d = c.tier_dims
    if "family" in d:  # loans
        return (d.get("family"), d.get("term_months"), d.get("term_years"),
                d.get("model_from"), d.get("model_to"), d.get("amount_up_to"),
                d.get("variant"), d.get("member"))
    if "product" in d:  # deposit family
        return (d["product"], d.get("tier_low"), d.get("tier_high"), d.get("member"))
    return (d["term_months"], d.get("jumbo"), d.get("special"),
            d.get("ira_type"), d.get("member"))


def build():
    return CurrentTruth()
