"""S3.4 router determinism tests (PLAN.md T3).

Invariant: the same paraphrase group NEVER splits across answer routes with
different numeric output. Two layers:

  Layer 1 (here, CI-safe — pure parser, no corpus): every member of a
  paraphrase group routes to the same (family, mode) and agrees on the
  load-bearing slots. The router is a pure function of the question string,
  so this runs anywhere.

  Layer 2 (local corpus — tools/run_paraphrase_benchmark.py): the answers
  themselves must be claim-identical (token multiset for numeric claims,
  byte-identical text for digit-free claims). When the S4.1 BM25 fallback
  lands, that runner additionally records which path answered (rule vs
  fallback) per group — a path split is only acceptable when the numeric
  output is identical, which Layer 2 already enforces.
"""
import json
import sys
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_ROOT = _TESTS.parent.parent
sys.path.insert(0, str(_TESTS.parent))
sys.path.insert(0, str(_TESTS))

import question as Q  # noqa: E402

_spec = spec_from_file_location(
    "paraphrase_benchmark", _ROOT / "tools" / "run_paraphrase_benchmark.py"
)
BENCH = module_from_spec(_spec)
_spec.loader.exec_module(BENCH)

# slots whose disagreement between group members would change the answer's
# numbers or claim identity (everything else is paraphrase noise)
_LOAD_BEARING = (
    "term_months", "term_years", "model_year", "special", "jumbo", "ira",
    "member", "metric", "entity", "tier", "tier_low", "tier_high",
    "link_role", "link_family", "product", "series", "purpose",
    "city", "branch_subject", "channel", "program", "year",
)


def _route(q: str) -> tuple:
    s = Q.parse_question(q)
    if s is None:
        return ("None", None)
    return (s.get("family"), s.get("mode") or s.get("entity"))


def _norm_slot(key: str, val, fam: str):
    """Loans publish ONE APR column — a 'rate' vs 'apr' ask is the same claim
    (the loan synth renders the table's own metric either way; proven by the
    benchmark's token-identity). Deposits keep rate/apy strictly distinct."""
    if key == "metric" and fam == "loans" and val in ("rate", "apr"):
        return "apr"
    return val


def _groups() -> dict[str, list[str]]:
    """group id -> [original question, *reworded variants]."""
    out: dict[str, list[str]] = {}
    with (_ROOT / "eval" / "public_eval.jsonl").open() as f:
        for line in f:
            it = json.loads(line)
            out[it["id"]] = [it["question"], *BENCH.PARAPHRASES.get(it["id"], [])]
    return out


class TestParseIsIdempotent(unittest.TestCase):
    """The router must be a pure function: no hidden state, no randomness."""

    BATTERY = [
        "What is the APY on a 12-month CD?",
        "What are the business savings rates?",
        "When does the Hy-Vee branch close?",
        "What changed between May and September?",
        "Who is eligible to become a Dupaco member?",
        "What is the highest Share Savings APY?",
        "Do any Dupaco savings tiers pay 0.35% APY?",
        "What's the link to become a Dupaco member online?",
    ]

    def test_same_question_same_slots(self):
        for q in self.BATTERY:
            self.assertEqual(Q.parse_question(q), Q.parse_question(q), q)

    def test_interleaved_parsing_changes_nothing(self):
        # parse A, B, A — the second A must equal the first (no context leak)
        a = self.BATTERY[0]
        before = Q.parse_question(a)
        for other in self.BATTERY[1:]:
            Q.parse_question(other)
        self.assertEqual(Q.parse_question(a), before)

    def test_route_tuple_stable(self):
        for q in self.BATTERY:
            self.assertEqual(_route(q), _route(q), q)


class TestGroupsNeverSplitRoute(unittest.TestCase):
    """Layer 1 of the S3.4 invariant: no paraphrase group may route its
    members to different answer paths. A split here is how a reworded
    question ends up answered by a different mechanism (and, post-S4.1,
    silently by the BM25 fallback) with different numbers."""

    def test_every_group_routes_consistently(self):
        bad = {}
        for gid, members in _groups().items():
            routes = {_route(q) for q in members}
            if len(routes) > 1:
                bad[gid] = sorted(str(r) for r in routes)
        self.assertEqual(bad, {}, "groups splitting across routes")

    def test_group_members_agree_on_load_bearing_slots(self):
        bad = {}
        for gid, members in _groups().items():
            parsed = [Q.parse_question(q) or {} for q in members]
            shared = set(parsed[0])
            for s in parsed[1:]:
                shared &= set(s)
            fam = _route(members[0])[0]
            for key in _LOAD_BEARING:
                if key not in shared:
                    continue
                vals = {json.dumps(_norm_slot(key, s[key], fam), sort_keys=True)
                        for s in parsed}
                if len(vals) > 1:
                    bad[f"{gid}:{key}"] = sorted(vals)
        self.assertEqual(bad, {}, "load-bearing slot disagreements")

    def test_all_39_groups_have_variants(self):
        # the benchmark covers every gradable public item (dup-005 excluded
        # as judge-only) — a group losing its variants would silently shrink
        # the determinism guarantee
        groups = _groups()
        covered = {g for g, ms in groups.items() if len(ms) > 1}
        self.assertEqual(len(covered), 39)


if __name__ == "__main__":
    unittest.main()
