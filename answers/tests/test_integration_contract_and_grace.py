"""S0.1: contract shape + graceful zero-snapshot behaviour (integration tier).

Grading may happen on a machine where the corpus vendor files were never unpacked
(e.g. a fresh clone without snapshots/). The submission must degrade gracefully:
every answer() is a clean, digit-free refusal and conflicts() returns nothing —
never a crash.
"""
import importlib.util
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUBMISSION_DIR = HERE.parent          # answers/
REFUSAL_RE = re.compile(
    r"\b(i (?:do not|don't|can't|cannot) (?:know|find|confirm)|not (?:sure|able to confirm)|"
    r"no (?:longer )?(?:available|offered)|isn't listed|is not listed|please (?:contact|call|visit)|"
    r"no information)\b",
    re.I,
)


def _load_solution():
    spec = importlib.util.spec_from_file_location(
        "solution_under_test", SUBMISSION_DIR / "solution.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeSnapshot:
    snapshot_id = "99_1970-01-01_fake"
    taken_on = "1970-01-01"
    pages = []


class TestContractShape(unittest.TestCase):
    def setUp(self):
        self.mod = _load_solution()
        self.ks = self.mod.build()

    def test_build_returns_object_with_three_methods(self):
        for m in ("ingest", "answer", "conflicts"):
            self.assertTrue(callable(getattr(self.ks, m, None)), f"missing method: {m}")

    def test_build_is_repeatable(self):
        ks2 = self.mod.build()
        self.assertIsNot(ks2, self.ks)

    def test_answer_satisfies_answer_shape(self):
        ans = self.ks.answer("What is the rate?", as_of=None)
        self.assertTrue(hasattr(ans, "text"))
        self.assertTrue(hasattr(ans, "sources"))
        self.assertTrue(hasattr(ans, "confident"))
        self.assertTrue(hasattr(ans, "conflict_note"))
        self.assertIsInstance(ans.sources, list)


class TestGracefulZeroSnapshots(unittest.TestCase):
    def setUp(self):
        self.ks = _load_solution().build()

    def test_refusal_without_ingest(self):
        ans = self.ks.answer("What is the 60-month auto loan rate?")
        self.assertFalse(ans.confident, "zero-snapshot answer must be a refusal")
        self.assertIsNone(re.search(r"\d", ans.text), "refusals must be digit-free")
        self.assertTrue(REFUSAL_RE.search(ans.text), "refusal phrase not recognized")

    def test_conflicts_empty_without_ingest(self):
        self.assertEqual(self.ks.conflicts(), [])

    def test_ingest_then_answer_still_safe(self):
        self.ks.ingest(_FakeSnapshot())
        ans = self.ks.answer("How much is a lost debit card?")
        self.assertFalse(ans.confident)
        self.assertIsNone(re.search(r"\d", ans.text))

    def test_deterministic_across_builds(self):
        a1 = self.ks.answer("any question")
        a2 = _load_solution().build().answer("any question")
        self.assertEqual(a1.text, a2.text)


if __name__ == "__main__":
    unittest.main()
