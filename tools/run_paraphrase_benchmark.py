#!/usr/bin/env python3
"""S3.3 paraphrase self-benchmark (PLAN.md T3) — consistency under rewording.

Hand-rewords every public eval item into two semantics-preserving variants
(same product, metric, tier, member, as_of and ask-type; only syntax and
synonyms change), runs BOTH the originals and the variants through the
UNMODIFIED harness runner (run_eval.py --eval), and gates on the story DoD:

    >=90% of variants must land on the same claim as their original
    (same confident flag + identical numeric/time token multiset — R3:
    same question in different words gets the same answer).

Local-only by construction: the derived JSONL files are generated into
results/ (gitignored); the corpus and the organizers' eval file are read
but never copied into git. Judge-scored items (empty must_include, e.g.
dup-005) are excluded from the denominator — the local scorer cannot
grade them (harness/scoring.py: correctness = hits/must, 0/0 -> 0.0).

Usage:
    python3 tools/run_paraphrase_benchmark.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "paraphrase_benchmark"

# Hand-written rewordings: original id -> [variant 1, variant 2].
# Discipline: change the WORDS, never the ASK. Each variant must be answerable
# to the same claim: same product entity, same metric (rate vs APY vs APR),
# same tier/qualifier, same member segment, same as_of, same ask-type
# (current / as-of / count / list / refuse / link).
PARAPHRASES: dict[str, list[str]] = {
    # tier_disambiguation
    "dup-001": [
        "What APY does the 17-month special certificate pay?",
        "How much do you earn on Dupaco's 17-month special certificate?",
    ],
    "dup-011": [
        "What are today's mortgage rates?",
        "What are your current mortgage rates?",
    ],
    "dup-016": [
        "What APR would I get on a 60-month auto loan for a 2025 car?",
        "Rate on a 2025 vehicle with a 60-month auto loan?",
    ],
    "dup-045": [
        "What dividend rate do I get on Share Savings if my balance is between $10,000 and $24,999?",
        "Share Savings pays what dividend rate on a $10,000 to $24,999 balance?",
    ],
    "dup-035": [
        "What's the standard purchase rate on the Platinum Visa?",
        "How high is the purchase APR on Dupaco's Platinum Visa card?",
    ],
    "dup-028": [
        "What's the APR on a 36 month personal loan?",
        "Rate for a personal loan with a 36-month term?",
    ],
    "dup-046": [
        "What's the top APY on Share Savings, and at what balance?",
        "Which Share Savings balance tier earns the most?",
    ],
    "dup-049": [
        "Does any savings tier at Dupaco pay 0.35% APY?",
        "Is there a savings balance tier earning 0.35% APY?",
    ],
    # stale_trap
    "dup-009": [
        "What's the interest rate on a 30-year home loan?",
        "Can you tell me the rate for a 30-year mortgage loan?",
    ],
    "dup-087": [
        "How many times has Forbes recognized Dupaco?",
        "Has Forbes given Dupaco any Best-in-State recognition?",
    ],
    "dup-008": [
        "Where can I find Dupaco's certificate rates on the website?",
        "Which page lists your CD rates?",
    ],
    "dup-052": [
        "What are the current checking account rates?",
        "What interest rate does your checking pay right now?",
    ],
    "dup-017": [
        "What APR applies to an 84-month auto loan for a 2024 car?",
        "84-month auto loan on a 2024 model - what's the APR?",
    ],
    "dup-080": [
        "Where on your site is the branch and ATM locator?",
        "What link takes me to the branch and ATM locator?",
    ],
    "dup-082": [
        "What's the link to become a Dupaco member online?",
        "Where do I sign up to join Dupaco on the web?",
    ],
    # list_completeness
    "dup-034": [
        "Which credit cards does Dupaco offer, and what are the APRs?",
        "List your credit card options with their rates.",
    ],
    "dup-040": [
        "What are the APRs on your credit cards?",
        "Could you list the rates for each credit card?",
    ],
    "dup-094": [
        "Does Dupaco support adding debit and credit cards to Apple Pay, Google Pay or Samsung Pay?",
        "Can I use my Dupaco cards in mobile wallets like Apple Pay?",
    ],
    # entity_attribution
    "dup-054": [
        "What's Dupaco's ABA routing number?",
        "I need Dupaco's routing number for a direct deposit.",
    ],
    "dup-050": [
        "What rate does Bright Savings pay?",
        "How much interest does the Bright Savings account earn?",
    ],
    "dup-055": [
        "What was that routing number again?",
        "Could you repeat Dupaco's routing number?",
    ],
    "dup-101": [
        "Do you have loan options for students heading to college?",
        "I'm starting university soon - are there student loan options with flexible repayment?",
    ],
    # branch_info
    "dup-064": [
        "What are Dupaco's typical lobby hours?",
        "When are your lobbies open?",
    ],
    "dup-066": [
        "When is the drive-up open?",
        "What are Dupaco's drive-thru hours?",
    ],
    "dup-068": [
        "Where is the Galena branch located?",
        "Can you tell me the street address of the Galena branch?",
    ],
    "dup-065": [
        "What are the lobby hours at Dupaco?",
        "When are your lobbies open?",
    ],
    "dup-076": [
        "Which branches can Hy-Vee members use for full-service banking?",
        "Where should Hy-Vee branch members go to do their full-service banking?",
    ],
    "dup-104": [
        "Are lobby hours the same at every Dupaco branch?",
        "Do all branches open and close at the same time?",
    ],
    # conflict_resolution
    "dup-073": [
        "How many branch locations does Dupaco have?",
        "What's the total number of Dupaco branches?",
    ],
    "dup-081": [
        "What do I need to be eligible for Dupaco membership?",
        "Can anyone join Dupaco, or do you have to live in the charter area?",
    ],
    # temporal_as_of
    "dup-075": [
        "Is the Hy-Vee branch open as of October 2026?",
        "Did the Hy-Vee location stay open in October 2026?",
    ],
    "dup-074": [
        "What's the closure date for the Hy-Vee branch?",
        "When is the Hy-Vee branch closing?",
    ],
    "dup-006": [
        "What rate was the 10-month fixed jumbo special certificate paying in May 2026?",
        "As of the end of May 2026, what was the APY on the 10-month jumbo special?",
    ],
    "dup-088": [
        "How many Dupaco employees took Volunteer Time Off last year?",
        "How many employees volunteered through the VTO program last year?",
    ],
    # current_value
    "dup-031": [
        "Can you explain what the Home$tart program is?",
        "What does Dupaco's Home$tart program offer?",
    ],
    "dup-060": [
        "How do I change my contact information at Dupaco?",
        "What's the process to update my address and phone number with Dupaco?",
    ],
    # should_refuse
    "dup-145": [
        "What's the rate on a 7/1 ARM?",
        "Do you publish rates for 7/1 adjustable-rate mortgages?",
    ],
    "dup-147": [
        "What rate do you offer on construction loans?",
        "How much interest do you charge for a construction loan?",
    ],
    "dup-102": [
        "What are the lobby hours for a branch on Mullan Avenue?",
        "Is there a Dupaco branch on Mullan Avenue, and what time is it open?",
    ],
    # NOTE: dup-005 ("certificate of accounts" enumeration) is judge-scored
    # (empty must_include) and structurally unscorable locally — excluded
    # from this benchmark's denominator, same as in the public eval.
}

_TOKEN_RE = re.compile(r"\d[\d,.:]*")


def _tokens(text: str) -> list[str]:
    """All numeric/time tokens, commas stripped ('4.10' == '4.1' stays distinct
    only if rendered differently — our formatter is deterministic (R3), so
    same claim -> identical rendering -> identical token multiset)."""
    return sorted(t.replace(",", "") for t in _TOKEN_RE.findall(text or ""))


def _write_jsonl(path: Path, items: list[dict]) -> None:
    with path.open("w") as f:
        for it in items:
            f.write(json.dumps(it) + "\n")


def _run_harness(eval_file: Path, out_dir: Path) -> None:
    cmd = [
        sys.executable, "harness/run_eval.py",
        "--submission", "answers",
        "--eval", str(eval_file.relative_to(ROOT)),
        "--out", str(out_dir.relative_to(ROOT)),
    ]
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout[-2000:])
        print(res.stderr[-2000:])
        raise SystemExit(f"harness run failed for {eval_file.name}")


def main() -> int:
    originals_all = [json.loads(line) for line in (ROOT / "eval" / "public_eval.jsonl").open()]
    gradable = [
        it for it in originals_all
        if it.get("must_include") or it.get("category") == "should_refuse"
    ]
    excluded = [it["id"] for it in originals_all if it not in gradable]

    variants = []
    for it in gradable:
        for k, q in enumerate(PARAPHRASES[it["id"]], start=1):
            v = dict(it)
            v["id"] = f"{it['id']}-p{k}"
            v["group"] = it["id"]
            v["question"] = q
            variants.append(v)

    OUT.mkdir(parents=True, exist_ok=True)
    orig_file = OUT / "originals.jsonl"
    var_file = OUT / "variants.jsonl"
    _write_jsonl(orig_file, gradable)
    _write_jsonl(var_file, variants)

    print(f"originals: {len(gradable)} gradable items (excluded judge-only: {excluded})")
    print(f"variants:  {len(variants)} hand-reworded paraphrases")
    _run_harness(orig_file, OUT / "originals")
    _run_harness(var_file, OUT / "variants")

    def load_results(p: Path) -> dict:
        out = {}
        with (p / "per_question.jsonl").open() as f:
            for line in f:
                it = json.loads(line)
                out[it["id"]] = it
        return out

    orig_res = load_results(OUT / "originals")
    var_res = load_results(OUT / "variants")

    passed, failed = 0, []
    for v in variants:
        o = orig_res[v["group"]]
        r = var_res[v["id"]]
        same_claim = (
            _tokens(o["answer"]["text"]) == _tokens(r["answer"]["text"])
            and o["answer"]["confident"] == r["answer"]["confident"]
        )
        if same_claim:
            passed += 1
        else:
            failed.append({
                "id": v["id"],
                "question": v["question"],
                "orig_text": o["answer"]["text"][:150],
                "var_text": r["answer"]["text"][:150],
                "orig_conf": o["answer"]["confident"],
                "var_conf": r["answer"]["confident"],
                "correctness": r["correctness"],
            })

    total = len(variants)
    rate = passed / total if total else 0.0
    ok = rate >= 0.90
    summary = {
        "variants": total,
        "same_claim": passed,
        "rate": round(rate, 4),
        "gate": ">=0.90",
        "ok": ok,
        "excluded_judge_only": excluded,
        "failures": failed,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))

    print(f"\nsame-claim rate: {passed}/{total} = {rate:.1%} (gate >=90%) -> {'OK' if ok else 'FAIL'}")
    if failed:
        print("\nfailures:")
        for f in failed:
            print(f"  {f['id']}: {f['question'][:70]}")
            print(f"     orig: conf={f['orig_conf']} {f['orig_text'][:90]!r}")
            print(f"     var:  conf={f['var_conf']} {f['var_text'][:90]!r}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
