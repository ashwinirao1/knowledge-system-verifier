"""BM25 fallback (S4.1): last-resort answers for questions the grammar router
cannot parse at all.

Policy (R1/R2/R3/R4):
- Fires ONLY on a total grammar miss (parse_question -> None). A question the
  grammar UNDERSTOOD but the site does not answer keeps its informed refusal —
  the fallback must never override it (that is what protects should_refuse).
- Answers quote ONE published sentence from the as_of VIEW snapshot (the same
  trust view every other path uses: snapshot-filtered, never cross-snapshot).
- A sentence qualifies only if it contains a published number ($x or x.xx%)
  and every KEY query term (idf-weighted; ask-verbs like "charge"/"pay"
  describe the ask, not the fact, and are excluded). Quote units are
  sentences AND table lines (fee schedules are line-shaped), matched on the
  unit's OWN text only — section-heading context was tried and REVERTED: it
  let blog headings ("building a home...") pull construction-loan refusals
  into confident wrong quotes (the kill-criterion fired in development).
  Otherwise the honest answer is the digit-free refusal. Precision-first:
  a wrong confident quote is worse than an "I don't know" (accuracy rules
  zero out old/wrong values anyway).
- Pure stdlib BM25 (k1=1.5, b=0.75, BM25+ idf so every term contributes
  positively). Deterministic by construction: fixed tokenizer, fixed
  stopwords, stable tie-breaks (score desc, then section order).
- Index cost is paid at INGEST (tokenize + postings per page, incremental);
  answer time is a postings walk plus one idf lookup per query term (R2: no
  finalize pass, no first-question warm-up spike).
"""
from __future__ import annotations

import math
import re

_K1 = 1.5
_B = 0.75

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
# a "published number": a rate/percentage or a dollar amount
_NUMBER_RE = re.compile(r"\d+\.\d+\s*%|\d+\s*%|\$\s*[\d,]+(?:\.\d+)?")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$", re.M)

# Small fixed stopword list (deterministic; embedded — no downloads)
_STOP = frozenset("""
a an and are as at be but by can could do does for from had has have how i
in is it its may me my no not of on or our out should so some such than that
the their them then there these they this to was we were what when where which
who will with would you your yours about after all also any because been being
both did each else ever every get gets give given got if into just like made
make many more most much need needs now off only other over own same say says
see set take than thats thing things think those through too under up use used
using want wants way well went yes yet offer offers
""".split())

# Query-side ASK verbs: they describe the asking, not the fact ("what do you
# CHARGE for a stop payment?"). Rare in corpus prose, so idf wrongly marks
# them KEY — excluded from the key-term requirement, still scored.
_ASK_VERBS = frozenset(
    "charge charges charging cost costs pay pays paying withdraw withdrawing "
    "borrow borrowing lend lend".split()
)


def _fold(tok: str) -> str:
    """Deterministic light plural fold (no stemming library): 'fees'->'fee',
    'members'->'member'. Applied identically to queries and index."""
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def tokenize(text: str) -> list[str]:
    """Deterministic content tokens: lowercase [a-z0-9]+, stopwords and
    single characters dropped, plurals folded."""
    return [
        _fold(t) for t in _TOKEN_RE.findall((text or "").lower())
        if len(t) > 1 and t not in _STOP
    ]


class _Section:
    __slots__ = ("snap_id", "url", "title", "heading", "text", "tokens", "tf")

    def __init__(self, snap_id, url, title, heading, text):
        self.snap_id = snap_id
        self.url = url
        self.title = title
        self.heading = heading
        self.text = text
        self.tokens = tokenize(text)
        self.tf: dict[str, int] = {}
        for t in self.tokens:
            self.tf[t] = self.tf.get(t, 0) + 1


