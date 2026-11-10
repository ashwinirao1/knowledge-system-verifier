"""Question parser (S0.3 v0 + S1.1): rule grammar → product/metric/tier slots.

Families:  certificate  → 17-month special / jumbo / IRA term certs
           deposit      → Share Savings, savings variants, money markets,
                          checking (personal + business), with balance tiers

Questions neither family can slot return `None` → the answer path declines
honestly instead of guessing (R1).
"""
from __future__ import annotations

import re

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
_CERT_RE = re.compile(r"\b(certificates?|certs?)\b", re.I)
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
_HIGHEST_RE = re.compile(r"\b(highest|best|max(?:imum)?|tops?\s+out)\b", re.I)
_PCT_HYPO_RE = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*%", re.I)
_TIER_RANGE_RE = re.compile(
    r"balance[s]?\s+(?:between|of|from|over|above)\s+\$?"
    r"([\d,]+(?:\.\d+)?)\s*(?:(?:and|to|-|–)\s*\$?([\d,]+(?:\.\d+)?))?",
    re.I,
)
_TIER_RANGE_ALT_RE = re.compile(r"\$([\d,]+(?:\.\d+)?)\s*(?:-|–|to)\s*\$([\d,]+(?:\.\d+)?)", re.I)


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
    if _CERT_RE.search(q):
        return _parse_certificate(q)
    slots = _parse_deposit(q)
    if slots:
        return slots
    slots = _parse_loan(q)
    if slots:
        return slots
    return _parse_cards(q)


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
