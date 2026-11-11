#!/usr/bin/env python3
"""S0.6 data-leak guard: the credit-union corpus must NEVER enter git.

Checks every file git currently sees (staged + tracked + untracked-but-not-ignored,
so it works pre-commit as well as in CI):

  1. Path rules — nothing under snapshots/, snapshots_zip/ (outside harness/),
     results*/ , .venv/, no top-level zips, no snapshot manifests.
  2. Content rules — no credit-union page text outside the allowed kit/docs files:
     URL markers, `fetched_at` JSON, and "Rates are effective as of" markers are
     red flags anywhere the real pages could hide.

Exit 0 = boundary intact. Exit 1 = leak (lists every offending file).
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# paths that may legitimately contain credit-union URLs / kit content:
ALLOWED_CONTENT_PREFIXES = ("harness/", "eval/", "starter/", "tools/archived/")
ALLOWED_CONTENT_FILES = {
    "README.md", "SETUP.md", "PLAN.md", "AGENTS.md",
    "tools/data_leak_guard.py",  # this file quotes the markers it detects
    # answers/tests/test_unit_table_parser.py quotes the "Rates are effective
    # as of MM/DD/YYYY" DETECTION PATTERN with fully synthetic dates/lables —
    # the unit test for the date-marker rule must say the phrase verbatim.
    "answers/tests/test_unit_table_parser.py",
    # answers/tests/test_component_conflicts.py: fixtures build synthetic
    # rate sheets whose table-level effective-date statement is part of the
    # RULE UNDER TEST (freshest-date wins); all dates/URLs are fake
    # (example.org, 2026 synthetic dates) — no corpus text.
    "answers/tests/test_component_conflicts.py",
    # answers/tests/test_unit_deposits.py and test_component_deposit_answers.py:
    # synthetic tier tables (Share Savings / checking fixtures) whose
    # table-level effective-date statement is part of the parse rules under
    # test; all dates/URLs fake (example.org) — no corpus text.
    "answers/tests/test_unit_deposits.py",
    "answers/tests/test_component_deposit_answers.py",
    # S1.2 loans fixtures: synthetic loan sheets (auto model-year tiers /
    # mortgage labels / personal terms) whose table-level effective-date
    # statement is part of the parse rules under test; all numbers, dates and
    # URLs are synthetic (example.org) — no corpus text.
    "answers/tests/test_unit_loans.py",
    "answers/tests/test_component_loan_answers.py",
    # S1.3 cards fixtures: synthetic card tables (Platinum/Rewards Visa, APR
    # ranges + intro flag) whose table-level effective-date statement is part
    # of the parse rules under test; all synthetic (example.org) — no corpus text.
    "answers/tests/test_unit_cards.py",
    "answers/tests/test_component_card_answers.py",
    # S1.5 facts fixtures: the published hostname IS the rule under test —
    # join/locator/site-link claims gate on the literal `join.dupaco.com`
    # host and `dupaco.com/contact` locator target, so priors must quote the
    # host pattern. Fixtures are synthetic sentences; no corpus page text.
    "answers/tests/test_unit_facts.py",
    "answers/tests/test_component_facts_answers.py",
    # S2.3 changes fixtures: synthetic certificate rate sheets across two
    # snapshots whose table-level effective-date statement (MM/DD/YYYY form)
    # is part of the transition rule under test; all dates/rates/URLs are
    # synthetic (example.org) — no corpus page text.
    "answers/tests/test_component_answer_path.py",
}
# path patterns that must never appear in git at all (outside harness/):
FORBIDDEN_PATH_RE = re.compile(
    r"^(?:"
    r"snapshots(/.*)?"                       # unpacked corpus (top level)
    r"|snapshots_zip(/.*)?"                  # corpus zips (top level)
    r"|results(/.*)?"                        # eval outputs quoting page text
    r"|\.venv(/.*)?"
    r"|[^/]*\.zip"                           # any loose zip
    r"|[^/]*\.pdf"                           # organizer PDF stays local
    r"|[^/]*manifest\.json"                  # snapshot manifests live only under harness/
    r"|[^/]*\.db|[^/]*\.sqlite3?|[^/]*\.sqlite"  # ledger DBs may carry page text
    r")$",
    re.I,
)
CONTENT_MARKERS = (
    re.compile(r"https?://(?:www\.)?dupaco\.com", re.I),
    re.compile(r'"fetched_at"\s*:'),
    re.compile(r"Rates are effective as of \d{2}/\d{2}/\d{4}", re.I),
)


def _tracked_and_uncollowed_files():
    """Files git sees now: tracked + staged + untracked-not-ignored (ignores honored)."""
    out = subprocess.run(
        [shutil.which("git"), "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO, capture_output=True, text=True, check=True,
    )
    return [line for line in out.stdout.splitlines() if line.strip()]


def main() -> int:
    files = _tracked_and_uncollowed_files()
    violations = []

    for path in files:
        p = path.replace("\\", "/").lower()

        # 1. path rules (harness/selftest snapshots are the ONLY snapshots we keep)
        if FORBIDDEN_PATH_RE.match(p) and not p.startswith("harness/"):
            violations.append(f"PATH violation: {path}")
            continue

        # 2. content rules on text-ish files outside allowed locations
        allowed = (
            any(p.startswith(pref) for pref in ALLOWED_CONTENT_PREFIXES)
            or p in {f.lower() for f in ALLOWED_CONTENT_FILES}
            or p.startswith("answers/tests/baseline_selftest.json")  # scorer report subset only
        )
        if allowed or path.endswith((".png", ".jpg", ".webp", ".zip")):
            continue
        try:
            text = (REPO / path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for marker in CONTENT_MARKERS:
            hit = marker.search(text)
            if hit:
                line_no = text[: hit.start()].count("\n") + 1
                violations.append(
                    f"CONTENT violation: {path}:{line_no} matched {marker.pattern!r}"
                )

    if violations:
        print(f"DATA-LEAK GUARD FAILED ({len(violations)}):", file=sys.stderr)
        for v in violations:
            print("  " + v, file=sys.stderr)
        print("\nRule: the credit-union corpus stays local (gitignored);", file=sys.stderr)
        print("remove the files / content or fix .gitignore before committing.", file=sys.stderr)
        return 1

    print(f"leak guard OK: {len(files)} file(s) scanned, boundary intact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
