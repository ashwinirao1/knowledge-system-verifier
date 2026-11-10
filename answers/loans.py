"""Loan-family extractor (S1.2): auto (model-year tiers), personal, mortgage
(rate/loan-amount tiers), home-improvement, boat-RV amount tiers, HELOC / home-
equity product variants.

Row-grammar driven (header naming drifts across pages — one calculator page
even renders an auto sheet under "Account Type | Balance Tier" headers):

    | Loan Program | Term | APR (As Low As) |                          → auto/personal/...
    | 2024-27 Model Year | 60 Months | 5.39% APR1 |
    | Program | Rate | Points | APR | *Payment Example |                → mortgage
    | Purchase: 30-Year Fixed Conventional $832,750 or less | 7.25% | 0 | 7.29% |

Outcome: claims with family-specific qualifiers in tier_dims (model-year range,
term, purpose, loan-amount tier) plus page-level member. The trust stack then
resolves stale sibling copies (promo / calculator / blog rate sheets stay live
in the latest snapshot) by page-class authority — no URL special-casing.
"""
from __future__ import annotations

import re

_MONEY_NUM_RE = re.compile(r"\$?\s*(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)")
_PCT_RE = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*%", re.I)
_TERM_CELL_RE = re.compile(r"^\*{0,2}(\d{1,3})\s*[-\s]?months?\*{0,2}$", re.I)
_MODEL_RANGE_RE = re.compile(r"(\d{4})\s*[-–]\s*(\d{1,2})\s*[- ]?model\s*year", re.I)
_MODEL_OLDER_RE = re.compile(r"^(\d{4})\s*[- ]?model\s*year.*\(and older\)", re.I)
_MORTGAGE_LABEL_RE = re.compile(
    r"^(?P<purpose>purchase|refinance):\s*(?P<term>\d{1,2})[- ]year\s*[- ]?fixed\s*"
    r"(?:conventional\s*)?(?P<amount>\$?[\d,]+\s*or less)?",
    re.I,
)
_AMOUNT_ONLY_RE = re.compile(
    r"^\$?\s*[\d,]+(?:\.\d+)?\s*(?:[-–]\s*\$?\s*[\d,]+(?:\.\d+)?|\+)\s*$"
)

# section heading → (family canonical, display name); first match wins
SECTION_RULES = [
    (re.compile(r"auto\s*&\s*motorcycle|vehicle", re.I), ("auto", "Auto & Motorcycle")),
    (re.compile(r"boat\s*&\s*rv|recreational", re.I), ("boat_rv", "Boat & RV")),
    (re.compile(r"atv|snowmobile|jet ski", re.I), ("atv_snowmobile", "ATV, Snowmobile & Jet Ski")),
    (re.compile(r"personal\s+loans?\b", re.I), ("personal", "Personal Loan")),
    (re.compile(r"home\s+loans?\s*[-–]\s*refinance|home\s+equity\s+refinance", re.I), ("mortgage_refi", "Refinance")),
    (re.compile(r"home\s+loans?\s*[-–]\s*purchase", re.I), ("mortgage_purchase", "Purchase")),
    (re.compile(r"home\s+equity\s+line|heloc", re.I), ("heloc", "HELOC")),
    (re.compile(r"home\s+equity\s+loan", re.I), ("home_equity_fixed", "Home Equity Loan")),
    (re.compile(r"home\s+improvement", re.I), ("home_improvement", "Home Improvement")),
]
_FALLBACK = ("other_loans", "Loan")


def _col_i(headers: list[str], needles: list[str]) -> int:
    for i, h in enumerate(headers):
        hl = h.lower()
        if any(n in hl for n in needles):
            return i
    return -1


def _num(cell: str) -> float | None:
    m = _MONEY_NUM_RE.search(cell or "")
    return float(m.group(1).replace(",", "")) if m else None


def _family_of(section: str):
    s = (section or "").strip()
    for rx, (canon, display) in SECTION_RULES:
        if rx.search(s):
            return canon, display
    return _FALLBACK


def _mortgage_dims(label: str) -> dict | None:
    m = _MORTGAGE_LABEL_RE.match(label.strip())
    if not m:
        return None
    return {
        "purpose": m.group("purpose").lower(),
        "term_years": int(m.group("term")),
        "amount_tier": m.group("amount").strip() if m.group("amount") else None,
        "amount_up_to": _num(m.group("amount")) if m.group("amount") else None,
    }


