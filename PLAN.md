# plan.md — Delivery Plan: "Dupaco Current-Truth Assistant"

**Project:** Credit-union knowledge-system hackathon (see `Knowledge-Hackathon-Assignment.pdf`)
**Repo:** `/Users/ashwinirao/Documents/git/knowledge-system-verifier` — the participant kit lives at the repo root (`eval/`, `harness/`, `snapshots_zip/`, `snapshots/`, `starter/`); submission code will live in `answers/` (any folder except `starter/`)
**Status:** DRAFT → IN PROGRESS (v0.1 · 2026-11-09)
**Owners:** PL = Ashwini · Builder = ... · Reviewer = ...
**Agent ruleset:** `AGENTS.md` (repo root) — applies to every contributor and agent working here

---

## 1. Mission (one paragraph)

Build a system that, given five dated snapshots of the same credit-union website, answers member
questions like a careful human expert: with the **current** value, the **right tier**, a **source**,
and an honest decline when the site doesn't say. Architecturally we are not building a chatbot —
we are building a **reconciliation engine over a temporal claims ledger** whose input is a website
instead of a settlement file.

## 2. Objective function & non-negotiables

Scored by the provided harness (`harness/scoring.py`, same scorer used for grading):

```
final = 0.55·accuracy + 0.15·accuracy·consistency + 0.15·accuracy·speed + 0.15·conflicts
```

Every story below must trace to one of these hard requirements:

| # | Requirement | Why (from the scorer) |
|---|---|---|
| R1 | **Trap immunity** — emit only the selected value(s), never ranges/history | One `must_not_include` value zeroes the question (27/40 public items have traps) |
| R2 | **Speed** — p95 answer latency ≪ 2 s; no call > 60 s | Speed pillar 1.0 only ≤2 s; >60 s = zeroed question |
| R3 | **Numeric determinism** — paraphrases and repeats return identical numbers | Consistency = numeric-gist equality (public groups are singletons; hidden set has real pairs) |
| R4 | **Offline safety** — grading path needs no network, no API key | Graded in a clean Python 3.11 env; online dependency = possible total failure |
| R5 | **Conflict precision** — only real same-key contradictions | Conflicts = F1 vs gold + 0.3·resolution; flooding destroys precision |

**Rules we obey verbatim (PDF §8):** answer only from the provided snapshots (no live website
calls) · every `answer` call ≤ 60 s · ingest ≤ 30 min · any language model or library allowed, paid
APIs must be declared in `NOTES.md` (we plan to need none) · do not redistribute the snapshot data
(repo carries code + notes only) · do not rename anything in the contract · never modify
`harness/` or `eval/` (changes there have no effect on grading).

## 3. Current state of the system (as of today)

**What exists:**

- The provided kit, at repo root: `snapshots_zip/` (five zips, **not yet unpacked** — the first eval
  run unpacks them automatically), `snapshots/README.md`, `eval/public_eval.jsonl` (40 practice
  questions), `harness/` scorer, `starter/solution.py` (~0.09 final score, by design).
- **S0.1 scaffold complete (2026-11-09):** `answers/` stub is live and contract-conformant
  (digit-free refusal path), integration/grace tests green, starter baseline measured (final 0.093),
  eval-gate baseline committed. Git repo has **no commits yet** — first push pending a remote.

**Analysis phase — DONE.** Key findings that drive the plan (verified in the data):

- Corpus: 637→705 pages/snapshot; 621 URLs present in all five, 722 unique.
- 97% of pages "changed" between early snapshots but mostly dynamic noise (captcha payloads,
  vehicle-inventory tables) → **page-level diffing is not a viable backbone** (Option H rejected).
- Trust signals exist in-site: per-table "Rates are effective as of MM/DD/YYYY" lines. E.g.
  `/personal/loans/home-loans` → 09/25/2026; `/homebuying-guidance` (stale mortgage trap) →
  04/22/2026; `/switch-and-earn` (stale auto trap) → 10/22/2024; calculators have no date at all.
  One page carries many tables with different dates (`/rates` hub: 10 distinct dates;
  `/personal/savings-account`: 4) → **effective dates must be captured at table level**.
- Within-snapshot contradictions are everywhere in the *latest* snapshot: auto 5.39% vs 5.34%;
  mortgage 7.13/7.27 vs 6.037/6.061/5.954; branch count 22 vs 24 → conflicts must be found **within
  and across** snapshots, grouped by canonical key (replicas deduped — e.g. the corporate footer
  is one claim, not 436).
