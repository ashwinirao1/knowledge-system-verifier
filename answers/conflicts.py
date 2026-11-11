"""Conflicts report (S0.4): same canonical key + different values, in the
CURRENT view (latest ingested snapshot view).

R5 precision rules implemented here:
  - only (product, metric, tier_dims) EQUALITY counts — tier/entity differences
    are not conflicts;
  - replica pages carrying the SAME fact count once (ingest already merged
    them; survivors here are genuinely competing statements);
  - every conflict states a winner and the reason it won.
Trust resolution (per AGENTS section 3): page-class authority, then freshest
table-level effective date, then the ledger's stable tie-breaking.
"""
from __future__ import annotations

import re

from contract import Conflict, Source

_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def _value_num(v: str) -> float:
    m = _PCT_RE.search(v or "")
    return float(m.group(1)) if m else 0.0


def _key_of(c) -> tuple:
    return (c.product, c.metric, tuple(sorted(c.tier_dims.items())))


def _topic_text(claim) -> str:
    """Human topic from canonical dims — member phrasing ("6-Month certificate APY")."""
    d = claim.tier_dims
    if d.get("kind") == "card":  # cards
        name = d.get("card_display") or d.get("card")
        word = "intro APR" if d.get("rate_period") == "intro" else "APR"
        return f"{name} {word}"
    if "family" in d:  # loans
        bits = []
        if d.get("family_display"):
            bits.append(d["family_display"])
        if d.get("purpose") and d.get("purpose") != (d.get("family_display") or "").lower():
            bits.append(d["purpose"])
        if d.get("model_older"):
            bits.append(f"{int(d['model_to'])} model-year and older")
        elif d.get("model_from") is not None:
            bits.append(f"{int(d['model_from'])}-{int(d['model_to']) % 100} model-year")
        if d.get("term_years"):
            bits.append(f"{int(d['term_years'])}-year")
        elif d.get("term_months"):
            bits.append(f"{int(d['term_months'])}-month")
        if d.get("amount_tier"):
            bits.append(str(d["amount_tier"]))
        if d.get("amount_tier") is None and d.get("amount_low") is not None:
            bits.append(f"${d['amount_low']:,.0f} tier")
        if d.get("variant"):
            bits.append(str(d["variant"]))
        word = "APR" if claim.metric == "apr" else "rate"
        return (f"{' '.join(bits)} {word}").strip()
    if "product" in d:  # deposit family
        from synthesize import tier_display  # local sibling import (no cycle at import time)
        word = "dividend rate" if claim.metric == "dividend_rate" else "APY"
        tier = tier_display(d)
        seg = f"{d['product_display']} {tier}".strip()
        return f"{seg} {word}"
    pre = {"roth": "Roth ", "traditional": "Traditional "}.get(d.get("ira_type"), "")
    mid = ""
    if d.get("jumbo"):
        mid += "jumbo "
    if d.get("special"):
        mid += "special "
    return f"{pre}{d['term_months']}-Month {mid}certificate {claim.metric}"


def _reason(winner, loser) -> str:
    if (winner.effective_date or "") > (loser.effective_date or ""):
        return (
            "Freshest statement wins: effective as of "
            f"{winner.effective_date} vs {loser.effective_date} on the "
            f"lower-authority {loser.page_type} page."
        )
    return (
        f"Page-class authority wins: {winner.page_type} outranks the "
        f"{loser.page_type} rendering of the same statement."
    )


def generate(store) -> list[Conflict]:
    """One Conflict per canonical key that keeps >1 distinct value in the current view."""
    from trust import snapshot_id_as_of  # local sibling cycle-avoidance

    ledger = store.ledger
    snap_dates = ledger.snapshot_dates()
    if not snap_dates:
        return []
    latest = snapshot_id_as_of(snap_dates, None)
    change_index = getattr(store, "change_index", None) or {}
    conflicts: list[Conflict] = []
    for family_product, family_metric in _FAMILY_VIEWS:
        claims = ledger.all_claims_snapshot(latest, family_product, family_metric)
        _scan_family(claims, conflicts, change_index)
    conflicts.sort(key=lambda c: (c.topic, c.values[0]))
    return conflicts


# metric views scanned for same-key value disagreements in the current view
_FAMILY_VIEWS = (
    ("certificate", "apy"),
    ("deposit", "apy"),
    ("deposit", "dividend_rate"),
    ("loans", "apr"),
    ("loans", "rate"),
    ("cards", "apr"),
)


def _scan_family(claims: list, conflicts: list, change_index: dict | None = None) -> None:
    from trust import pick_winners  # local sibling cycle-avoidance

    # group rows by canonical key preserving deterministic iteration order
    groups: dict[tuple, list] = {}
    for c in claims:
        groups.setdefault(_key_of(c), []).append(c)
    for key, group in groups.items():
        texts = {c.value_text for c in group}
        if len(texts) < 2:
            continue
        winner = pick_winners(group)[key]
        others = [c for c in group if c.value_text != winner.value_text]
        loser = sorted(others, key=lambda c: (c.page_rank, c.page_url))[0]
        sources = [
            Source(url=c.page_url, snapshot_id=c.snapshot_id, quote=c.quote)
            for c in sorted(group, key=lambda c: (-c.page_rank, c.page_url))
        ]
        # stable display order: resolution first, then descending value
        values = [winner.value_text] + [
            v for v in sorted(texts, key=_value_num, reverse=True) if v != winner.value_text
        ]
        # S2.3: when the same key ALSO moved between snapshots, cite the
        # transition — the disagreement the site shows now has a history, and
        # the reason string is the contract-safe place to carry it.
        reason = _reason(winner, loser)
        if change_index:
            t = change_index.get(key)
            if t:
                reason += f" Previous value {t['old']} until the {t['to_date']} snapshot."
        conflicts.append(Conflict(
            topic=_topic_text(winner),
            values=values,
            sources=sources,
            resolution=winner.value_text,
            reason=reason,
        ))
    conflicts.sort(key=lambda c: (c.topic, c.values[0]))
    return conflicts