def _auto_dims(label: str):
    """'2024-27 Model Year' -> (2024, 2027); '2016 Model Year (and older)' -> (None, 2016)."""
    s = label.strip()
    m = _MODEL_RANGE_RE.search(s)
    if m:
        lo = int(m.group(1))
        hi_digits = int(m.group(2))
        hi = lo - (lo % 100) + hi_digits if hi_digits < 100 else hi_digits
        return {"model_from": float(lo), "model_to": float(hi), "model_older": False}
    m = _MODEL_OLDER_RE.match(s)
    if m:
        return {"model_from": None, "model_to": float(m.group(1)), "model_older": True}
    return None


def extract_loans(tab) -> list[dict]:
    """Loan claims from one parsed table ([] for tables without loan rows)."""
    fam, display = _family_of(tab.section)
    headers_l = [h.lower() for h in tab.headers]
    has_rate_col = any(("apr" in h or re.search(r"\brate\b", h)) for h in headers_l)
    if not has_rate_col:
        return []
    term_i = _col_i(tab.headers, ["term"])
    # rate-ish columns: APR or bare Rate (mortgage); skip Points / payment examples
    rate_cols = []
    for i, h in enumerate(tab.headers):
        hl = h.lower()
        if "points" in hl or "payment" in hl or "term" in hl:
            continue
        if "apr" in hl:
            rate_cols.append((i, "apr"))
        elif re.search(r"\brate\b", hl):
            rate_cols.append((i, "rate"))
    claims: list[dict] = []
    for cells, raw in zip(tab.rows, tab.raw_rows):
        if len(cells) < 2:
            continue
        label = cells[0].strip().strip("*").strip()
        dims = None
        # mortgage rows: "Purchase: 30-Year Fixed Conventional $832,750 or less";
        # the label's own purpose prefix is the family (headings drift, and a
        # stale purchase sheet under a bare "Home Loans" heading must land in
        # the same canonical keys as the rate-sheet rows it competes with)
        mdims = _mortgage_dims(label)
        if mdims:
            fam, display = ("mortgage_refi", "Refinance") if mdims["purpose"] == "refinance" \
                else ("mortgage_purchase", "Purchase")
            dims = mdims
        # auto rows: model-year label regardless of header naming
        if dims is None and (_MODEL_RANGE_RE.search(label) or _MODEL_OLDER_RE.match(label)):
            adims = _auto_dims(label)
            if adims and fam == "other_loans":
                fam, display = "auto", "Auto & Motorcycle"
            dims = adims
        # term-only loan rows ("24 Months") with an APR column → personal/...
        if dims is None:
            tm = _TERM_CELL_RE.match(label)
            if tm and fam != "other_loans":
                dims = {"term_months": int(tm.group(1))}
        # amount-tier + term rows (boat-RV / home-improvement / vehicle pages)
        if dims is None:
            tm = _TERM_CELL_RE.match(cells[term_i].strip()) if 0 <= term_i < len(cells) else None
            if tm and (_AMOUNT_ONLY_RE.match(label) or _num(label) and "$" in label):
                dims = {
                    "amount_tier": label,
                    "amount_low": _num(label),
                    "term_months": int(tm.group(1)),
                }
        # product-variant rows with the term inside the label ("Loan – Standard (60 mo)")
        if dims is None:
            mm = re.match(r"^loan\s*[–-]\s*standard\s*\((\d{1,3})\s*mo\)", label, re.I)
            if mm and fam != "other_loans":
                dims = {"term_months": int(mm.group(1))}
        # HELOC-style single product rows ("HELOC – Standard")
        if dims is None and fam == "heloc":
            dims = {"variant": label}
        if dims is None:
            continue
        # every family that uses a Term column gets term_months attached
        if "term_months" not in dims and "term_years" not in dims:
            tm = _TERM_CELL_RE.match(cells[term_i].strip()) if 0 <= term_i < len(cells) else None
            if tm:
                dims = {**dims, "term_months": int(tm.group(1))}
        for idx, metric in rate_cols:
            if idx >= len(cells):
                continue
            mp = _PCT_RE.search(cells[idx])
            if not mp:
                continue
            claims.append({
                "tier_dims": {
                    "family": fam,
                    "family_display": display,
                    **dims,
                },
                "metric": metric,
                "value": float(mp.group(1)),
                "min_earn": None,
                "quote": raw.strip()[:200],
                "effective_date": tab.effective_date,
            })
    return claims