- Question set facts: 9 categories; 27/40 items carry traps; all 21 groups are singletons →
  paraphrase robustness is unmeasurable from the public set (we will self-build a paraphrase
  benchmark, Story T3.3); 4 items have no `must_include` (3 `should_refuse` + 1 judge-only, so the
  hidden run very likely uses the optional `--judge`); 8 items carry source credit.
- Refusal calibration cases: unpublished products (7/1 ARM, construction loans), branches absent
  from the locator (Mullan Avenue — mentioned only in blog/PDF stories), and refusal answers must
  be **digit-free**.
- Known data hazards: 62 calculator pages full of numeric arrays (quarantine), `hubfs/` PDF
  conversions, boilerplate footer variants (600/650/700 employees), legacy links in old pages
  (`info.dupaco.com/*` → replaced by `join.dupaco.com`, `/personal/savings-account#rates`, `/contact`).

## 4. Tracer-bullet strategy

We build **thin vertical slices end-to-end, then fatten them**. The first "tracer bullet" is:

> unpack → clean → classify → store claims for **one fact family only** (certificate rates) →
> answer one tier question, one "as of" question, decline one unpublished product → run the public
> scorer end-to-end → print a real score above the starter's.

Every later increment repeats the same loop for a wider slice. **After every story we run the
public eval and append a row to the Eval Ledger (§7).** Nothing merges without a runnable system.

## 5. Deliverable roadmap

| ID | Deliverable | Scope (thin → fat) | Exit criteria (exit = DoD met) | Est |
|----|---|---|---|---|
| **T0** | **Tracer bullet** | Repo + contract scaffold; ingest (clean/classify/store); ONE rate family end-to-end; template answers; refusal stub; conflicts stub | Public eval runs cleanly through `answers/`; score > starter; latency p95 < 0.5 s | 2–3 d |
| **T1** | **Fact-base v1** | All structured families: deposit products incl. tiers, loan families, cards (personal+business), branch hours/addresses, canonical links, programs/eligibility | All 40 public questions produce an intended answer path (audit per item); est. accuracy ≥ 0.55* | 4–6 d |
| **T2** | **Temporal layer** | Table-level effective dates; `as_of` windowing incl. edge dates; change events for "what changed" questions | All `temporal_as_of` items pass incl. dup-006 (3.90% @ 2026-05-31); 3.90→4.00 detectable | 2–3 d |
| **T3** | **Question understanding** | Slot grammar + synonym/entity resolution (personal vs business); deterministic router; **self-built paraphrase benchmark (40 → ~80 reworded)** | Route agreement on paraphrase set ≥ 90%; no group splits | 3–4 d |
| **T4** | **Fallback + a11y of speed/consistency** | BM25 fallback through the *shared* resolver; answer caching; index warmed during ingest | Repeat-consistency 100%; route agreement maintained; p95 < 200 ms | 2–3 d |
| **T5** | **Conflicts productionized** | Tier-aware conflict generator w/ precision control (replica dedup, ranking, cap); hand-built local gold (≥15 entries) | `harness/selftest` gold passes; local-gold precision ≥ 0.8, resolution ok | 2–3 d |
| **T6** | **Submission hardening** | Pinned requirements; clean-3.11 venv install test; fresh-clone end-to-end; final `NOTES.md`; red-team vs PDF rules | Submission checklist (§10) fully green | 1–2 d |

*\* Score targets are honest engineering estimates, not promises; they exist so we can tell whether
an increment moved us. The Eval Ledger (§7) is the scoreboard of record.*

## 6. Stories & tasks

> Format per story: **Intent → Tasks → Done when**. Task status tracked as `[ ] [~] [x]`.
> Owner column left for assignment during standup.

### T0 — Tracer bullet

**S0.1 Repo & contract scaffold — DONE, except the GitHub push (no remote created yet)**
- Intent: a runnable, submittable skeleton exists from day one.
- Tasks
  - [x] Create `answers/` with `solution.py` implementing `build()` → object with `ingest/answer/conflicts` matching `harness/contract.py` (no renames); contract imported exactly like the starter does
  - [x] `requirements.txt` (intentionally empty — stdlib only, R4), `NOTES.md` stub
  - [x] `.gitignore`: snapshot zips & unpacked snapshots, `results*/`, caches, `.DS_Store`; no data redistribution
  - [x] Push this repo to GitHub — only after `.gitignore` excludes the data dirs (see `AGENTS.md` §2: no data redistribution) — done 2026-11-10; CI verified green (see S0.6)
  - [x] Baseline run: `python harness/run_eval.py --submission starter --eval eval/public_eval.jsonl` → recorded in §7 (final 0.093)
