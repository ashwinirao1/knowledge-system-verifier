"""Template-only answer synthesis (S0.3).

R1 rails implemented here, hard:
  - the answer carries ONLY the selected claims' values (nothing from the trap
    snapshot, no ranges, no "the page says", no both-worlds prose);
  - refusals are digit-FREE and confident=False;
  - identical slot sets produce byte-identical text (R3), because claim
    selection is deterministic and the templates are pure functions.
"""
from ledger import Claim

REFUSAL = (
    "Based on the website information we have, this question isn't covered. "
    "Please contact us."
)


def fmt_money(v: float | None) -> str:
    if v is None:
        return ""
    if float(v) == int(v):
        return f"${int(v):,}"
    return f"${v:,.2f}"


def fmt_rate(claim: Claim) -> str:
    """Canonical rate text: page writes 4.10 -> say 4.10% (two decimals)."""
    return f"{claim.value:.2f}%"


def label_term(term: int) -> str:
    return f"{term}-Month"


def cert_label(claim: Claim) -> str:
    """Label from claims dims — matches the marketing sheet's product name."""
    d = claim.tier_dims
    base = label_term(d["term_months"])
    if d.get("ira_type"):
        pre = {"roth": "Roth", "traditional": "Traditional"}[d["ira_type"]]
        base = f"{pre} {base}"
    base += " Fixed Jumbo Special" if d.get("jumbo") else (
        " Fixed Certificate Special" if d.get("special") else " Certificate"
    )
    return base


def cert_answer(claims: list[Claim], present_tense: bool = True) -> str:
    """Claims are pre-selected winners, ordered by (jumbo, term) → deterministic.

    one part per canonical key, joined with '; ' — a single claim never invents
    extra tiers; every claim states its minimum as published.
    """
    parts = []
    for c in claims:
        payable = fmt_rate(c)
        minimum = fmt_money(c.min_earn)
        verb = "pays" if present_tense else "paid"
        parts.append(f"the {cert_label(c)} {verb} {payable} APY ({minimum} minimum)")
    if not parts:
        return REFUSAL
    return parts[0][0].upper() + parts[0][1:] + ("." if len(parts) == 1 else "; " + "; ".join(parts[1:]) + ".")


def refusal() -> tuple[str, None]:
    return REFUSAL, None
