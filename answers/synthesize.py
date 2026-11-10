"""Template-only answer synthesis (S0.3).

R1 rails implemented here, hard:
  - the answer carries ONLY the selected claims' values (nothing from the trap
    snapshot, no ranges, no "the page says", no both-worlds prose);
  - refusals are digit-FREE and confident=False;
  - identical slot sets produce byte-identical text (R3), because claim
    selection is deterministic and the templates are pure functions.
"""
from __future__ import annotations

from ledger import Claim

REFUSAL = (
    "Based on the website information we have, this question isn't covered. "
    "Please contact us."
)

DISAGREEMENT_NOTE = (
    "Some pages on the site currently disagree for this item; we used the more "
    "authoritative statement per page class and effective date."
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
        part = f"the {cert_label(c)} {verb} {payable} APY"
        if minimum:
            part += f" ({minimum} minimum)"
        parts.append(part)
    if not parts:
        return REFUSAL
    return parts[0][0].upper() + parts[0][1:] + ("." if len(parts) == 1 else "; " + "; ".join(parts[1:]) + ".")


# ------------------------------------------------------------------ deposits
def _money_fmt(v: float) -> str:
    return f"${v:,.2f}" if v % 1 else f"${v:,.0f}"


def tier_display(dims: dict) -> str:
    lo, hi = dims.get("tier_low"), dims.get("tier_high")
    if lo is None and hi is None:
        return ""
    if hi is None:
        return f"{_money_fmt(lo)} and up"
    return f"{_money_fmt(lo)} – {_money_fmt(hi)}"


def _deposit_metric_word(metric: str) -> str:
    return "dividend rate" if metric == "dividend_rate" else "APY"


def deposit_answer(claims: list[Claim], metric: str, present_tense: bool = True) -> str:
    """One part per tier, ascending; a single-claim product reads as a sentence."""
    verb = "pays" if present_tense else "paid"
    word = _deposit_metric_word(metric)
    parts = []
    for c in sorted(claims, key=lambda c: (c.tier_dims.get("tier_low") or 0.0)):
        t = tier_display(c.tier_dims)
        rate = f"a {fmt_rate(c)} {word}" if word == "dividend rate" else f"{fmt_rate(c)} {word}"
        if t:
            parts.append(f"{c.tier_dims['product_display']} {verb} {rate} for balances of {t}")
        else:
            parts.append(f"{c.tier_dims['product_display']} {verb} {rate}")
    if not parts:
        return REFUSAL
    return parts[0][0].upper() + parts[0][1:] + ("." if len(parts) == 1 else "; " + "; ".join(parts[1:]) + ".")


def deposit_highest(claim: Claim, metric: str, present_tense: bool = True) -> str:
    word = _deposit_metric_word(metric)
    t = tier_display(claim.tier_dims)
    phrase = f" for balances of {t}" if t else ""
    if present_tense:
        return (f"The highest {claim.tier_dims['product_display']} {word} is "
                f"{fmt_rate(claim)}{phrase}.")
    return (f"The highest {claim.tier_dims['product_display']} {word} was "
            f"{fmt_rate(claim)}{phrase}.")


def deposit_do_any_yes(claims: list[Claim], metric: str, present_tense: bool = True) -> str:
    """Hypothesis form that checks out: 'Yes — Product pays V% APY for ...'"""
    verb = "pays" if present_tense else "paid"
    parts = []
    for c in sorted(claims, key=lambda c: (c.tier_dims.get("product"), c.tier_dims.get("tier_low") or 0.0)):
        t = tier_display(c.tier_dims)
        parts.append(f"{c.tier_dims['product_display']} {verb} {fmt_rate(c)} "
                     f"{_deposit_metric_word(metric)}" + (f" for balances of {t}" if t else ""))
    if not parts:
        return REFUSAL
    return "Yes — " + "; ".join(parts) + "."


def deposit_do_any_no(top: Claim, metric: str, present_tense: bool = True) -> str:
    """Negative hypothesis: never repeat the queried value; state the family top."""
    word = _deposit_metric_word(metric)
    t = tier_display(top.tier_dims)
    phrase = f", for balances of {t}" if t else ""
    return (f"No. The highest {top.tier_dims['product_display']} {word} is "
            f"{fmt_rate(top)}{phrase}.")


def refusal() -> tuple[str, None]:
    return REFUSAL, None