- Done when: `[x]` — `run_eval.py --submission answers` executes end-to-end on both the public corpus
  and the synthetic selftest; zero-snapshot grace verified by tests (7 OK, 100% coverage).

**S0.2 Ingest: clean → classify → store — DONE (2026-11-10)**
- Intent: the ledger exists and is populated from all five snapshots.
- Tasks
  - [x] Cleaning pass: strip nav/footer boilerplate, captcha blocks, image/recaptcha payloads (`answers/cleaning.py`)
  - [x] Page classifier: product page / rates hub / newsroom / blog / promo / calculator / PDF (URL-based v0; authority ranks fixed) (`answers/classify.py`)
  - [x] SQLite schema claims(...) with canonical key = (product, metric, tier_dims) (`answers/ledger.py`); in-memory SQLite, `check_same_thread=False` (harness answers on the eval pool thread — serialized, deterministic)
  - [x] Table parser v0: markdown tables → candidate claims; certificates family only (tracer slice) (`answers/tables.py`)
  - [x] Replica dedup by content hash (one claim per distinct fact, N replicas) — hash includes member segment so personal vs business pages never absorb each other; replica merges upgrade provenance to the highest-authority page
  - [x] Ingest driver: 5 snapshots oldest-first → **230 claims, 1.9–3.4 s total** (limit 1800 s)
- Done when: ✅ ledger contains all certificate claims from all 5 snapshots with provenance
  (verified: 10-month-fixed-jumbo history 3.90% → 3.90% → 4.00% present with effective dates 03/03/2026→06/02/2026→09/01/2026).

**S0.3 Answer: minimal (certificates family) — DONE (2026-11-10)**
- Tasks
  - [x] Question parser v0: product + metric + term/tier slots (rule grammar, word numbers too) (`answers/question.py`)
  - [x] `as_of` filter: last snapshot with `taken_on ≤ as_of`; month names clamp to month end (`answers/trust.py`)
  - [x] Trust stack v0: tier exact match → page-class authority → freshest effective date (`answers/trust.py::pick_winners`)
  - [x] Answer template from canonical dims; "The {term}-Month Fixed ... pays {apy} APY (${min} minimum)"; one Source + quote; `confident=True` (`answers/synthesize.py`)
  - [x] Refusal: no claim → `confident=False`, refusal phrase, **digit-free text**
- Done when: ✅ **dup-001 scores 1.0 with byte-exact template text**; **dup-006 scores 1.0**
  (as_of clamps to the 2026-05-19 snapshot: says 3.90%, never 4.00%, past tense "paid");
  **dup-145 refuses cleanly** (digit-free, confident=False). Public eval: 0.093 → 0.1508.

**S0.4 Conflicts stub — DONE (2026-11-10)**
- Intent: the conflicts report path exists from the first increment.
- Tasks
  - [x] Prose extractor (`answers/certificates.py::extract_prose_certificates`): sentence-form
    cert rates ("6-month certificate APY: 2.95%", "Summer special: 6-month certificate APY 2.95% …")
    so promo/trap pages enter the ledger; `special` token taken only from text between term and
    "certificate" so a leading "Summer special:" never forks the canonical key
  - [x] Generator v0 (`answers/conflicts.py`): same canonical key + ≥2 distinct values **in the
    latest snapshot view** → Conflict with winner + reason (freshest effective date, else
    page-class authority); R5 precision: replicas count once, tier differences are not conflicts
  - [x] `conflict_note` on answers: digit-free `DISAGREEMENT_NOTE` when the answered key holds
    >1 distinct value in the same view; answer text stays value-pure (R1)
  - [x] Validate against `harness/selftest/conflicts_gold.json` (c1: 6-month cert 2.95% vs 3.50%,
    correct 3.50%)
