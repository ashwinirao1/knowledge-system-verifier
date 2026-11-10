"""Facts extractor (S1.5): programs, member services, wallet support, annual
series, and current site links — prose, not tables.

Claim shapes (mirroring branches.py: value=0.0 text claims unless a real number
carries the fact):

    site_link:      [label](https://...) CTA anchors — the URL (query and
                    fragment stripped) IS the fact; the role is bound by the
                    anchor label + target host. Legacy trap URLs
                    (`info.dupaco.com/*`, `/locations/branch-hours`) exist in
                    no snapshot (verified), so latest-snapshot trust
                    resolution keeps them out for free.
    program:        assistance programs ("...through the Home$tart program.
                    This initiative provides up to $15,000 in assistance,
                    applied as a credit toward down payment and closing
                    costs...") — value carries the dollar amount so the
                    scorer's value match sees it.
    service:        change/review-your-information how-tos ("...by logging
                    into your account and making the desired changes. You may
                    also call Dupaco at 800-373-7600...").
    wallet:         mobile-wallet support ("Add your Dupaco debit and credit
                    cards to your phone's Apple Pay, Google Pay or Samsung
                    Pay...") plus the set-as-default capability flag.
    annual_series:  newsroom "In <year> alone:" recap bullets — the year is a
                    tier dim, so different years are different facts (R5); an
                    unbound-year question answers the chronological series.

Extraction is label- and sentence-driven; nothing is keyed to a question.
These families stay OUT of the conflicts views — programs, services, wallets
and links legitimately differ page to page, which is not a contradiction (R5).
"""
from __future__ import annotations

import re

_ANCHOR_RE = re.compile(
    r"[ \t]*\[(?P<label>[^\]\n]{1,140})\]\((?P<url>https?://[^)\s]+)\)"
)

# ------------------------------------------------------------- site links
_LOCATOR_LABEL_RE = re.compile(
    r"\b(?:find a branch(?: or ATM)?|branch(?:es)? (?:and|or) ATM|shared branch(?:es)?)\b",
    re.I,
)
_JOIN_LABEL_RE = re.compile(r"\b(?:become a member|join(?: dupaco)?)\b", re.I)
# only application CTA hosts count: "Become a member" -> /about/join on
# marketing pages is navigation, not the application form
_JOIN_HOST_RE = re.compile(r"join\.dupaco\.com", re.I)
_LOCATOR_URL_RE = re.compile(r"dupaco\.com/contact", re.I)


def norm_url(url: str) -> str:
    """Deterministic published-link form: query string and fragment stripped."""
    base = (url or "").split("#", 1)[0].split("?", 1)[0]
    return base


def extract_site_links(text: str) -> list[dict]:
    """Primary nav/CTA application links (role-tagged by label + host)."""
    claims: list[dict] = []
    for m in _ANCHOR_RE.finditer(text or ""):
        label = m.group("label").strip()
        url = m.group("url").strip()
        base = norm_url(url)
        if not base:
            continue
        role = None
        if _JOIN_HOST_RE.search(url) and _JOIN_LABEL_RE.search(label):
            role = "join_application"
        elif _LOCATOR_URL_RE.search(url) and _LOCATOR_LABEL_RE.search(label):
            role = "branch_atm_locator"
        if role is None:
            continue
        claims.append({
            "tier_dims": {"kind": "site_link", "role": role, "url": base},
            "value": 0.0,
            "value_text": base,
            "quote": f"{label} -> {base}"[:200],
        })
    return claims


# ---------------------------------------------------------------- programs
_ASSIST_RE = re.compile(
    r"provides\s+up\s+to\s+\$(?P<amt>[\d,]+)(?:\.\d+)?\s+in\s+(?P<kind>assistance|grant funds)"
    r"(?:,\s*applied as a credit toward\s+(?P<purpose>[^.]{0,140}?))?(?=\.)",
    re.I,
)
_PROGRAM_NAME_RE = re.compile(r"(?:the\s+)?(?P<name>[A-Za-z$][\w$'-]{2,28})\s+program\b", re.I)
_FHLB_RE = re.compile(r"(?:Federal Home Loan Bank|FHLB)(?:\s+of\s+Des\s+Moines)?", re.I)
_AUDIENCE_RE = re.compile(r"\b(?P<aud>(?:eligible|first-time)\s+[a-z]+s?\b)", re.I)
_FHLB_NAME = "FHLB (Federal Home Loan Bank of Des Moines)"


