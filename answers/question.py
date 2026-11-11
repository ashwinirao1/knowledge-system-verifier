"""Question parser (S0.3 v0 + S1.1): rule grammar → product/metric/tier slots.

Families:  certificate  → 17-month special / jumbo / IRA term certs
           deposit      → Share Savings, savings variants, money markets,
                          checking (personal + business), with balance tiers

Questions neither family can slot return `None` → the answer path declines
honestly instead of guessing (R1).
"""
from __future__ import annotations

import re

from trust import MONTH_ABBRS, MONTHS

WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "twenty": 20, "twenty-five": 25, "thirty": 30, "thirty-six": 36, "forty": 40,
    "forty-eight": 48, "fifty": 50, "sixty": 60,
}
_MONTHS_RE = re.compile(r"(\d{1,2})\s*[-\s]?\s*month", re.I)
_WORD_MONTH_RE = re.compile(
    r"\b(" + "|".join(WORD_NUMBERS) + r")\s*[-\s]?\s*months?\b", re.I
)
# "CD" = certificate of deposit (the everyday synonym); the bare-noun
# "special" trigger is TERM-ANCHORED ("the 17-month special") — an unanchored
# "special" would over-trigger on "any special requirements..." phrasings.
_CERT_RE = re.compile(r"\b(certificates?|certs?|cds?)\b", re.I)
_CERT_SPECIAL_RE = re.compile(
    r"\b\d{1,2}[\s-]*(?:month|year)s?[\s-]*(?:fixed[\s-]*)?(?:jumbo[\s-]*)?specials?\b",
    re.I,
)
_SPECIAL_RE = re.compile(r"\bspecials?\b", re.I)
_REGULAR_RE = re.compile(r"\bregulars?\b|\bstandard\b", re.I)
_JUMBO_RE = re.compile(r"\bjumbos?\b", re.I)
_IRA_RE = re.compile(r"\b(iras?|roth|traditional)\b", re.I)
_DIV_RE = re.compile(r"dividend\s+rate", re.I)

# ---------------------------------------------------------------- deposits
# named products first, generic fallbacks last; first hit per canonical wins
_DEPOSIT_PRODUCT_RES = [
    (re.compile(r"\bshare\s+savings\b", re.I), "share_savings"),
    (re.compile(r"\bbright\s+savings\b", re.I), "bright_savings"),
    (re.compile(r"\bhigh[- ]yield\b", re.I), "high_yield_savings"),
    (re.compile(r"\bmoney\s+market", re.I), "investors_choice_mm"),
    (re.compile(r"\byou[- ]?name[- ]?it\b", re.I), "you_name_it_savings"),
    (re.compile(r"\bholiday\s+club\b", re.I), "holiday_club"),
    (re.compile(r"\blaunchpad\b", re.I), "launchpad_savings"),
    (re.compile(r"\bchecking\b", re.I), "checking_family"),
]
_GENERIC_SAVINGS_RE = re.compile(r"\bsavings?\b", re.I)
_CHECKING_FAMILY = ["free_checking", "first_rate_checking"]

_DO_ANY_RE = re.compile(r"\bdo any\b|\bdoes any\b|\bis there (?:a|any)\b", re.I)
_HIGHEST_RE = re.compile(r"\b(highest|best|max(?:imum)?|tops?\s+out|top|the most)\b", re.I)
_PCT_HYPO_RE = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*%", re.I)
_TIER_RANGE_RE = re.compile(
    r"balance[s]?\s+(?:(?:is|was|are|'s)\s+)?(?:between|of|from|over|above)\s+\$?"
    r"([\d,]+(?:\.\d+)?)\s*(?:(?:and|to|-|–)\s*\$?([\d,]+(?:\.\d+)?))?",
    re.I,
)
_TIER_RANGE_ALT_RE = re.compile(
    r"\$([\d,]+(?:\.\d+)?)\s*(?:-|–|to|and)\s*\$?([\d,]+(?:\.\d+)?)", re.I
)