- Done when: ✅ selftest conflicts **F1 = 1.0, resolution_accuracy = 1.0**; selftest final 0.17 →
  **0.83** (t1/t1b/t2/t4 now 1.0; t3 "lost debit card fee" = fees family, out of certificates
  tracer scope, deferred to T1). Real-corpus conflicts: **0 — truthful**, because certificate
  rates exist only in tables there (prose-verified: zero prose rate lines in all 5 snapshots);
  conflicts machinery is exercised by the synthetic promo-trap fixture. Public eval unchanged:
  0.1508 (no regressions).

**S0.5 Playback review (tracer-bullet retro)**
- [ ] Demo: run scorer, show ledger contents, one conflict, one refusal
- [ ] Retro: extraction quality on the certificates family; update plan if schema bends
- Done when: Eval Ledger row for T0 filled; go/no-go for T1.

**S0.6 CI/CD quality gate (GitHub Actions) — every push is triaged by CI: tests by tier,
quality, security, data boundary — before any ledger row means anything.**
- Tasks
  - [x] `.github/workflows/ci.yml` — triggers: push / PR / dispatch; docs-only changes skip heavy jobs; tests on matrix (3.9 + 3.11); concurrency cancel-in-progress
  - [x] Test tiers as separate labeled steps by file pattern: `test_unit_*`, `test_component_*`, `test_integration_*` (missing pattern = harmless 0-test run until a tier exists)
  - [x] Integration = `run_eval.py` on `harness/selftest/` synthetic corpus + `--conflicts-gold` + `tools/eval_gate.py` vs committed baseline (`answers/tests/baseline_selftest.json`)
  - [x] Quality: ruff lint; coverage: `coverage.py` → `coverage.xml` (artifact for Sonar)
  - [x] SonarQube scan step, conditional on `SONAR_TOKEN` (no report published without it)
  - [x] Security (OWASP-aligned): gitleaks secret scan (full history), bandit 1.9.4 SAST, pip-audit vulnerable-dependency check
  - [x] Data-leak guard job: `tools/data_leak_guard.py` — paths + content markers; scans staged + tracked + untracked-not-ignored so it works pre-push too
  - [x] Committed config: `ruff.toml`, `.coveragerc`, `sonar-project.properties` (dev-only tooling — never in `answers/requirements.txt`)
- Done when: **DONE and verified (2026-11-10, run 42763791893 — all 6 jobs green on GitHub's
  hosted runners)**: leak-guard, ruff, tests × (3.9, 3.11) incl. selftest `run_eval` + eval gate,
  coverage + Sonar (publish skipped without `SONAR_TOKEN`), gitleaks/bandit/pip-audit.
  Root causes fixed along the way: (1) unanchored `.gitignore` pattern `snapshots/` silently
  excluded the synthetic `harness/selftest/snapshots/` corpus from git — anchored to root and
  committed the fixtures; (2) `ubuntu-latest` is rolling to Ubuntu 26.04 and setup-python
  manifests for 3.9 lag the new image — jobs pinned to `ubuntu-24.04` (literal; `runs-on`
  rejects the `env` context); (3) runner-bundled setuptools 79.0.1 has open CVEs (PYSEC-2026-3447,
  GHSA-xmj3-9gf7-h52w) and fails pip-audit's environment scan — tooling env upgraded pre-audit.

### T1 — Fact-base v1 (widen the slice)

**S1.1 Deposit products with tiers** (certificates, Share Savings, Money Market, checking,
business variants)
- [ ] Balance-tier parsers (e.g. $0,000–$24,999 → dims), dividend/normaliser (rate vs APY)
- [ ] Entity split: personal vs business product variants (**Business** 1st Rate vs personal 1st Rate)
- Done when: dup-045 (0.15%), dup-046 (0.20% + $25,000), dup-049 (top out 0.20%), dup-052 (2.50%) pass traps.

**S1.2 Loan families** (auto w/ model-year tiers & terms, personal, mortgage tiers incl. loan-amount
tiers, home-improvement)
- [ ] Term + model-year + loan-amount tier parser; effective-date capture from the *same table*
- Done when: dup-016/017 (5.39%/5.59%, trap 5.34 avoided), dup-009/011 (7.13/7.25, traps avoided), dup-028 (10.49%) pass.

**S1.3 Cards (personal + business)** incl. intro vs standard APR qualifiers
- [ ] Card entity + standard vs intro APR dims (intro duration e.g. 90 days)
- Done when: dup-034 (four cards), dup-035/dup-040 (standard 12.5%, not intro) pass.

