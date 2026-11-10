"""Page classifier (S0.2): URL-based v0 with fixed authority ranks.

Trust order from AGENTS.md section 3 (higher rank = more authoritative):
    product page ~= rates hub  >  template / footer  >  newsroom / blog
    >  promo  >  calculator  >  old PDF

The rank is attached to the claim at ingest time so the ledger can order
candidates without re-classifying pages at answer time (R2: lookups only).
"""
from __future__ import annotations

import re

# (page_type, authority_rank)
RANKS = {
    "product_page": 100,   # leaf page describing one product's terms
    "rates_hub": 95,       # the classic "rates table" hub page
    "template": 70,        # generic landing/template pages carrying boilerplate
    "newsroom": 55,
    "blog": 50,
    "promo": 40,
    "calculator": 25,
    "legacy_pdf": 10,
    "other": 30,
}

_RULES = [
    # most specific first; first match wins
    (re.compile(r"/hubfs/|\.pdf(\?|$)", re.I), "legacy_pdf"),
    (re.compile(r"/calculators?(/|$)", re.I), "calculator"),
    (re.compile(r"/learn/blog(/|$)|/blog(/|$)", re.I), "blog"),
    (re.compile(r"/newsroom(/|$)", re.I), "newsroom"),
    (re.compile(r"/(promo|special-offer|offer|deals?)", re.I), "promo"),
    (re.compile(r"/rates(/|$)|^/rates$|/rates-|/business-rates", re.I), "rates_hub"),
    (re.compile(r"/personal/", re.I), "product_page"),
]


def classify(url: str, title: str = "") -> tuple[str, int]:
    """Return (page_type, authority_rank) for a page URL/title."""
    u = url or ""
    low = u.lower()
    for rx, page_type in _RULES:
        if rx.search(low):
            _type = page_type
            break
    else:
        # hub-like short titles that are de-facto rate sheets
        if (title or "").strip().lower() in {"rates", "current rates", "rates & fees"}:
            _type = "rates_hub"
        else:
            _type = "template"
    rank = RANKS[_type]
    # business variants of any class are personal-family noise; rank them below
    # everything so they can never beat a personal claim on equal footing.
    low_url = u.rstrip("/").lower()
    is_business = "/business" in low_url or low_url.endswith("business-rates")
    if is_business:
        rank = min(rank, 5)
    return _type, rank


def is_business(url: str, title: str = "") -> bool:
    u = (url or "").rstrip("/").lower()
    if "/business" in u or u.endswith("business-rates"):
        return True
    return (title or "").strip().lower().startswith("business")
