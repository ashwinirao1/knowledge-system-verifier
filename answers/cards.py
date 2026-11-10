"""Card-family extractor (S1.3): personal + business credit cards, with the
standard-vs-intro APR qualifier (the S1.3 trap: 2.90% is ONLY the intro
balance-transfer APR; standard purchase APR is 12.50%–19.50%).

Table grammar (rate hub + business-card page):

    | Card Type | APR |
    | Introductory Balance Transfer Rate | 2.90%1 |        → rate_period="intro"
    | Platinum Visa Rate | 12.50% – 19.50%2 |              → standard range
    | Standard | 15.50% – 21.00%1 |                        → standard (heading carries product)
    | Business Rewards Visa | 20.5%1 |                     → standard single value

Product identity comes from the row label first, then the section heading —
business cards match before personal ones so "Platinum Visa" inside
"Business Platinum Visa" cannot mis-alias. APRs may be ranges: value = low
bound, tier_dims["apr_high"] = high bound, value_text keeps both.
"""
from __future__ import annotations

import re

_PCT_RE = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*%")
_RANGE_RE = re.compile(
    r"(\d{1,2}(?:\.\d+)?)\s*%\s*[–—-]\s*(\d{1,2}(?:\.\d+)?)\s*%"
)
_INTRO_RE = re.compile(r"introductory|intro\b|promotional", re.I)

# first match wins; business before personal disambiguates the Visa substring
CARD_ALIASES = [
    (re.compile(r"business\s+platinum\s+visa", re.I),
     ("business_platinum_visa", "Business Platinum Visa")),
    (re.compile(r"business\s+rewards\s+visa", re.I),
     ("business_rewards_visa", "Business Rewards Visa")),
    (re.compile(r"platinum\s+visa", re.I), ("platinum_visa", "Platinum Visa")),
    (re.compile(r"rewards\s+visa", re.I), ("rewards_visa", "Rewards Visa")),
]


def canonical_card(label: str):
    s = (label or "").strip()
    for rx, ident in CARD_ALIASES:
        if rx.search(s):
            return ident
    return None


def parse_apr(cell: str):
    """('12.50% – 19.50%' -> (12.50, 19.50)); '15.50%1' -> (15.50, None)."""
    s = (cell or "").strip()
    m = _RANGE_RE.search(s)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = _PCT_RE.search(s)
    if m:
        return float(m.group(1)), None
    return None, None


def _rate_period_of(label: str):
    return "intro" if _INTRO_RE.search(label) else None


def extract_cards(tab) -> list[dict]:
    """Card claims from one parsed table ([] for non-card tables)."""
    headers_l = [h.lower() for h in tab.headers]
    if not (any("card type" in h for h in headers_l)
            and any(h.strip().lower() == "apr" for h in headers_l)):
        return []
    apr_i = next(i for i, h in enumerate(headers_l) if h.strip().lower() == "apr")
    claims: list[dict] = []
    for cells, raw in zip(tab.rows, tab.raw_rows):
        if len(cells) <= apr_i:
            continue
        label = cells[0].strip().strip("*").strip()
        if not label or label.strip("|").strip() == "":
            continue
        value, high = parse_apr(cells[apr_i])
        if value is None:
            continue
        ident = canonical_card(label) or canonical_card(tab.section)
        if not ident:
            continue
        canon, display = ident
        claims.append({
            "tier_dims": {
                "kind": "card",
                "card": canon,
                "card_display": display,
                "rate_period": _rate_period_of(label),
                "apr_high": high,
            },
            "metric": "apr",
            "value": value,
            "min_earn": None,
            "quote": raw.strip()[:200],
            "effective_date": tab.effective_date,
        })
    return claims