**S1.4 Branch knowledge** (hours, addresses, closures)
- [ ] `/contact` locator parse: branch → {lobby, drive-up} hours, address; closure events from newsroom (Hy-Vee → closed 2026-03-31, replaced by Key West + Sycamore)
- [ ] "Varies by branch" aggregation answer pattern
- Done when: dup-064/065/066/068/074/075/076/104 pass; dup-102 (Mullan) refuses without hallucination.

**S1.5 Canonical links, programs, misc facts**
- [ ] Link extractor for current nav/CTA links (`join.dupaco.com`, `/contact`, `/personal/savings-account#rates`) with authority rules vs legacy links in old pages
- [ ] Program facts (Home$tart $15,000), support phone (800-373-7600), education/wallet lists — extracted as prose-fact claims
- Done when: dup-008/080/082, dup-031, dup-060, dup-094, dup-088 pass.

### T2 — Temporal layer

**S2.1 Effective dates at table granularity**
- [ ] Effective-date capture adjacent to each table (a page may carry several); date normalisation MM/DD/YYYY
- Done when: switch-and-earn's 10/22/2024 auto table loses to the 08/31/2026 rate page *without special-casing any URL*.

**S2.2 as_of edge handling**
- [ ] Dates between pulls (05-31 → snap 02), inside the 10-week gap → snap 03, before baseline → earliest+note, after latest → latest
- [ ] Robust input parsing (ISO required; month names tolerated)
- Done when: hidden-style variants behave predictably; unit tests for each edge.

**S2.3 Change events ("what changed")**
- [ ] Attribute ledger events when a key's value changes between snapshots (3.90% → 4.00% example)
- Done when: answerable "what changed between May and September" queries; conflicts can cite the transition.

### T3 — Question understanding

**S3.1 Slot grammar + synonym layer** (share certificate = CD; model-year phrasing; "current"/"right now")
**S3.2 Entity resolution** (personal vs business; Bright Savings vs Jump Start; Money Market vs Share Savings)
**S3.3 Paraphrase self-benchmark** — hand-reword the 40 public items into ~80 variants (selftest
`t1`/`t1b` style); harness runner to compare route + numeric outcome
- Done when: ≥90% route to the same claim; numeric output identical.
**S3.4 Router determinism test** — assert the same group never splits rule-path vs fallback for different numeric output.

### T4 — Fallback + speed/consistency hardening

**S4.1 BM25 fallback index** over cleaned sections, **filtered by as_of**, passed through shared trust stack
**S4.2 Deterministic caching & formatting** (canonical number formatting; memoise repeats)
**S4.3 Warm-up at end of ingest** (first question is not the slowest question)
- Done when: repeats/paraphrases identical; p95 < 200 ms locally.

### T5 — Conflicts productionized

**S5.1 Precision control**: replica/boilerplate-aware dedupe, tier-aware grouping (0.35% belongs to Money
Market, not Share Savings — not a conflict), ranking + capped list
**S5.2 Local gold**: hand-derived ~15 gold conflicts from known data (5.34/5.39, 6.037 vs 7.13, 3.90/4.00, 22 vs 24,
fourth vs fifth, legacy vs current links…) + tuning run
**S5.3 `harness/selftest` regression** in the eval loop
- Done when: local-gold precision ≥ 0.8 with resolution ≥ 0.8; selftest green.

### T6 — Submission hardening

**S6.1 Environment** — pin all requirements; test install+run in a fresh py3.11 venv; keep
dependencies lean/offline
**S6.2 NOTES.md final** (how "current" is decided; conflicts policy; keys needed: none)
**S6.3 Fresh-clone E2E** — clone → install → `run_eval.py --submission answers ...` runs clean
**S6.4 Red-team vs PDF rules** — audit: no live calls, ≤60 s/answer, ≤30 min ingest, no renames,
harness/eval untouched, **no snapshot data in repo**, deadline: repo URL + pinned commit shared
- Done when: §10 checklist fully green.

## 7. Eval Ledger (scoreboard of record)

