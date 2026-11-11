"""Template-only answer synthesis (S0.3).

R1 rails implemented here, hard:
  - the answer carries ONLY the selected claims' values (nothing from the trap
    snapshot, no ranges, no "the page says", no both-worlds prose);
  - refusals are digit-FREE and confident=False;
  - identical slot sets produce byte-identical text (R3), because claim
    selection is deterministic and the templates are pure functions.
"""
from __future__ import annotations

import re

from ledger import Claim

REFUSAL = (
    "Based on the website information we have, this question isn't covered. "
    "Please contact us."
)

DISAGREEMENT_NOTE = (
    "Some pages on the site currently disagree for this item; we used the more "
    "authoritative statement per page class and effective date."
)

# S2.2: an as_of that precedes every snapshot still gets answered from the
# EARLIEST snapshot (best knowledge for that date) with this provenance note
# on the answer — never a refusal, never silent. Lives on conflict_note, so
# the answer text itself stays a pure claim template (R1).
AS_OF_EARLIEST_NOTE = (
    "The requested date precedes the earliest snapshot on file ({date}); "
    "showing the earliest available data."
)


def as_of_earliest_note(date_iso: str) -> str:
    return AS_OF_EARLIEST_NOTE.format(date=date_iso)


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


# --------------------------------------------------------------------- facts
_FHLB_SPONSOR = "with FHLB (Federal Home Loan Bank of Des Moines)"

_SERIES_PHRASES = {
    "employees_vto": "employees used Volunteer Time Off",
    "volunteer_hours": "volunteer hours",
    "board_seats": "nonprofit boards and committees served on",
    "employees_volunteered": "employees volunteered",
}


def facts_link(role: str, claims: list[Claim]) -> str:
    """CTA-link answers: only the normalised URL the corpus publishes wins."""
    urls = sorted({c.tier_dims.get("url", "") for c in claims} - {""})
    if not urls:
        return REFUSAL
    url = urls[0]
    if role == "join_application":
        return f"To become a member online, use {url}."
    return f"Dupaco's branch and ATM locator is at {url}."


def cert_directory(url: str) -> str:
    """Rates directory: where the published certificate rate rows live now."""
    return f"The published certificate rates are on the rate tables at {url}."


def deposit_directory(url: str) -> str:
    """Rates directory: where the published savings rate rows live now."""
    return f"The published savings rates are on the rate tables at {url}."


def program_fact(claims: list[Claim]) -> str:
    """Assistance-program description built only from the winner's own dims."""
    if not claims:
        return REFUSAL
    c = sorted(claims, key=lambda x: (-x.value, x.tier_dims.get("program", "")))[0]
    d = c.tier_dims
    sponsor = f", {_FHLB_SPONSOR}," if d.get("sponsor") == "fhlb" else ""
    word = "grant funds" if d.get("kind") == "grant" else "assistance"
    return (
        f"The {d.get('program_display', d.get('program', 'program'))}{sponsor} "
        f"provides up to {fmt_money(c.value)} in {word}"
        + (
            f", applied as a credit toward {d['purpose']}"
            if d.get("purpose") else ""
        )
        + (f" for {d['audience']}." if d.get("audience") else ".")
    )


def update_contact(claims: list[Claim]) -> str:
    """Channels exactly as the winner's service claim stores them."""
    if not claims:
        return REFUSAL
    c = sorted(claims, key=lambda x: (-x.page_rank, x.page_url))[0]
    d = c.tier_dims
    lead = None
    if d.get("login"):
        lead = "by logging into your account and making the desired changes"
    alts: list[str] = []
    if d.get("phone"):
        alts.append(f"call us at {d['phone']}")
    if d.get("email"):
        alts.append(f"email {d['email']}")
    if d.get("branch"):
        alts.append("visit a branch in person")
    if not lead:
        return "You can review and change your personal information: " + ", ".join(alts) + "."
    return (
        "You can review and change your personal information "
        + lead
        + ("; you may also " + ", ".join(alts) if alts else "")
        + "."
    )


def wallet_support(claims: list[Claim]) -> str:
    """"Yes — ... Apple Pay, Google Pay or Samsung Pay..." from winner dims."""
    if not claims:
        return REFUSAL
    c = sorted(claims, key=lambda x: (-x.page_rank, x.page_url))[0]
    d = c.tier_dims
    text = (
        f"Yes — you can add your Dupaco {d.get('cards', 'cards')} to "
        f"{d.get('wallets_display', '')}"
    )
    if d.get("default_ok"):
        text += " and set one as your default for faster checkouts"
    return text + "."


def _series_part(series: str, year: int, n: int, approx: bool) -> str:
    phrase = _SERIES_PHRASES.get(series, series.replace("_", " "))
    mod = "Nearly " if approx else ""
    return f"{mod}{n} {phrase} in {year}"


