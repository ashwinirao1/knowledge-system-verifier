"""Branch-knowledge extractor (S1.4): lobby/drive-up hours, branch addresses,
and relocation notices — prose, not tables.

Shapes parsed:

    Branch hours are:            (newsroom pages, one per branch opening)
    **Lobby**
    Monday-Thursday: 8:30 a.m.-5 p.m.
    ...

    ### Dupaco Credit Union      (contact-page locator list)
    Dupaco Branch
    11375 Oldenburg Ln., Galena, IL, 61036
    Closed

    "...full-service branches at Key West and Sycamore Street."   (notices)

Claims are TEXT claims (value=0.0, the schedule/address/alternatives text is
the fact); they are kept out of the conflicts family views — different
branches legitimately publish different schedules, which is not a
contradiction (R5).
"""
from __future__ import annotations

import re

from trust import MONTHS

_WEEKDAY = r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
_DAY_GROUP_RE = re.compile(
    r"^\s*(?P<days>" + _WEEKDAY + r"(?:\s*[–—-]\s*" + _WEEKDAY + r")?"
    r"(?:(?:,\s*)?" + _WEEKDAY + r")?)\s*:\s*(?P<spec>.+?)\s*$",
    re.I,
)
_BOLD_CHANNEL_RE = re.compile(r"^\s*\*\*(?P<ch>lobby|drive[- ]?up|drive?-?thru)\*\*\s*(?P<rest>.*)$", re.I)
_LOCATOR_BRANCH_RE = re.compile(r"^\s*#{2,4}\s*Dupaco Credit Union\s*$", re.I)
_LOCATOR_TYPE_BRANCH_RE = re.compile(r"^\s*Dupaco Branch\s*$", re.I)
_ADDRESS_RE = re.compile(
    r"^(?P<addr>\d+[A-Za-z]? .+?,\s*(?P<city>[^,]+?),\s*(?P<state>AZ|IA|IL|MN|WI)),\s*(?P<zip>\d{5})(?:-\d{4})?$"
)
_HOURS_ANCHOR_RE = re.compile(r"Branch hours are:", re.I)
_BRANCH_NAME_RE = re.compile(
    r"(?:^|\.|\n)\s*(?:The\s+)?(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*?)\s+(?:Dubuque\s+)?"
    r"branch is located", re.I
)
_HYVEE_ALTERNATIVES_RE = re.compile(
    r"full-service branches at (?P<alts>[^.”']+|[A-Z][^.”']*)", re.I
)


def _entry_from_match(md) -> dict:
    days = re.sub(r"\s+[–—-]\s+", "-", md.group("days"))
    # dash/spacing variants across pages must not split identical schedules
    spec = re.sub(r"[–—]", "-", md.group("spec").strip())
    return {"days": days.strip(), "spec": spec}


def _schedule_text(entries: list[dict]) -> str:
    """Deterministic single-line schedule: 'Monday-Thursday: 8:30 a.m.-5 p.m.; ...'."""
    return "; ".join(f"{e['days']}: {e['spec']}" for e in entries)


def _hours_blocks(text: str) -> list[tuple[str, list[dict]]]:
    """(channel, entries) per Lobby/Drive-up block."""
    lines = text.split("\n")
    blocks: list[tuple[str, list[dict]]] = []
    channel = None
    entries: list[dict] = []
    for line in lines:
        s = line.strip()
        mb = _BOLD_CHANNEL_RE.match(s)
        if mb:
            if channel and entries:
                blocks.append((channel, entries))
            channel = "drive_up" if ("up" in mb.group("ch") or "thru" in mb.group("ch")) else mb.group("ch").lower()
            entries = []
            # the first entry may sit on the same line ("**Lobby** Monday-Thursday: ...")
            md = _DAY_GROUP_RE.match(mb.group("rest").strip())
            if md:
                entries.append(_entry_from_match(md))
            continue
        if channel is None or not s:
            continue
        # block ends at the next non-entry structural line
        if s.startswith("**") or s.startswith("#") or s.startswith("["):
            if entries:
                blocks.append((channel, entries))
            channel, entries = None, []
            continue
        md = _DAY_GROUP_RE.match(s)
        if md:
            entries.append(_entry_from_match(md))
        elif s.startswith("Branch hours are"):
            continue
        elif entries and re.search(r"a\.\s?m\.|p\.\s?m\.|noon", s, re.I):
            # wrapped entry continuation "<time>( )p.m." — attach to last entry
            entries[-1]["spec"] = f"{entries[-1]['spec']} {s}".strip()
    if channel and entries:
        blocks.append((channel, entries))
    return blocks


