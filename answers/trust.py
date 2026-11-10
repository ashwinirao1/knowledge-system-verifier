"""Temporal selection + trust resolution (S0.3 v0).

Fixed order (AGENTS.md section 3) applied to a candidate set:
    1. exact qualifier / tier match  (done by the slot filter at query time)
    2. page-class authority          (ledger carries page_rank per claim)
    3. freshest table-level effective date
    4. liveness is a snapshot-stage property (the selected rows ARE the snapshot)

One winner per canonical key; distinct keys collapse how the synthesizer wants.
"""
from __future__ import annotations

import re

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
# tolerated month abbreviations ("may" needs no entry — full name covers it)
MONTH_ABBRS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TEXT_RE = re.compile(r"(\w+) (\d{4})", re.I)


def days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    if month == 2:
        leap = (year % 4 == 0 and year % 100 != 0) or year % 400 == 0
        return 29 if leap else 28
    return 30 if month in (4, 6, 9, 11) else 31


def parse_as_of(spec: str | None) -> str | None:
    """Normalize harness as_of input to an ISO date.

    ISO YYYY-MM-DD is the required form; month names ("May 2026", "jun 2026",
    "Sept 2026") are tolerated and clamp to the month's LAST day (a whole-month
    request asks about everything known by month end). Anything unparseable
    returns None, which callers treat as "now" — the documented fallback, never
    a guess at the intended date.
    """
    s = (spec or "").strip()
    if not s:
        return None
    m = _ISO_RE.match(s)
    if m:
        month, day = int(s[5:7]), int(s[8:10])
        if 1 <= month <= 12 and 1 <= day <= days_in_month(int(s[:4]), month):
            return s
        return None  # shape-ISO but out of range: refuse to guess
    m = _TEXT_RE.match(s)
    if m:
        name = m.group(1).lower()
        month = MONTHS.get(name) or MONTH_ABBRS.get(name)
        if month:
            year = int(m.group(2))
            return f"{year:04d}-{month:02d}-{days_in_month(year, month):02d}"
    return None


def snapshot_id_as_of(snap_dates: dict[str, str], as_of_iso: str | None) -> str | None:
    """Latest ingested snapshot with taken_on <= as_of (or the latest overall)."""
    if not snap_dates:
        return None
    if as_of_iso is None:
        return max(snap_dates, key=lambda k: (snap_dates[k], k))
    elig = [(d, k) for k, d in snap_dates.items() if d <= as_of_iso]
    if not elig:
        return None
    return max(elig)[1]


def clamp_snapshot(snap_dates: dict[str, str], as_of_iso: str | None) -> tuple[str | None, str]:
    """Snapshot selection for an as_of request plus an edge status (S2.2).

    Every as_of lands in exactly one of four edges, each with predictable
    behavior:
      - as_of is None                      -> latest snapshot, status "now"
      - between pulls / inside a long gap  -> newest snapshot published by the
        requested date, status "ok" (an as_of AFTER the latest snapshot also
        lands here — the newest data known by that date is the latest snapshot)
      - before the baseline                -> EARLIEST snapshot, status
        "before_baseline": we still answer (the earliest data IS our best
        knowledge for that date) and the caller attaches a provenance note —
        never a silent refusal, never silent present-tense prose.

    Returns (snapshot_id, status); status in {"now", "ok", "before_baseline",
    "none"}.
    """
    if not snap_dates:
        return None, "none"
    if as_of_iso is None:
        return max(snap_dates, key=lambda k: (snap_dates[k], k)), "now"
    elig = [(d, k) for k, d in snap_dates.items() if d <= as_of_iso]
    if elig:
        return max(elig)[1], "ok"
    return min(snap_dates, key=lambda k: (snap_dates[k], k)), "before_baseline"


def pick_winners(claims) -> dict[tuple, object]:
    """One claim per canonical key: authority → freshest value-date → stable key."""
    winners: dict[tuple, object] = {}
    for c in claims:
        key = (c.product, c.metric, tuple(sorted(c.tier_dims.items())))
        cur = winners.get(key)
        better = False
        if cur is None:
            better = True
        else:
            cur_sort = (cur.page_rank, cur.effective_date or "", cur.snapshot_date, cur.replicas)
            new_sort = (c.page_rank, c.effective_date or "", c.snapshot_date, c.replicas)
            if new_sort > cur_sort:
                better = True
        if better:
            winners[key] = c
    return winners
