"""Deposit-account family extractor (S1.1): Share Savings, savings variants,
Money Markets, checking (personal + business).

The tier tables all follow one grammar:

    | Account Type | Balance Tier | Dividend Rate | APY | Min. to Open | Min. to Earn |
    | Share Savings | $10,000 – $24,999.99 | 0.15% | 0.15%1 | $25.00 | $10,000.00 |

Product identity comes from ROW column 0 (not the section heading, which
drifts: "Share Savings Account", "Saving Account Rates", "None"). The
canonical key stays (product, metric, tier_dims) where tier_dims now also
carries  member  (page-level, set by the ingest driver) and
{tier_low, tier_high, tier_text}. Replica rows across pages collapse by
content hash exactly like certificates.
"""
from __future__ import annotations

import re

_MONEY_NUM_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d+)?|\d+(?:\.\d+)?)")
_PCT_RE = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*%", re.I)
_TIER_SPLIT_RE = re.compile(r"^\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(?:\+|–|-|—\s*\$?\s*([\d,]+(?:\.\d+)?))")
_EM_DASH_ONLY_RE = re.compile(r"^\s*[—–-]\s*$")

# row-label → (canonical product, display name); first match wins
PRODUCT_ALIASES = [
    (re.compile(r"business\s+share\s+savings", re.I), ("share_savings", "Share Savings")),
    (re.compile(r"share\s+savings", re.I), ("share_savings", "Share Savings")),
    (re.compile(r"you[- ]?name[- ]?it\s+savings", re.I), ("you_name_it_savings", "You Name It Savings")),
    (re.compile(r"bright\s+savings", re.I), ("bright_savings", "Bright Savings")),
    (re.compile(r"holiday\s+club\s+savings", re.I), ("holiday_club", "Holiday Club Savings")),
    (re.compile(r"launchpad\s+savings", re.I), ("launchpad_savings", "Launchpad Savings")),
    (re.compile(r"investor.?s\s+choice\s+money\s+market", re.I), ("investors_choice_mm", "Investor's Choice Money Market")),
    (re.compile(r"high[- ]yield\s+savings", re.I), ("high_yield_savings", "High-Yield Savings")),
    (re.compile(r"achieve\s+money\s+market", re.I), ("achieve_mm", "Achieve Money Market")),
    (re.compile(r"(?:business\s+)?1st\s+rate\s+checking", re.I), ("first_rate_checking", "1st Rate Checking")),
    (re.compile(r"free\s+checking", re.I), ("free_checking", "Free Checking")),
]

PRODUCT_ORDER = [
    "share_savings", "you_name_it_savings", "bright_savings", "holiday_club",
    "launchpad_savings", "investors_choice_mm", "high_yield_savings",
    "achieve_mm", "free_checking", "first_rate_checking",
]


def _business_display(section: str, display: str) -> str:
    """S3.2 entity resolution: on business pages the section heading carries
    the site's own qualified product name ("Business Share Savings",
    "Investor's Choice Money Market (Business)") while the row's Account Type
    cell says the plain name. Adopt the section name VERBATIM when the row
    label is contained in it — never invent a name. Scoped to sections headed
    with 'business' so drifted personal headings ("Share Savings Account",
    "Saving Account Rates") can never churn personal labels."""
    sec = (section or "").strip()
    if sec and re.search(r"business", sec, re.I):
        if display.lower() in sec.lower() and display.lower() != sec.lower():
            return sec
    return display


def canonical_product(label: str) -> tuple[str, str] | None:
    s = (label or "").strip().strip("*").strip()
    if not s:
        return None
    for rx, (canon, display) in PRODUCT_ALIASES:
        if rx.search(s):
            return canon, display
    return None


def _first_money(cell: str) -> float | None:
    m = _MONEY_NUM_RE.search(cell or "")
    return float(m.group(1).replace(",", "")) if m else None