def extract_branch_hours(text: str) -> list[dict]:
    """Lobby/drive-up schedule claims. Anchored on a 'Branch hours are:' intro."""
    claims: list[dict] = []
    pos = 0
    while True:
        m = _HOURS_ANCHOR_RE.search(text, pos)
        if not m:
            break
        window_end = min(len(text), m.end() + 1200)
        window = text[m.end():window_end]
        name = None
        nm = _BRANCH_NAME_RE.search(text[max(0, m.start() - 400):m.start()])
        if nm:
            name = re.sub(r"\s+dupaco$", "", nm.group("name").strip(), flags=re.I).lower()
        for channel, entries in _hours_blocks(window):
            if len(entries) < 3:
                continue
            claims.append({
                "tier_dims": {
                    "kind": "branch_hours",
                    "channel": channel,
                    "branch": name,
                    "schedule": _schedule_text(entries),
                },
                "value": 0.0,
                "value_text": "",
                "min_earn": None,
                "quote": (entries[0]["days"] + ": " + entries[0]["spec"])[:200],
            })
        pos = window_end
    return claims


def _norm_addr_spacing(addr: str) -> str:
    return re.sub(r"\s+", " ", addr).strip()


def extract_branch_addresses(text: str) -> list[dict]:
    """Locator blocks: '### Dupaco Credit Union / Dupaco Branch / ADDRESS'."""
    claims: list[dict] = []
    lines = text.split("\n")
    for i, raw in enumerate(lines):
        if not _LOCATOR_TYPE_BRANCH_RE.match(raw.strip()):
            continue
        addr = None
        for j in range(i + 1, min(len(lines), i + 4)):
            ma = _ADDRESS_RE.match(lines[j].strip())
            if ma:
                addr = ma
                break
        if not addr:
            continue
        display = f"{_norm_addr_spacing(addr.group('addr'))}, {addr.group('zip')}"
        claims.append({
            "tier_dims": {
                "kind": "branch_address",
                "city": addr.group("city").strip().lower(),
                "city_display": addr.group("city").strip(),
                "state": addr.group("state"),
                "zip": addr.group("zip"),
                "address_display": display,
            },
            "value": 0.0,
            "value_text": display,
            "min_earn": None,
            "quote": raw.strip()[:200],
        })
    return claims


def extract_branch_notices(text: str) -> list[dict]:
    """"full-service branches at Key West and Sycamore Street" (Hy-Vee closure)."""
    claims: list[dict] = []
    m = _HYVEE_ALTERNATIVES_RE.search(text or "")
    if not m or "hy-vee" not in (text or "").lower():
        return claims
    alts = _norm_addr_spacing(m.group("alts")).strip().rstrip(" ,")
    claims.append({
        "tier_dims": {
            "kind": "branch_notice",
            "subject": "hyvee_locust_full_service_alternatives",
            "alternatives": alts,
        },
        "value": 0.0,
        "value_text": alts,
        "min_earn": None,
        "quote": m.group(0)[:200],
    })
    return claims


# S2.3 change events: dated branch events announced in prose. The corpus's
# only event shape so far is a closure ("This location will close March 31,
# 2026." on the newsroom announcement). Subjects are bound from page content
# (the page must name the branch), never from URLs.
_CLOSURE_RE = re.compile(
    r"(?:location|branch|store)[^\n.]{0,120}?\b(?:will\s+)?clos(?:e|ing|ed)\s+"
    r"(?P<mon>January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(?P<day>\d{1,2}),?\s+(?P<yr>\d{4})",
    re.I,
)


def _event_subject(text: str) -> tuple[str, str] | None:
    """Canonical (subject, label) for a dated event page, or None if unknown."""
    low = (text or "").lower()
    if "hy-vee" in low or "hyvee" in low:
        return "hyvee_locust", "Hy-Vee"
    return None


def extract_branch_events(text: str) -> list[dict]:
    """Dated branch events (kind=branch_event): event, ISO date, published form.

    value_text keeps the site's OWN rendering ("March 31, 2026") — event dates
    are quoted to members exactly as published (R3), while event_date carries
    the ISO form for temporal logic (past vs scheduled).
    """
    claims: list[dict] = []
    bound = _event_subject(text)
    if not bound:
        return claims
    subject, label = bound
    seen: set[tuple] = set()
    for m in _CLOSURE_RE.finditer(text or ""):
        mon = MONTHS[m.group("mon").lower()]
        day = int(m.group("day"))
        yr = int(m.group("yr"))
        iso = f"{yr:04d}-{mon:02d}-{day:02d}"
        ck = (subject, "close", iso)
        if ck in seen:
            continue
        seen.add(ck)
        claims.append({
            "tier_dims": {
                "kind": "branch_event",
                "subject": subject,
                "label": label,
                "event": "close",
                "event_date": iso,
            },
            "value": 0.0,
            "value_text": f"{m.group('mon')} {day}, {yr}",
            "min_earn": None,
            "quote": m.group(0)[:200],
        })
    return claims


def extract_branches(text: str) -> list[dict]:
    """Prose-statement branch claims for one page (hours + addresses + notices
    + dated events)."""
    out: list[dict] = []
    out.extend(extract_branch_hours(text))
    out.extend(extract_branch_addresses(text))
    out.extend(extract_branch_notices(text))
    out.extend(extract_branch_events(text))
    return out