# ---------------------------------------------------------------- loans (S1.2)
_LOAN_FAMILY_RES = [
    (re.compile(r"\bmortgage|home\s+loan\b", re.I), "mortgage"),
    (re.compile(r"\brefinanc", re.I), "mortgage"),
    (re.compile(r"\bhome\s+equity|heloc\b", re.I), "home_equity"),
    (re.compile(r"\bhome\s+improvement\b", re.I), "home_improvement"),
    (re.compile(r"\bboat\b|\brv\b|\brecreational\b", re.I), "boat_rv"),
    (re.compile(r"\bpersonal\s+loans?\b", re.I), "personal"),
    (re.compile(r"\bauto\b|\bcar\b|\bvehicle\b|\bmotorcycle\b", re.I), "auto"),
]
_MODEL_YEAR_Q_RE = re.compile(
    r"\b(?:model[- ]year\s*(?:vehicle)?\s*)?(20\d\d)\b", re.I
)
_TERM_YEARS_RE = re.compile(r"\b(\d{1,2})\s*[-\s]?years?\b", re.I)


# ------------------------------------------------------------------ cards (S1.3)
_CARDS_TRIGGER_RE = re.compile(r"\bcredit cards?\b|\bvisa\b", re.I)
_CARDS_PRODUCT_RES = [
    (re.compile(r"\bbusiness\s+platinum\b", re.I), "business_platinum_visa"),
    (re.compile(r"\bbusiness\s+rewards\b", re.I), "business_rewards_visa"),
    (re.compile(r"\bplatinum\s+visa\b", re.I), "platinum_visa"),
    (re.compile(r"\brewards\s+visa\b", re.I), "rewards_visa"),
]
_CARDS_BUSINESS_RE = re.compile(r"\bbusiness\b", re.I)
_CARDS_PERSONAL_RE = re.compile(r"\bpersonal\b", re.I)


def _parse_cards(q: str) -> dict | None:
    if not _CARDS_TRIGGER_RE.search(q):
        return None
    products: list[str] = []
    for rx, canon in _CARDS_PRODUCT_RES:
        if rx.search(q):
            products.append(canon)
    member = None
    if _CARDS_BUSINESS_RE.search(q):
        member = "business"
    elif _CARDS_PERSONAL_RE.search(q):
        member = "personal"
    rate_period = "standard" if re.search(r"\bstandard\b|\bpurchase\b", q) else None
    return {
        "family": "cards",
        "products": products,
        "member": member,
        "rate_period": rate_period,
    }


# ----------------------------------------------------------------- branch (S1.4)
_HOURS_TRIGGER_RE = re.compile(r"\bhours?\b|\bopen\b|\bclos", re.I)
_DRIVE_UP_RE = re.compile(r"\bdrive[- ]?up\b|\bdrive.?thru\b|\bdrive.?through\b", re.I)
_ADDRESS_TRIGGER_RE = re.compile(r"\baddress\b|\blocated\b|\bwhere is\b", re.I)
_HYVEE_RE = re.compile(r"\bhy-?vee\b", re.I)
_ALL_SAME_RE = re.compile(r"\ball\b.*\bsame\b|\bsame\b.*\ball\b|every\s+(?:\w+\s+){0,2}branch", re.I)
# S2.3 change events: "when does/did/will the X branch close" is an EVENT
# question, not an hours question — it must win over the hours trigger, which
# also matches "\bclos". Opening events are future scope (no corpus shape yet).
_EVENT_WHEN_RE = re.compile(
    r"\bwhen\s+(?:does|did|will|is|was|'s)\b"
    r"|\bclosure date\b|\bwhat date\b|\bon what date\b|\bwhat day\b",
    re.I,
)
_EVENT_STILL_RE = re.compile(
    r"\bstill\s+open\b|\bhas\s+\S.+\bclosed\b|\bdid\s+\S.+\bclose\b"
    r"|\b(?:stay|stayed|remain|remains|remained)\s+open\b"
    # "Is the Hy-Vee branch open as of October 2026?" — a branch STATUS ask,
    # unless a weekday follows ("open on Sundays" is an hours ask)
    r"|\bis\s+the\s+((?:(?!\bthe\b)[\w'\- ]){3,40}?)\s+branch\s+open\b"
    r"(?![a-z ,]*(?:mon|tues|wednes|thurs|fri|satur|sun)day)",
    re.I,
)
_EVENT_NAMED_RE = re.compile(
    # tempered: "the" may not appear INSIDE the captured name, so
    # "the closure date for the Hy-Vee branch" captures "Hy-Vee",
    # not "closure date for the hy-vee"
    r"\bthe\s+((?:(?!\bthe\b)[a-z0-9'\- ]){3,40}?)\s+branch\b"
    r"|\bthe\s+((?:(?!\bthe\b)[a-z0-9'\- ]){3,40}?)\s+location\b",
    re.I,
)