| Increment | Date | Accuracy | Consistency | Speed | Conflicts | Final | Notes |
|---|---|---|---|---|---|---|---|
| starter | 2026-11-09 | 0.093 | 1.0 | 1.0 (p95 0.61s) | — | **0.093** | word-overlap is deterministic but ignores traps/tiers/as_of — sanity-checks the PDF's "~0.09" |
| answers stub (S0.1) | 2026-11-09 | 0.2 | 1.0 | 1.0 | 0.0 | **0.17** | `harness/selftest` synthetic only (not public); refusal path scores; this report = the eval-gate baseline |
| S0.2+S0.3 tracer (certs) | 2026-11-10 | 0.402 (weighted) | 1.0 | 1.0 (p50 0.0s) | — | **0.1508** | public eval: dup-001 ✅ byte-exact, dup-006 ✅, dup-145 ✅ + 2 more refusals; ingest 1.9–3.4 s for 5 snapshots (3266 pages) |
| S0.4 conflicts | 2026-11-10 | 0.8 (selftest qa) | 1.0 | 1.0 | **1.0** (F1 1.0, resolution 1.0) | **0.83 selftest** / **0.1508 public** | gold c1 matched w/ correct winner; 0 real-corpus conflicts is truthful (cert rates only in tables); 58 tests, coverage 88% |
| T1 | | | | | — | | |
| T2 | | | | | — | | |
| T3 | | | | | — | | |
| T4 | | | | | — | | |
| T5 | | | | | *(scored locally)* | | |

Note: conflicts are only scored when grading passes `--conflicts-gold`; locally we always run a
gold file (selftest + our hand-built one in S5.2). The public `--judge` LLM scoring exists in the
harness (organizer-side); assume hidden run uses it for free-text items.

## 8. Working agreements / DoD

**Story DoD:** task acceptance criteria met; public eval run appended to §7; no regressions on
previously-passing questions; unit tests for the changed extractor family.
**Release DoD:** §10 checklist green.
**Red flags (instant fix):** any answer text that can contain an unselected value, any digit in a
refusal, any non-deterministic answer path, any network/key dependency in the grading path, any
"data redistribution" risk in the repo.
**Cadence:** standup each increment; playback demo after each deliverable (§5) for observers.

## 9. Risks, kill criteria & decision log

| Risk | Likelihood | Mitigation / kill criterion |
|---|---|---|
| Rule extractors under-cover (messy PDFs/prose) | Medium | Audit at T1 exit: if < ~70% coverage of value-bearing pages → pull **D** (offline LLM extraction, cached, same claim schema) forward |
| Paraphrase routing misses (can't measure from public set) | Medium | T3.3 self-built benchmark; if BM25+synonyms <95% route agreement → add small **ONNX embeddings** in fallback only |
| Conflict F1 collapses on pseudo-conflicts | Medium | T5.1 precision control + local gold tuning before relying on the pillar |
| Ingest beyond 30 min with extras | Low | Time-box ingest; only leaner extraction paths may scale up |
| Grading env lacks a dependency | Low | S6.1 fresh-env test; avoid heavy/uncommon wheels (no torch-class deps) |
| Hidden set emphasises unmeasurable pillars (judge free-text) | Medium | Template answers read like careful human prose; no token-dumping |

**Decision log (already made, with rationale in the design discussions):**
1. Core = **claims ledger + trust resolution** (Option B) — the eval is a qualified-facts-over-time problem, not a search problem.
2. **Hybrid** (Option C): BM25 fallback through the shared resolver — coverage without losing determinism.
3. **Rejected for answer-time LLM (Option F)**: violates R1/R2/R3/R4 structurally (trap leakage, tail latency, nondeterminism, offline risk). Off-by-default formatter only, ever.
4. **Rejected diff-first (H)**: 97% churn is dynamic noise; blind to within-snapshot contradictions. Diff events kept as a *feature* (S2.3).
5. Graph (G) folded into schema design, not a graph store. D and E on the bench behind kill criteria.

## 10. Submission checklist (from PDF §7)

- [ ] GitHub repo pushed; organizers have read access
- [ ] `solution.py` with `build()` in the repo (folder ≠ `starter/`) — our `answers/`
- [ ] `requirements.txt` lists every package; clean Python 3.11 install verified
- [ ] `NOTES.md` explains: how current is decided; which API keys (none planned)
- [ ] `python harness/run_eval.py --submission answers --eval eval/public_eval.jsonl` runs clean from fresh clone
- [ ] Repo contains **no** kit data redistribution: no snapshots/zips, no eval outputs, and the
      assignment PDF stays local (organizer material; graders have their own copy)
- [ ] Repo URL + grading commit shared before the deadline
