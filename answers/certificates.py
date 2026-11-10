"""Certificates-family extractor (S0.2 tracer slice).

Turns markdown rate-table rows into candidate claims. The grammar is generic
over the page variants seen in the corpus:

    "17 Month Fixed Jumbo Certificate Special"   (plain specials)
    "10 Month Fixed Certificate Special"         (plain specials)
    "60 Month"                                   (standard terms, section context)
    "Roth: 10 Month Fixed Jumbo Special"         (IRA taxes), period)

Canonical key = (product, metric, tier_dims) where tier_dims captures every
dimension that distinguishes the fact: term, jumbo, special, IRA flavor.
Values with footnote markers ("4.10%2") are unmarked; the dividend-rate and
APY columns both become claims (separate metrics, same tier_dims).
"""
from __future__ import annotations

import re

from tables import Table

# a "certificate-shaped" row label: bare term, or term + cert tokens
_BARE_TERM_RE = re.compile(r"^\*{0,2}(\d{1,2})\s*-?\s*Month\s*\*{0,2}$", re.I)
_IRA_PREFIX_RE = re.compile(r"^(Roth|Traditional)\s*:\s*", re.I)
_TERM_RE = re.compile(r"(\d{1,2})\s*-?\s*Month", re.I)
_PCT_RE = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*%?", re.I)
_MONEY_RE = re.compile(r"\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)")
_CERT_TOKEN_RE = re.compile(r"certificate|special|jumbo|fixed", re.I)
_CERT_SECTION_RE = re.compile(r"certificate", re.I)
_IRA_SECTION_RE = re.compile(r",?\bIRAs?\b", re.I)

# prose forms ("6-month certificate APY: 2.95%", "Summer special: 6-month
# certificate APY 2.95% (offer ended 2025-09-30)") — rates stated in a sentence
# rather than a table (promo pages, blog posts, hub prose).
_PROSE_RATE_RE = re.compile(
    r"(\d{1,2})\s*[-\s]?\s*month\s+(?:fixed\s+)?((?:jumbo\s+)?(?:special\s+)?)?"
    r"certificates?\s*(?:special)?\s*"
    r"(?:APY|rate|yield|dividend rate)\s*:?[\s*]*(\d{1,2}(?:\.\d+)?)\s*%",
    re.I,
)

# columns we can use (canonical header text, fallback patterns)
def _col_index(headers: list[str], needles: list[str]) -> int:
    for i, h in enumerate(headers):
        hl = h.lower()
        if any(n.lower() in hl for n in needles):
            return i
    return -1


def _first_pct(cell: str) -> float | None:
    m = _PCT_RE.search(cell or "")
    return float(m.group(1)) if m else None


def _first_money(cell: str) -> float | None:
    m = _MONEY_RE.search(cell or "")
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def _label_dims(label: str, section: str) -> dict | None:
    """Parse a row label into tier_dims, or None when the row isn't a certificate."""
    s = label.strip().strip("\\*").strip()
    m_ira = _IRA_PREFIX_RE.match(s)
    ira_type = None
    if m_ira:
        ira_type = m_ira.group(1).lower()
        s = s[m_ira.end():].strip()
    m_term = _TERM_RE.search(s)
    bare = _BARE_TERM_RE.match(s)
    if not (m_term or bare):
        return None
    if not _CERT_TOKEN_RE.search(s) and not (_CERT_SECTION_RE.search(section) or _IRA_SECTION_RE.search(section)):
        return None
    term = int((m_term or bare).group(1))
    is_special = ("special" in s.lower()) or ("special" in section.lower())
    is_jumbo = "jumbo" in s.lower()
    return {
        "term_months": term,
        "jumbo": is_jumbo,
        "special": is_special,
        "ira_type": ira_type,
    }


def extract_certificates(tab: Table) -> list[dict]:
    """Yield claim dicts for one parsed table (only rows that parse as certificates)."""
    apy_i = _col_index(tab.headers, ["annual percentage yield", "apy"])
    div_i = _col_index(tab.headers, ["dividend rate", "rate"])
    min_i = _col_index(tab.headers, ["min. to earn", "min to earn"])
    claims: list[dict] = []
    for cells, raw in zip(tab.rows, tab.raw_rows):
        if len(cells) <= 1:
            continue
        dims = _label_dims(cells[0], tab.section)
        if not dims:
            continue
        min_earn = _first_money(cells[min_i]) if 0 <= min_i < len(cells) else None
        base = {"tier_dims": dims}
        base["min_earn"] = min_earn
        base["quote"] = raw.strip()[:200]
        base["effective_date"] = tab.effective_date
        if apy_i >= 0 and apy_i < len(cells):
            v = _first_pct(cells[apy_i])
            if v is not None:
                claims.append({**base, "metric": "apy", "value": v})
        if div_i >= 0 and div_i < len(cells):
            v = _first_pct(cells[div_i])
            if v is not None:
                claims.append({**base, "metric": "dividend_rate", "value": v})
    return claims


def extract_prose_certificates(text: str) -> list[dict]:
    """Cert-family claims stated in prose lines rather than tables (S0.4 need:
    the promo/trap pages that old rates linger on use sentence forms)."""
    claims: list[dict] = []
    for line in text.split("\n"):
        s = line.strip()
        if not s or s.startswith("|") or s.startswith("#"):
            continue
        for m in _PROSE_RATE_RE.finditer(s):
            term = int(m.group(1))
            tail = (m.group(2) or "").lower()
            dims = {
                "term_months": term,
                "jumbo": "jumbo" in tail,
                "special": bool(tail),   # token between term and "certificate" only,
                "ira_type": None,        # so "Summer special:" doesn't fork the key
            }
            value = float(m.group(3))
            # sentence form states the yield; there is no separate dividend rate
            claims.append({
                "tier_dims": dims,
                "metric": "apy",
                "value": value,
                "min_earn": None,
                "quote": s[:200],
                "effective_date": None,
            })
    return claims
