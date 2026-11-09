"""
answers/solution.py — S0.1 stub (tracer bullet prep).

The contract shape is FINAL from day one (per harness/contract.py — nothing renamed).
Internals are deliberately minimal; PLAN.md S0.2/S0.3 (clean -> classify -> claim
ledger -> trust stack -> template answers) will replace them incrementally.

The stub already honours the hard rails (AGENTS.md §3):
- R1: honest refusal, digit-free text, confident=False
- R2: no network, no model calls; answers are instant
- R3: fully deterministic — repeated questions give identical answers
- R4: stdlib only, offline, no keys
"""
import sys
from pathlib import Path
from typing import Optional

_REPO = next(
    d for d in Path(__file__).resolve().parents
    if (d / "harness" / "contract.py").exists()
)
sys.path.insert(0, str(_REPO / "harness"))

from contract import Answer, Snapshot  # noqa: E402

REFUSAL = (
    "Based on the website information we have, this question isn't covered. "
    "Please contact us."
)


class CurrentTruth:
    """Reconciliation engine over a temporal claims ledger (stub for now)."""

    def __init__(self) -> None:
        # S0.1: we retain nothing yet; the ledger arrives with S0.2.
        self._snapshots_ingested = 0

    # ------------------------------------------------------------------ contract
    def ingest(self, snapshot: Snapshot) -> None:
        """Called once per snapshot, oldest first. (Ledger build arrives in S0.2.)"""
        self._snapshots_ingested += 1

    def answer(self, question: str, as_of: Optional[str] = None) -> Answer:
        """Stub: we currently hold no claims, so every question is refused honestly."""
        return Answer(
            text=REFUSAL,
            sources=[],
            confident=False,
            conflict_note=None,
        )

    def conflicts(self) -> list:
        """Stub: no claims yet, so no contradictions to report."""
        return []


def build():
    return CurrentTruth()