def _norm_subject(name: str | None) -> str | None:
    """'Hy-Vee' -> 'hyvee' — the token matched against a claim's subject key."""
    if not name:
        return None
    s = re.sub(r"[^a-z0-9]+", "", name.lower())
    return s or None


def _event_slots(q: str, mode: str) -> dict:
    named = None
    m = _EVENT_NAMED_RE.search(q)
    if m:
        named = (m.group(1) or m.group(2)).strip()
    return {
        "family": "branch",
        "mode": mode,
        "branch_subject": _norm_subject(named),
        "branch_name": named,
    }


def _parse_branch(q: str) -> dict | None:
    # a NAMED branch ("... hours for the Mullan Avenue branch") makes the item
    # branch-specific: only claims for that branch may be used or it's a refuse
    named = None
    m = re.search(
        r"for the ((?:(?!\bthe\b)[a-z0-9'\- ]){3,40}?) branch(?:\?|$)"
        r"|at the ((?:(?!\bthe\b)[a-z0-9'\- ]){3,40}?) branch",
        q,
    )
    if m:
        named = (m.group(1) or m.group(2)).strip()
    if not named:
        # "a branch on Mullan Avenue" — a street-locator naming, just as
        # branch-specific as "the X branch": ungrounded names must refuse,
        # never fall back to generic hours presented as this branch's (R1)
        m2 = re.search(
            r"branch\s+(?:on|at)\s+([a-z0-9'\- ]{3,40}?)(?:\?|$|,| and\b|,? and what\b|\bin\b)",
            q, re.I,
        )
        if m2:
            named = m2.group(1).strip()
    if _EVENT_WHEN_RE.search(q) and re.search(r"\bclos", q, re.I):
        return _event_slots(q, "event_when")
    if _EVENT_STILL_RE.search(q):
        return _event_slots(q, "event_status")
    if _HOURS_TRIGGER_RE.search(q):
        mode = "hours_drive_up" if _DRIVE_UP_RE.search(q) else "hours_lobby"
        if _ALL_SAME_RE.search(q) and not _DRIVE_UP_RE.search(q):
            mode = "hours_same"
        return {
            "family": "branch",
            "mode": mode,
            "channel": "drive_up" if _DRIVE_UP_RE.search(q) else "lobby",
            "branch_name": named,
        }
    if _HYVEE_RE.search(q):
        return {"family": "branch", "mode": "hyvee_alternatives"}
    if _ADDRESS_TRIGGER_RE.search(q):
        m = re.search(r"\b([a-z]{4,})\s+branch\b|\bbranch\s+(?:in|at)\s+([a-z]{4,})\b", q)
        city = (m.group(1) or m.group(2)).lower() if m else None
        if city is None and named:
            city = named
        return {"family": "branch", "mode": "address", "city": city}
    return None


# ------------------------------------------------------- changes (S2.3)
# "What changed between May and September?" / "What changed since June?" —
# answered from the transition index recorded at ingest. Windows are
# (year, month) points; year None = any year (deterministic, corpus-agnostic).
_CHANGES_TRIGGER_RE = re.compile(
    r"\bwhat\s+(?:has\s+)?changed\b|\banything\s+changed\b"
    r"|\bwhat(?:'s| is)\s+new\b|\b(?:which|what)\s+rates?\s+(?:have\s+)?changed\b",
    re.I,
)
_BETWEEN_RE = re.compile(
    r"between\s+([a-z]+|\d{4}-\d{2})(?:\s+(\d{4}))?\s+and\s+([a-z]+|\d{4}-\d{2})(?:\s+(\d{4}))?",
    re.I,
)
_SINCE_RE = re.compile(r"since\s+([a-z]+|\d{4}-\d{2})(?:\s+(\d{4}))?", re.I)