def parse_balance_tier(cell: str) -> tuple[float | None, float | None, str]:
    """'$25,000+' -> (25000.0, None); '$10,000 – $24,999.99' -> (10000.0, 24999.99);
    '—' -> (None, None) (single non-tiered product, e.g. Free Checking)."""
    s = (cell or "").strip()
    if _EM_DASH_ONLY_RE.match(s):
        return None, None, ""
    if "+" in s:
        m = _MONEY_NUM_RE.search(s)
        return (float(m.group(1).replace(",", "")), None, s) if m else (None, None, s)
    m = re.match(r"^\s*\$?\s*([\d,]+(?:\.\d+)?)\s*[–-]\s*\$?\s*([\d,]+(?:\.\d+)?)", s)
    if m:
        lo = float(m.group(1).replace(",", ""))
        hi = float(m.group(2).replace(",", ""))
        return lo, hi, s
    m = _MONEY_NUM_RE.search(s)
    if m:
        v = float(m.group(1).replace(",", ""))
        return v, v, s
    return None, None, s


def _tier_display(low: float | None, high: float | None) -> str:
    if low is None and high is None:
        return ""
    if high is None and low is not None:
        return f"${low:,.2f} and up"
    if low is not None and high is not None:
        return f"${low:,.2f} – ${high:,.2f}"
    return ""


def _period_qualifier(header: str) -> str | None:
    """Intro/standard rate-period distinction from the column header itself.

    "Dividend Rate for 1st 6 Months" / "APY* for 1st 6 Months" → "intro" —
    a genuinely different fact (promotional rate for a bounded period).
    "After Promotional Period" columns describe the standard tiers, so they
    must merge with plain "Dividend Rate"/"APY" tables as replicas (None).
    """
    h = (header or "").lower()
    if re.search(r"\b(?:1st|first)\b|\bintroductory\b|\bintro\b", h):
        return "intro"
    return None


def _col_index(headers: list[str], needles: list[str]) -> int:
    for i, h in enumerate(headers):
        hl = h.lower()
        if any(n in hl for n in needles):
            return i
    return -1


def extract_deposits(tab) -> list[dict]:
    """Deposit claims from one parsed table ([] for non-deposit tables).

    Every rate column is classified into (metric, rate_period) so promo
    tables carrying BOTH introductory and after-promotion columns produce
    two distinct keys instead of a fake contradiction (R5).
    """
    headers_l = [h.lower() for h in tab.headers]
    if not any("balance tier" in h for h in headers_l):
        return []
    product_i = _col_index(tab.headers, ["account type"])
    min_open_i = _col_index(tab.headers, ["min. to open", "min to open"])
    min_earn_i = _col_index(tab.headers, ["min. to earn", "min to earn"])
    columns = []
    for i, h in enumerate(tab.headers):
        hl = h.lower()
        if "account type" in hl or "balance tier" in hl or "min" in hl:
            continue
        if "dividend rate" in hl:
            metric = "dividend_rate"
        elif "annual percentage yield" in hl or "apy" in hl:
            metric = "apy"
        else:
            continue
        columns.append((i, metric, _period_qualifier(h)))
    claims: list[dict] = []
    for cells, raw in zip(tab.rows, tab.raw_rows):
        if len(cells) <= 1:
            continue
        lbl = cells[product_i] if 0 <= product_i < len(cells) else ""
        ident = canonical_product(lbl)
        if not ident:
            continue
        canon, display = ident
        display = _business_display(tab.section, display)
        tier_i = _col_index(tab.headers, ["balance tier"])
        lo, hi, _raw = parse_balance_tier(cells[tier_i]) if 0 <= tier_i < len(cells) else (None, None, "")
        for idx, metric, period in columns:
            m = _PCT_RE.search(cells[idx])
            if not m:
                continue
            v = float(m.group(1))
            claims.append({
                "tier_dims": {
                    "product": canon,
                    "product_display": display,
                    "tier_low": lo,
                    "tier_high": hi,
                    "rate_period": period,
                },
                "metric": metric,
                "value": v,
                "min_open": _first_money(cells[min_open_i]) if 0 <= min_open_i < len(cells) else None,
                "min_earn": _first_money(cells[min_earn_i]) if 0 <= min_earn_i < len(cells) else None,
                "quote": raw.strip()[:200],
                "effective_date": tab.effective_date,
            })
    return claims
