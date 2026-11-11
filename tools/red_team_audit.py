#!/usr/bin/env python3
"""S6.4 red-team audit vs the assignment rules (PLAN.md T6).

Mechanically verifies every rule that CAN be checked from the repository:
no live calls, contract fidelity (nothing renamed), organizer kit untouched,
no corpus data in git, stdlib-only grading path, latency/ingest budgets.

Corpus-dependent checks (timing on the real data, determinism spot-check)
run only when snapshots/ is present; on CI (no corpus) they are skipped.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANSWERS = ROOT / "answers"

_NETWORK_RE = re.compile(
    r"\b(import\s+(requests|urllib(\.|$)|http(\.|$)|socket|ssl|ftplib|smtplib|telnetlib|"
    r"httpx|aiohttp|websockets)|from\s+(requests|urllib|http|socket|ssl|ftplib|smtplib|"
    r"telnetlib|httpx|aiohttp|websockets)\b|urlopen\()"
)

failures: list[str] = []
passed: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (passed if ok else failures).append(f"{name}{(' — ' + detail) if detail else ''}")
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""))


# 1. No live calls: no network-capable imports anywhere in the submission
net_hits = []
for py in sorted(ANSWERS.glob("*.py")):
    for i, line in enumerate(py.read_text().splitlines(), 1):
        if _NETWORK_RE.search(line):
            net_hits.append(f"{py.name}:{i}")
check("no live calls (no network imports in answers/)", not net_hits, str(net_hits[:4]))

# 2. Contract fidelity: imports the harness contract like starter does; build()
#    exposes ingest/answer/conflicts; nothing renamed
sol_text = (ANSWERS / "solution.py").read_text()
check(
    "contract imported from harness (not copied)",
    re.search(r"(from contract import|import contract)", sol_text) is not None
    and not (ANSWERS / "contract.py").exists(),
)
sys.path.insert(0, str(ANSWERS))
sys.path.insert(0, str(ROOT / "harness"))
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("sol_audit", ANSWERS / "solution.py")
sol = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sol)
ks = sol.build()
check(
    "build() -> ingest/answer/conflicts (contract shape)",
    all(callable(getattr(ks, m, None)) for m in ("ingest", "answer", "conflicts")),
)

# 3. Organizer kit untouched (never modified in any commit)
KIT = ["harness/", "eval/", "starter/", "README.md", "Knowledge-Hackathon-Assignment.pdf"]
res = subprocess.run(
    ["git", "log", "--oneline", "--name-only", "--diff-filter=M", "--", *KIT],
    cwd=ROOT, capture_output=True, text=True,
)
check("harness/eval/starter/README/PDF never modified", res.stdout.strip() == "")

# 4. No kit data redistribution: nothing corpus-shaped is tracked in git
tracked = subprocess.run(
    ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True
).stdout.splitlines()
BAD_PREFIX = ("snapshots/", "snapshots_zip/", "results/", "results_ci/")
bad = [
    f for f in tracked
    if f.startswith(BAD_PREFIX) or f.endswith(".pdf") or f.endswith(".zip")
]
check("no snapshots/zips/eval-outputs/PDFs tracked in git", not bad, str(bad[:4]))

# 5. Grading path is stdlib-only: requirements.txt declares no packages
req_lines = [
    line.strip() for line in (ANSWERS / "requirements.txt").read_text().splitlines()
    if line.strip() and not line.strip().startswith("#")
]
check("requirements.txt pins zero packages (pure stdlib)", not req_lines, str(req_lines))

# 6. NOTES.md present in the submission and states no keys are needed
notes = (ANSWERS / "NOTES.md").read_text().lower()
check("NOTES.md exists and says no API keys", "no api keys" in notes)

# 7. Corpus-dependent budgets (skipped on CI where the corpus is absent)
if (ROOT / "snapshots").is_dir():
    sys.path.insert(0, str(ROOT / "harness"))
    from run_eval import load_snapshots  # noqa: E402

    t0 = __import__("time").time()
    snaps = load_snapshots(ROOT / "snapshots")
    for s in snaps:
        ks.ingest(s)
    ingest_s = __import__("time").time() - t0
    check("ingest <= 30 min (5 snapshots)", ingest_s < 1800, f"{ingest_s:.1f}s")

    t0 = __import__("time").time()
    ks.answer("What is the APY on Dupaco's 17-month special certificate?")
    answer_s = __import__("time").time() - t0
    check("answer <= 60s", answer_s < 60, f"{answer_s * 1000:.0f}ms")

    a1 = ks.answer("How many branches does Dupaco have?")
    a2 = ks.answer("How many branches does Dupaco have?")
    check("repeat answers identical (R3)", a1.text == a2.text and a1.confident == a2.confident)
else:
    print("SKIP corpus-dependent checks (no snapshots/ — CI mode)")

print()
print(f"audit: {len(passed)} passed, {len(failures)} failed")
if failures:
    for f in failures:
        print("  FAILED:", f)
sys.exit(1 if failures else 0)