def extract_programs(text: str) -> list[dict]:
    """Assistance-program facts: program name + up-to-$N assistance."""
    claims: list[dict] = []
    for m in _ASSIST_RE.finditer(text or ""):
        back = text[max(0, m.start() - 400):m.start()]
        nm = _PROGRAM_NAME_RE.search(back)
        if not nm:
            continue
        name = nm.group("name").strip()
        sponsor = "fhlb" if _FHLB_RE.search(back) else ""
        purpose_raw = (m.group("purpose") or "").strip().rstrip(" ,")
        audience = ""
        parts = re.split(r"\s+for\s+", purpose_raw, maxsplit=1)
        if len(parts) == 2:
            purpose_raw, tail = parts[0].strip().rstrip(" ,"), parts[1]
            am = _AUDIENCE_RE.search(" for " + tail)
            if am:
                audience = am.group("aud")
        purpose = purpose_raw
        amt = int(m.group("amt").replace(",", ""))
        claims.append({
            "tier_dims": {
                "kind": "program",
                "program": name.lower(),
                "program_display": f"{name} program",
                "sponsor": sponsor,
                "audience": audience,
                "purpose": purpose,
            },
            "value": float(amt),
            "value_text": str(amt),
            "quote": m.group(0)[:200],
        })
    return claims


# ---------------------------------------------------------------- services
_SERVICE_RE = re.compile(
    r"you (?:can|may) (?:review and change|update|correct)",
    re.I,
)
_SERVICE_PHONE_RE = re.compile(r"call\s+\S{0,30}?\s*at\s+((?:\d{3}[-–]?\d{3}[-–]?\d{4}))\b", re.I)
_SERVICE_EMAIL_RE = re.compile(r"email(?:\s+us)?\s+at\s+(?P<em>[\w.+-]+@[\w.-]+)", re.I)
_SERVICE_BRANCH_RE = re.compile(r"visit (?:a|ana?|us|your)?\s*Dupaco?\s*branch in person|in person", re.I)


def extract_services(text: str) -> list[dict]:
    """How-to-change-your-info service claims (channels as corpus phrasing).

    The corpus states the channels across two sentences ("...review and change
    your personal information by logging into your account... You may also
    call Dupaco at 800-373-7600..."), so the trigger's window spans both.
    """
    claims: list[dict] = []
    for m in _SERVICE_RE.finditer(text or ""):
        blob = text[m.start():m.start() + 700]
        phone_m = _SERVICE_PHONE_RE.search(blob)
        email_m = _SERVICE_EMAIL_RE.search(blob)
        branch = bool(_SERVICE_BRANCH_RE.search(blob))
        if not (phone_m or email_m or branch):
            continue
        login = bool(re.search(r"log(?:ging|s?) in(?:to)? (?:to )?your account", blob, re.I))
        claims.append({
            "tier_dims": {
                "kind": "service",
                "service": "review_change_personal_info",
                "login": login,
                "phone": phone_m.group(1) if phone_m else "",
                "email": email_m.group("em") if email_m else "",
                "branch": branch,
            },
            "value": 0.0,
            "value_text": phone_m.group(1) if phone_m else "",
            "quote": blob[:200] if not phone_m else f"... call at {phone_m.group(1)} ...",
        })
    return claims


# ----------------------------------------------------------------- wallets
_PAY_ITEM_RE = re.compile(r"\b(?:Apple Pay|Google Pay|Samsung Pay)\b")
_WALLET_DEFAULT_RE = re.compile(r"\bset (?:your new card|one|it) as your default\b", re.I)


def extract_wallets(text: str) -> list[dict]:
    """Mobile-wallet support: product names as published + default capability.

    Mentions are grouped when they sit within ~500 chars of the next one; a
    group only spans into a claim when its neighbourhood names Dupaco cards
    AND an add/compatible-with verb AND at least two wallet names — a bare
    three-name page section is not a card-support statement.
    """
    claims: list[dict] = []
    text = text or ""
    hits = list(_PAY_ITEM_RE.finditer(text))
    if not hits:
        return claims
    groups: list[list] = []
    group = [hits[0]]
    for h in hits[1:]:
        if h.start() - group[-1].end() <= 500:
            group.append(h)
        else:
            groups.append(group)
            group = [h]
    groups.append(group)
    for g in groups:
        lo = max(0, g[0].start() - 400)
        hi = min(len(text), g[-1].end() + 300)
        span = text[lo:hi]
        low = span.lower()
        if not (("add" in low or "compatible" in low) and "dupaco" in low):
            continue
        names: list[str] = []
        for nm in _PAY_ITEM_RE.finditer(span):
            if nm.group(0) not in names:
                names.append(nm.group(0))
        if len(names) < 2:
            continue  # one wallet name alone is not the support statement
        if len(names) == 1:
            display = names[0]
        else:
            display = ", ".join(names[:-1]) + f" or {names[-1]}"
        default_ok = bool(_WALLET_DEFAULT_RE.search(span))
        have_cards = bool(re.search(r"\bdebit\b.{0,60}?\bcredit\b", span, re.I | re.S))
        claims.append({
            "tier_dims": {
                "kind": "wallet",
                # pipe-joined (not a tuple): every tier dim must stay a JSON
                # scalar (nested lists break claim hashing in the ledger)
                "wallets": "|".join(names),
                "wallets_display": display,
                "default_ok": default_ok,
                "cards": "debit and credit cards" if have_cards else "cards",
            },
            "value": 0.0,
            "value_text": display,
            "quote": display[:200],
        })
    return claims