def _month_point(tok: str, year: str | None) -> tuple[int | None, int] | None:
    """'May'/'sep'/'2026-05' (+ optional explicit year) -> ((y|None), month)."""
    t = tok.lower()
    y: int | None = None
    if re.match(r"^\d{4}-\d{2}$", t):
        y, month = int(t[:4]), int(t[5:7])
        if not 1 <= month <= 12:
            return None
    else:
        month = MONTHS.get(t) or MONTH_ABBRS.get(t)
        if not month:
            return None
    if year:
        y = int(year)
    return (y, month)


def _parse_changes(q: str) -> dict | None:
    if not _CHANGES_TRIGGER_RE.search(q):
        return None
    frm = to = None
    label_from = label_to = None
    m = _BETWEEN_RE.search(q)
    if m:
        frm = _month_point(m.group(1), m.group(2))
        to = _month_point(m.group(3), m.group(4))
        if frm:
            label_from = m.group(1).capitalize() + (f" {m.group(2)}" if m.group(2) else "")
        if to:
            label_to = m.group(3).capitalize() + (f" {m.group(4)}" if m.group(4) else "")
    else:
        m = _SINCE_RE.search(q)
        if m:
            frm = _month_point(m.group(1), m.group(2))
            if frm:
                label_from = m.group(1).capitalize() + (f" {m.group(2)}" if m.group(2) else "")
    if frm is None and to is None:
        # a "what changed" question with no parsable window asks about the
        # whole ledger history — the widest deterministic window
        return {"family": "changes", "window_from": None, "window_to": None,
                "label_from": None, "label_to": None}
    return {"family": "changes", "window_from": frm, "window_to": to,
            "label_from": label_from, "label_to": label_to}


# ------------------------------------------------------------------ facts (S1.5)
_SERIES_ALIASES = {
    "used volunteer time off|volunteer time off|VTO": "employees_vto",
    "volunteer hours": "volunteer_hours",
    "nonprofit boards": "board_seats",
}
_FACTS_UPDATE_RE = re.compile(
    r"\bcontact information\b|\bcontact info\b|\bchange (?:my|the|your) "
    r"(?:address|phone|email)|\bupdate (?:my|the|your) (?:address|phone|email)|"
    r"\bpersonal information\b",
    re.I,
)
_FACTS_WALLET_RE = re.compile(
    r"\bmobile wallets?\b|\bwallets?\b|\b(?:apple|google|samsung) pay\b", re.I
)
_FACTS_PAY_RE = re.compile(r"\b(?:apple|google|samsung) pay\b", re.I)
_FACTS_PROGRAM_RE = re.compile(r"\bprogram\b", re.I)
_FACTS_PROGRAM_NAME_RE = re.compile(
    r"(?:dupaco'?s?|the)\s+([\w$'-]{2,28}(?:\s+[\w$'-]{2,28}){0,2})\s+program\b", re.I
)
_FACTS_LINK_RE = re.compile(
    r"\blinks?\b|\burls?\b|\bwhich page\b|\bwhich web page\b"
    r"|\bwhere (?:can|do|to) i (?:find|see|get|look)\b|\bwhere on (?:your|the) (?:web ?)?site\b",
    re.I,
)
_FACTS_LOCATOR_RE = re.compile(r"\blocat(?:or|ing)\b|\bfind a branch\b|\bbranch (?:and|or) ATM\b", re.I)
_FACTS_JOIN_RE = re.compile(
    r"\b(?:how do i (?:join|become a member)|join dupaco(?: online)?|become a (?:dupaco )?member)\b",
    re.I,
)
_FACTS_YEAR_RE = re.compile(r"\bin (20\d\d)\b", re.I)