class FallbackIndex:
    """Section-level BM25 over cleaned page text, per snapshot."""

    def __init__(self) -> None:
        self._sections: list[_Section] = []
        self._df: dict[str, int] = {}   # term -> sections containing it (global)
        self._df_view: dict[str, dict[str, int]] = {}  # term -> snap_id -> df
        self._view_n: dict[str, int] = {}  # snap_id -> section count
        self._avgdl = 0.0
        self._postings: dict[str, list[tuple[int, int]]] = {}  # term -> [(sec_idx, tf)]

    # ---------------------------------------------------------------- ingest
    def add_page(self, snap_id: str, url: str, title: str, cleaned_text: str) -> None:
        """Heading-split one cleaned page into sections and index them.
        Cheap (tokenize + dict updates); called once per page at ingest."""
        text = cleaned_text or ""
        if not text.strip():
            return
        headings = list(_HEADING_RE.finditer(text))
        chunks: list[tuple[str, str]] = []
        if not headings:
            chunks.append(("", text.strip()[:1200]))
        else:
            pre = text[: headings[0].start()].strip()
            if len(pre) > 80:
                chunks.append(("", pre[:1200]))
            for i, h in enumerate(headings):
                start = h.end()
                end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
                body = text[start:end].strip()
                if body:
                    chunks.append((h.group(1).strip(), body[:2000]))
        for heading, body in chunks:
            idx = len(self._sections)
            sec = _Section(snap_id, url, title, heading, body)
            self._sections.append(sec)
            dl = len(sec.tokens)
            self._avgdl = (
                (self._avgdl * idx + dl) / (idx + 1) if self._avgdl or idx else dl
            )
            self._view_n[snap_id] = self._view_n.get(snap_id, 0) + 1
            for term, tf in sec.tf.items():
                self._df[term] = self._df.get(term, 0) + 1
                per_view = self._df_view.setdefault(term, {})
                per_view[snap_id] = per_view.get(snap_id, 0) + 1
                self._postings.setdefault(term, []).append((idx, tf))

    # ---------------------------------------------------------------- search
    def _idf(self, term: str, snap_id: str) -> float:
        """idf within the VIEW snapshot — the fallback's statistics belong to
        the same trust view every other path answers from, so a term that
        only exists in other snapshots can never shape this view's ranking."""
        n = self._view_n.get(snap_id, 0)
        df = self._df_view.get(term, {}).get(snap_id, 0)
        return math.log((n - df + 0.5) / (df + 0.5) + 1.0)

    def _score_section(self, sec: _Section, q_terms: list[str]) -> float:
        dl = len(sec.tokens)
        # cap the length normalization at 4x average: table sections are long
        # but value-dense — plain BM25 buries them below thin blog sections
        dl_eff = min(dl, 4.0 * (self._avgdl or 1.0))
        norm = _K1 * (1.0 - _B + _B * (dl_eff / (self._avgdl or 1.0)))
        score = 0.0
        for t in q_terms:
            tf = sec.tf.get(t, 0)
            if tf:
                score += self._idf(t, sec.snap_id) * tf * (_K1 + 1.0) / (tf + norm)
        return score

    def _best_sentence(self, sec: _Section, q_terms: list[str]) -> str | None:
        """Best quote unit (sentence OR table line — fee schedules are
        line-shaped) that contains a published number and every KEY query
        term (idf >= 0.5 * max idf, ask-verbs excluded). Wins by idf-overlap,
        then SHORTER unit, then earlier position — all deterministic; the
        length filter keeps whole-table blobs out (R1)."""
        idfs = {t: self._idf(t, sec.snap_id) for t in q_terms}
        # the max is over terms the VIEW actually mentions: an ABSENT term
        # (df=0) gets the highest idf and would otherwise raise the key
        # threshold until nothing qualifies
        present = {t: i for t, i in idfs.items() if self._df_view.get(t, {}).get(sec.snap_id, 0) > 0}
        if not present:
            return None
        max_idf = max(present.values())
        key_terms = [
            t for t, i in present.items()
            if i >= 0.5 * max_idf and t not in _ASK_VERBS
        ]
        if not key_terms:
            return None
        units: list[str] = []
        for sent in _SENT_SPLIT_RE.split(sec.text):
            units.append(sent)
        for line in sec.text.splitlines():
            units.append(line)
        best, best_key = None, None
        for pos, unit in enumerate(units):
            if len(unit) > 280:
                continue  # whole-table blobs are not quotes (R1: extra numbers)
            if not _NUMBER_RE.search(unit):
                continue  # the quoted value must sit in the quote itself
            low = unit.lower()
            if not all(t in low for t in key_terms):
                continue
            score = sum(idfs[t] for t in q_terms if t in low)
            unit_key = (-score, len(unit), pos)
            if best_key is None or unit_key < best_key:
                best, best_key = " ".join(unit.split()), unit_key
        return best

    def best(self, snap_id: str, question: str) -> tuple[str, str, str] | None:
        """Best qualifying answer for one question within one snapshot view:
        (sentence, page_url, quote). None means "honestly refuse"."""
        q_terms = tokenize(question)
        if len(q_terms) < 2:
            return None  # too ambiguous to quote responsibly
        q_terms = list(dict.fromkeys(q_terms))  # stable dedupe, first-seen order
        # VETO: if the question names something the view never mentions
        # ("Titanium Amethyst card", "dirigible loan"), a quote would attribute
        # SOME OTHER product's numbers to it — refuse instead (R1).
        for t in q_terms:
            if self._df_view.get(t, {}).get(snap_id, 0) == 0:
                return None
        best_by_idx: dict[int, float] = {}
        for t in q_terms:
            for idx, _tf in self._postings.get(t, ()):  # postings walk
                sec = self._sections[idx]
                if sec.snap_id != snap_id:
                    continue
                s = self._score_section(sec, q_terms)
                if s > best_by_idx.get(idx, -1.0):
                    best_by_idx[idx] = s
        if not best_by_idx:
            return None
        scored = sorted(best_by_idx.items(), key=lambda p: (-p[1], p[0]))
        for idx, _score in scored[:16]:  # deterministic; quote rule filters
            sec = self._sections[idx]
            sent = self._best_sentence(sec, q_terms)
            if sent:
                return sent, sec.url, sent
        return None
