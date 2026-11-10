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


# --------------------------------------------------------------------- loans
_LOAN_METRIC_WORD = {"apr": "APR", "rate": "rate"}


def _model_range_label(dims: dict) -> str:
    if dims.get("model_older"):
        return f"{int(dims['model_to'])} model-year and older"
    return f"{int(dims['model_from'])}-{int(dims['model_to']) % 100} model-year"


def loan_answer(claims: list[Claim], slots: dict, present_tense: bool = True) -> str:
    """Winners already trust-collapsed; group by tier key so rate+APY-like APR
    columns pair into one phrase per tier. Deterministic ordering."""
    word = _LOAN_METRIC_WORD.get(slots.get("metric", "rate"), "rate")
    fam = slots["loan_family"]
    by_tier: dict[tuple, dict] = {}
    for c in claims:
        key = tuple(sorted((k, v) for k, v in c.tier_dims.items() if k != "metric"))
        by_tier.setdefault(key, {})[c.metric] = c

    if fam == "mortgage":
        parts = []
        for key, metrics in by_tier.items():
            d = dict(key)
            bits = []
            if metrics.get("rate"):
                bits.append(f"{fmt_rate(metrics['rate'])} rate")
            if metrics.get("apr"):
                bits.append(f"{fmt_rate(metrics['apr'])} APR")
            label = f"{d['term_years']}-Year Fixed Conventional"
            if d.get("amount_tier"):
                label += f" {d['amount_tier']}"
            parts.append(f"{label}: " + " / ".join(bits))
        if not parts:
            return REFUSAL
        return "Currently, " + parts[0] + ("." if len(parts) == 1 else
                                            "; " + "; ".join(parts[1:]) + ".")

    parts = []
    for key, metrics in by_tier.items():
        d = dict(key)
        c = metrics.get("apr") or metrics.get("rate")
        if not c:
            continue
        qualifier = []
        if d.get("model_from") is not None or d.get("model_older"):
            qualifier.append(_model_range_label(d))
        if d.get("term_months"):
            qualifier.append(f"{int(d['term_months'])}-month")
        elif d.get("term_years"):
            qualifier.append(f"{int(d['term_years'])}-year")
        if d.get("amount_tier"):
            qualifier.append(str(d["amount_tier"]).replace("$", "$"))
        family_word = d.get("family_display") or d.get("family", "loan")
        if fam == "auto" and qualifier:
            q = " ".join(qualifier)
            parts.append(f"{c.tier_dims['family_display']} {word} on a {q} loan is "
                         f"{fmt_rate(c)}")
        else:
            q = " ".join(qualifier) if qualifier else ""
            parts.append(
                f"{family_word} {word}{(' for a ' + q + ' loan') if q else ''} is {fmt_rate(c)}"
            )
    if not parts:
        return REFUSAL
    return "Currently, the " + parts[0] + ("." if len(parts) == 1 else
                                            "; " + "; ".join(parts[1:]) + ".")


# --------------------------------------------------------------------- cards
def _apr_text(claim: Claim) -> str:
    """'12.50% – 19.50%' for ranges, '15.50%' for a single value."""
    high = claim.tier_dims.get("apr_high")
    low_s = f"{claim.value:.2f}%"
    if high is None:
        return low_s
    return f"{low_s} – {high:.2f}%"


_CARDS_ORDER = [
    "platinum_visa", "rewards_visa",
    "business_platinum_visa", "business_rewards_visa",
]


def cards_list(claims: list[Claim], present_tense: bool = True) -> str:
    """One phrase per card: standard APR first, then the intro APR line.

    R1 rails: only corpus values; the intro value is labelled as intro so the
    standard rate can never be confused with the promotional one.
    """
    by_card: dict[str, dict] = {}
    for c in claims:
        by_card.setdefault(c.tier_dims["card"], {})[c.tier_dims.get("rate_period")] = c
    parts = []
    for canon in _CARDS_ORDER:
        bits = by_card.get(canon)
        if not bits:
            continue
        std = bits.get(None)
        intro = bits.get("intro")
        if not std and not intro:
            continue
        c = std or intro
        name = c.tier_dims["card_display"]
        if std and intro:
            parts.append(
                f"{name}: {_apr_text(std)} standard APR "
                f"({_apr_text(intro)} intro APR on balance transfers only)"
            )
        elif std:
            parts.append(f"{name}: {_apr_text(std)} APR")
        else:
            parts.append(f"{name}: {_apr_text(intro)} intro APR")
    if not parts:
        return REFUSAL
    return "Currently: " + "; ".join(parts) + "."


def card_standard(claims: list[Claim], present_tense: bool = True) -> str:
    """'The standard purchase APR on the Platinum Visa is 12.50% – 19.50%;
    the 2.90% intro APR applies only to balance transfers in the first 90 days.'
    The intro caveat is corpus-stated (intro rows exist for this card)."""
    std = next((c for c in claims if c.tier_dims.get("rate_period") is None), None)
    intro = next((c for c in claims if c.tier_dims.get("rate_period") == "intro"), None)
    if std is None:
        return REFUSAL
    name = std.tier_dims["card_display"]
    text = f"The standard purchase APR on the {name} is {_apr_text(std)}."
    if intro is not None:
        text += (f" The {_apr_text(intro)} intro APR is separate: it applies "
                 "only to balance transfers.")
    return text


def refusal() -> tuple[str, None]:
    return REFUSAL, None
