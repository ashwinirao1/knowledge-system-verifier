"""Question parser (S0.3 v0): rule grammar → product/metric/tier slots.

Scope note (tracer slice): this version only claims the certificate family.
Questions it cannot fully slot (no family, no term) return `None` → the answer
path declines honestly instead of guessing (R1).
"""
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
_MONTHS_IN_QUESTION_RE = re.compile(r"as of|in\s+(January|February|March|April|May|June|July|August|September|October|November|December)", re.I)


def parse_question(question: str) -> dict | None:
    """Return cert-family slots, or None when the family cannot be identified."""
    q = (question or "").lower()
    if not _CERT_RE.search(q):
        return None
    slots = {
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