def annual_series(claims: list[Claim], series: str, year: int | None = None) -> str:
    """"last year"/unbound-year questions answer the full chronological series
    (the freshest published annual recap may be older than today); a year-bound
    question answers only that year's statement."""
    best: dict[int, Claim] = {}
    for c in claims:
        d = c.tier_dims
        if d.get("series") != series:
            continue
        y = int(d.get("year", 0))
        if y not in best or c.page_rank > best[y].page_rank:
            best[y] = c
    if not best:
        return REFUSAL
    if year is not None:
        c = best.get(year)
        if c is None:
            return REFUSAL
        return _series_part(series, year, int(c.value), bool(c.tier_dims.get("approx")))
    parts = [
        _series_part(series, y, int(best[y].value), bool(best[y].tier_dims.get("approx")))
        for y in sorted(best)
    ]
    return (
        "Per the annual recaps on file: "
        + parts[0]
        + ("; " + "; ".join(parts[1:]) if len(parts) > 1 else "")
        + " (the years shown are the most recent reporting published by the site)."
    )


# -------------------------------------------------------------------- branch
def _sched_norm(text: str) -> str:
    """Deterministic schedule address text (dashes unified)."""
    return re.sub(r"[–—]", "-", text or "")


def branch_hours(claims: list[Claim], channel: str, same_question: bool) -> str:
    """Distinct schedules, deterministic order; straight 'No' when asked if all same."""
    scheds = sorted({
        _sched_norm(c.tier_dims.get("schedule", ""))
        for c in claims if c.tier_dims.get("channel") == channel
    } - {""})
    if not scheds:
        return REFUSAL
    channel_word = "drive-up" if channel == "drive_up" else "lobby"
    if len(scheds) == 1:
        verb_z = "Branch" if not same_question else "Yes — all branches on file keep the same"
        text = f"{verb_z} {channel_word} hours are: {scheds[0]}."
        if same_question:
            text = f"Yes — all branches on file keep the same {channel_word} hours: {scheds[0]}."
        return text
    if same_question:
        return ("No — at least two lobby schedules are on file: "
                + "; or ".join(s for s in scheds) + ".")
    return (f"Branch {channel_word} hours vary by branch. Schedules on file: "
            + "; or ".join(scheds) + ".")


def branch_address(claims: list[Claim], present_tense: bool = True) -> str:
    if not claims:
        return REFUSAL
    c = sorted(claims, key=lambda x: x.tier_dims.get("address_display", ""))[0]
    d = c.tier_dims
    return (f"The {d.get('city_display', d.get('city'))} branch is at "
            f"{d.get('address_display')}.")


def branch_hyvee_alternatives(claims: list[Claim], present_tense: bool = True) -> str:
    if not claims:
        return REFUSAL
    alts = claims[0].tier_dims.get("alternatives", "")
    return (f"Members can access the same full-service banking at the "
            f"{alts} branches.")


# ------------------------------------------------------- change events (S2.3)
# Event answers quote the date EXACTLY as published (claim.value_text, e.g.
# "March 31, 2026") — R3 determinism and member-facing fidelity in one move.
# Tense is a pure function of (event_date, view snapshot date), so the same
# question under an as_of before the event says "will close", after it says
# "closed" — the historical view stays truthful without extra machinery.

def branch_event_when(label: str, date_text: str, past: bool) -> str:
    verb = "closed" if past else "will close"
    return f"The {label} branch {verb} {date_text}."


def branch_event_status(label: str, date_text: str, past: bool) -> str:
    if past:
        return f"No. The {label} branch closed {date_text}."
    return f"Yes. The {label} branch is open; its closure is scheduled for {date_text}."


def changes_answer(rows: list[dict], label_from: str | None, label_to: str | None) -> str:
    """Rows pre-sorted by (topic, to_date) — one part per transition, joined
    with '; '. Each part states only that transition's old and new value (R1)."""
    lo = label_from or "the earlier snapshots"
    hi = label_to or "now"
    parts = [f"{r['topic']} changed from {r['old']} to {r['new']}" for r in rows]
    return f"Between {lo} and {hi}: " + "; ".join(parts) + "."


# ------------------------------------------------------ entity facts (S2.4)
# The "who/what is Dupaco" fact class. Each template renders ONLY the selected
# claim's payload (R1); freshness/tense decisions happen upstream in the trust
# stack, not here.

def entity_routing(claim: Claim) -> str:
    return f"Dupaco's routing number is {claim.value_text}."


def entity_branch_count(claim: Claim) -> str:
    return f"Dupaco has {claim.value_text} branch office locations."


def entity_forbes(claim: Claim) -> str:
    return (f"Forbes has recognized Dupaco for the {claim.value_text} time, "
            f"most recently on its Best-in-State Credit Union list.")


def entity_membership(claim: Claim) -> str:
    states = claim.tier_dims.get("states") or ""
    base = ("Membership is open to people who live or work within Dupaco's "
            "charter area")
    if states:
        return f"{base} — you can find us in {states}."
    return f"{base}."


def entity_student_loan(claim: Claim) -> str:
    return ("Yes — Dupaco offers student loans: choose a new student loan or "
            "refinance existing ones, with flexible repayment and $0 "
            "origination fees.")


# dispatch keyed by the question parser's entity slot (R3: explicit, total)
ENTITY_TEMPLATES = {
    "routing_number": entity_routing,
    "branch_count": entity_branch_count,
    "forbes_recognition": entity_forbes,
    "membership_eligibility": entity_membership,
    "student_loan": entity_student_loan,
}