# ------------------------------------------------------------ annual series
_RECAP_RE = re.compile(r"^In (?P<year>20\d\d) alone:\s*$", re.M)
_APPROX_RE = re.compile(r"\b(nearly|about|over|more than|almost|roughly)\b", re.I)
_VTO_RE = re.compile(r"(?:used|took)[^.]{0,140}?volunteer\s+time\s+off\b", re.I)
_VTO_NUM_RE = re.compile(
    r"(\d[\d,]*)\s*(?:Dupaco\s+)?(?:employees?|team members?)\s+(?:used|took)", re.I
)
_HOURS_RE = re.compile(r"volunteered\s+(?:a total of\s+)?(?:\*\*)?(\d[\d,]*)\s*hours", re.I)
_BOARDS_RE = re.compile(r"served on\s+(?:\*\*)?(\d[\d,]*)\s*(?:nonprofit\s+)?boards?", re.I)
_EMPLOYEES_VOL_RE = re.compile(
    r"(?:\*\*)?(?P<mod>Nearly\s+|About\s+|Almost\s+|Over\s+|More than\s+)?(?P<n>\d[\d,]*)"
    r"\s*(?:Dupaco\s+)?employees?\s+volunteered\b",
    re.I,
)


def _series_claim(series: str, year: int, n: str, quote: str, approx: bool) -> dict:
    value = float(n.replace(",", ""))
    return {
        "tier_dims": {
            "kind": "annual_series",
            "series": series,
            "year": year,
            "approx": approx,
        },
        "value": value,
        "value_text": str(int(value)),
        "quote": quote[:200],
    }


def extract_annual_series(text: str) -> list[dict]:
    """Newsroom 'In <year> alone:' recap bullets → per-year series facts."""
    claims: list[dict] = []
    text = text or ""
    for m in _RECAP_RE.finditer(text):
        year = int(m.group("year"))
        window = text[m.end():m.end() + 1400]
        # logical bullets, not physical lines (wrapping mentions cross lines)
        for chunk in re.split(r"\n\s*-\s+", window)[1:]:
            s = chunk.strip().replace("**", "")
            s = re.sub(r"\s+", " ", s)
            if _VTO_RE.search(s):
                nm = _VTO_NUM_RE.search(s)
                if nm:
                    claims.append(_series_claim("employees_vto", year, nm.group(1), s, approx=False))
                continue
            hm = _HOURS_RE.search(s)
            if hm:
                claims.append(_series_claim("volunteer_hours", year, hm.group(1), s, approx=False))
                continue
            bm = _BOARDS_RE.search(s)
            if bm:
                claims.append(_series_claim("board_seats", year, bm.group(1), s, approx=False))
                continue
            em = _EMPLOYEES_VOL_RE.search(s)
            if em:
                approx = bool(em.group("mod")) or bool(_APPROX_RE.search(s[: em.start()]))
                claims.append(_series_claim("employees_volunteered", year, em.group("n"), s, approx=approx))
    return claims


def extract_facts(text: str) -> list[dict]:
    """All prose-fact claims for one page (S1.5). Cheap gates first: most
    pages carry none of this, so each extractor is short-circuited."""
    out: list[dict] = []
    low = (text or "").lower()
    if "join.dupaco.com" in low or "dupaco.com/contact" in low:
        out.extend(extract_site_links(text))
    if "program" in low and re.search(r"up\s+to\s+\$", text, re.I):
        out.extend(extract_programs(text))
    if (
        "you can review" in low or "you may review" in low
        or "you can update" in low or "you may update" in low
        or "you can correct" in low or "you may correct" in low
    ):
        out.extend(extract_services(text))
    if "add" in low and " pay" in low and "dupaco" in low:
        out.extend(extract_wallets(text))
    if "alone:" in low:
        out.extend(extract_annual_series(text))
    return out