def _parse_facts(q: str) -> dict | None:
    """Facts family (S1.5): wallet support, annual series, services, programs,
    links, entity facts (S2.4). Runs BEFORE the product families so wording
    like "cards to a mobile wallet" or "CD rates link" never lands in the APR
    paths."""
    if _FACTS_WALLET_RE.search(q) and (_FACTS_PAY_RE.search(q) or "card" in q):
        return {"family": "facts", "mode": "wallet"}
    if re.search(r"how many\b", q) and re.search(r"volunteer|VTO", q, re.I):
        series = "employees_vto" if re.search(r"volunteer time off|\bvto\b", q, re.I) else "volunteer_hours"
        m = _FACTS_YEAR_RE.search(q)
        return {"family": "facts", "mode": "series", "series": series,
                "year": int(m.group(1)) if m else None}
    if re.search(r"\bhow many\b|\b(?:total|exact|approx(?:imate)?)\s+number\s+of\b", q, re.I) \
            and re.search(r"branch(?:es)?\b|branch office", q, re.I):
        # published-count semantics: the freshest published statement of the
        # count, never a naive count of ledger rows (R5 replica discipline).
        # "number of" is only counted when quantified ("total/exact number of")
        # so "the phone number of the branch" can never route here.
        return {"family": "facts", "mode": "entity", "entity": "branch_count"}
    if re.search(r"routing(?:\s+number)?|aba number", q, re.I):
        # "Can you repeat the routing number?" contains the noun phrase —
        # replay questions need no separate anaphora rule
        return {"family": "facts", "mode": "entity", "entity": "routing_number"}
    if re.search(r"\bforbes\b", q, re.I):
        return {"family": "facts", "mode": "entity", "entity": "forbes_recognition"}
    if not _FACTS_LINK_RE.search(q) and re.search(
        r"who (?:is|'s|can)\b.*\b(?:eligible|join|become)|eligib\w* to (?:become|join)"
        r"|become a (?:dupaco )?member|membership eligib"
        r"|eligib\w*\s+for\s+(?:dupaco\s+)?membership"
        r"|what do i need to (?:be\s+)?eligib"
        r"|can (?:anyone|anybody|just anyone)\b.*\bjoin",
        q, re.I,
    ):
        # eligibility must precede the join-LINK binding below — several of
        # these shapes also match "become a member"/"join", but they ask for
        # the RULE, not the URL. Exception: an explicit LINK/URL/PAGE ask
        # ("what's the link to become a member?") wants the URL — that falls
        # through to the join-link path below (S3.4 group-split fix).
        return {"family": "facts", "mode": "entity", "entity": "membership_eligibility"}
    if re.search(r"\bstudents?\b", q, re.I) and re.search(r"\bloan", q, re.I):
        # "I'm a student ... any loan options?" — student and loan need not be
        # adjacent ("student loan" alone would miss dup-101's phrasing)
        return {"family": "facts", "mode": "entity", "entity": "student_loan"}
    if _FACTS_UPDATE_RE.search(q):
        return {"family": "facts", "mode": "update_contact"}
    if _FACTS_PROGRAM_RE.search(q):
        m = _FACTS_PROGRAM_NAME_RE.search(q)
        return {"family": "facts", "mode": "program",
                "program": (m.group(1).lower() if m else None)}
    if _FACTS_LINK_RE.search(q):
        if _FACTS_LOCATOR_RE.search(q):
            return {"family": "facts", "mode": "link", "link_role": "branch_atm_locator"}
        if re.search(r"\brate", q) and _CERT_RE.search(q):
            return {"family": "facts", "mode": "link", "link_family": "certificate"}
        if re.search(r"\brate", q) and _GENERIC_SAVINGS_RE.search(q):
            return {"family": "facts", "mode": "link", "link_family": "deposit"}
    if _FACTS_JOIN_RE.search(q):
        return {"family": "facts", "mode": "link", "link_role": "join_application"}
    return None


