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
    """Normalize harness as_of input to an ISO date (month names clamp to month end)."""
    s = (spec or "").strip()
    if not s:
        return None
    if _ISO_RE.match(s):
        return s
    m = _TEXT_RE.match(s)
    if m and m.group(1).lower() in MONTHS:
        month = MONTHS[m.group(1).lower()]
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