def _parse_loan(q: str) -> dict | None:
    # ARM / non-conventional products are not on any rate sheet corpus-wide:
    # answering with the fixed-conventional tiers would be a wrong-fact answer.
    if re.search(r"\badjustable\b|\barm\b|5/1|7/1", q, re.I):
        return None
    fam = None
    for rx, f in _LOAN_FAMILY_RES:
        if rx.search(q):
            fam = f
            break
    if not fam:
        return None

    metric = "apr" if re.search(r"\bapr\b", q) else "rate"
    term_months = None
    term_years = None
    m = _MONTHS_RE.search(q)
    if m:
        term_months = int(m.group(1))
    else:
        my = _TERM_YEARS_RE.search(q)
        if my:
            term_years = int(my.group(1))
    model_year = None
    mm = _MODEL_YEAR_Q_RE.search(q)
    if mm:
        model_year = int(mm.group(1))
        # "model-year" phrasing only; a bare year+vehicle mentions count too
    if model_year is None and re.search(r"\bvehicle\b|\bcar\b", q):
        mm = re.search(r"\b(20\d\d)\b", q)
        if mm:
            model_year = int(mm.group(1))
    refinance = bool(re.search(r"\brefinanc", q))
    return {
        "family": "loans",
        "loan_family": fam,
        "metric": metric,
        "term_months": term_months,
        "term_years": term_years,
        "model_year": model_year,
        "refinance": refinance,
        "member": "business" if re.search(r"\bbusiness\b", q) else "personal",
    }


def parse_question(question: str) -> dict | None:
    """Return the family's slots, or None when no family can be identified."""
    q = (question or "").lower().strip()
    if not q:
        return None
    slots = _parse_changes(q)
    if slots:
        return slots
    slots = _parse_facts(q)
    if slots:
        return slots
    if _CERT_RE.search(q) or _CERT_SPECIAL_RE.search(q):
        return _parse_certificate(q)
    slots = _parse_deposit(q)
    if slots:
        return slots
    slots = _parse_loan(q)
    if slots:
        return slots
    slots = _parse_cards(q)
    if slots:
        return slots
    return _parse_branch(q)


def _parse_certificate(q: str) -> dict | None:
    slots = {
        "family": "certificate",
        "product": "certificate",
        "term_months": None,
        "special": None,
        "jumbo": None,
        "ira": False,
        "metric": "apy",
    }
    m = _MONTHS_RE.search(q)
    if not m:
        mw = _WORD_MONTH_RE.search(q)
        if mw:
            tok = mw.group(1)
            term = int(tok) if tok.isdigit() else WORD_NUMBERS[tok.lower()]
            slots["term_months"] = term
    else:
        slots["term_months"] = int(m.group(1))
    if _SPECIAL_RE.search(q):
        slots["special"] = True
    elif _REGULAR_RE.search(q):
        slots["special"] = False
    if _JUMBO_RE.search(q):
        slots["jumbo"] = True
        if " non-" in q:  # rare explicit negation
            slots["jumbo"] = False
    if _IRA_RE.search(q):
        slots["ira"] = True
    slots["member"] = "business" if re.search(r"\bbusiness\b", q) else "personal"
    if _DIV_RE.search(q):
        slots["metric"] = "dividend_rate"
    return slots


def _parse_deposit(q: str) -> dict | None:
    prods: list[str] = []
    for rx, canon in _DEPOSIT_PRODUCT_RES:
        if rx.search(q):
            prods.append(canon)
    if not prods and (_GENERIC_SAVINGS_RE.search(q) or re.search(r"\baccount rates?\b", q)):
        # generic "savings" → the primary savings account (Share Savings)
        prods = ["share_savings"]
    if not prods:
        return None
    prods = [c for p in prods for c in (_CHECKING_FAMILY if p == "checking_family" else [p])]

    metric = "dividend_rate" if _DIV_RE.search(q) else "apy"

    tier = None
    m = _TIER_RANGE_RE.search(q) or _TIER_RANGE_ALT_RE.search(q)
    if m:
        lo = float(m.group(1).replace(",", ""))
        hi = float(m.group(2).replace(",", "")) if m.group(2) else lo
        tier = (lo, hi)

    hypo = None
    mp = _PCT_HYPO_RE.search(q)
    if mp:
        hypo = float(mp.group(1))

    mode = "list_all"
    if _DO_ANY_RE.search(q) and hypo is not None:
        mode = "do_any"
    elif _HIGHEST_RE.search(q):
        mode = "highest"
    elif tier is not None:
        mode = "tier"

    return {
        "family": "deposit",
        "product": "deposit",
        "products": prods,
        "metric": metric,
        "mode": mode,
        "tier": tier,
        "hypo": hypo,
        "member": "business" if re.search(r"\bbusiness\b", q) else "personal",
    }
