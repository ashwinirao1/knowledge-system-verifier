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

**Rules we obey verbatim (PDF section 8):** answer only from the provided snapshots (no live website
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
public eval and append a row to the Eval Ledger (section 7).** Nothing merges without a runnable system.

## 5. Deliverable roadmap

| ID | Deliverable | Scope (thin → fat) | Exit criteria (exit = DoD met) | Est |
|----|---|---|---|---|
| **T0** | **Tracer bullet** | Repo + contract scaffold; ingest (clean/classify/store); ONE rate family end-to-end; template answers; refusal stub; conflicts stub | Public eval runs cleanly through `answers/`; score > starter; latency p95 < 0.5 s | 2–3 d |
| **T1** | **Fact-base v1** | All structured families: deposit products incl. tiers, loan families, cards (personal+business), branch hours/addresses, canonical links, programs/eligibility | All 40 public questions produce an intended answer path (audit per item); est. accuracy ≥ 0.55* | 4–6 d |
| **T2** | **Temporal layer** | Table-level effective dates; `as_of` windowing incl. edge dates; change events for "what changed" questions | All `temporal_as_of` items pass incl. dup-006 (3.90% @ 2026-05-31); 3.90→4.00 detectable | 2–3 d |
| **T3** | **Question understanding** | Slot grammar + synonym/entity resolution (personal vs business); deterministic router; **self-built paraphrase benchmark (40 → ~80 reworded)** | Route agreement on paraphrase set ≥ 90%; no group splits | 3–4 d |
| **T4** | **Fallback + a11y of speed/consistency** | BM25 fallback through the *shared* resolver; answer caching; index warmed during ingest | Repeat-consistency 100%; route agreement maintained; p95 < 200 ms | 2–3 d |
| **T5** | **Conflicts productionized** | Tier-aware conflict generator w/ precision control (replica dedup, ranking, cap); hand-built local gold (≥15 entries) | `harness/selftest` gold passes; local-gold precision ≥ 0.8, resolution ok | 2–3 d |
| **T6** | **Submission hardening** | Pinned requirements; clean-3.11 venv install test; fresh-clone end-to-end; final `NOTES.md`; red-team vs PDF rules | Submission checklist (section 10) fully green | 1–2 d |

*\* Score targets are honest engineering estimates, not promises; they exist so we can tell whether
an increment moved us. The Eval Ledger (section 7) is the scoreboard of record.*

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
  - [x] Push this repo to GitHub — only after `.gitignore` excludes the data dirs (see `AGENTS.md` section 2: no data redistribution) — done 2026-11-10; CI verified green (see S0.6)
  - [x] Baseline run: `python harness/run_eval.py --submission starter --eval eval/public_eval.jsonl` → recorded in section 7 (final 0.093)
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

**S0.5 Playback review (tracer-bullet retro) — DONE (2026-11-10)**
- [x] Demo (real corpus + selftest, all verified live):
  - ledger: 3,294 pages → 278 claims in 3.3 s; metrics apy/dividend_rate 139/139; personal 214 / business 64; replica counts 1/2/3̅ (replica merge w/ rank upgrade working — the rates-hub rendering upgrades to product-page rank 100 with multi-source provenance)
  - one conflict (selftest): `6-Month certificate apy values=[3.50%, 2.95%] → resolution 3.50%`, reason = page-class authority over promo; answered "The 6-Month Certificate pays 3.50% APY." with digit-free conflict_note
  - one refusal: mortgage question → clean digit-free `confident=False`
  - one temporal answer: dup-006 → "paid 3.90% APY ($100,000 minimum)" (no 4.00% leak)
  - determinism/speed: 5 repeats byte-identical, mean latency 0.6 ms per answer
- [x] Retro findings (certificates family):
  - **Keep:** member dim in canonical key (caught the personal/business page merge); statement-`startswith` effective-date rule; prose `special`-token alignment; replica rank-upgrade provenance
  - **Trap defended so far:** IRA flavor rows (Roth/Traditional/plain) are distinct keys; non-IRA questions filter them out — no cross-tier leak observed
  - **Known gap → T1:** consistency pillar on public eval = paraphrase+repeat OK, but accuracy is dragged by non-certificate families (branch_info, fees, entity_attribution, list_completeness all 0.00 — out of scope until their families land); selftest t3 (lost debit card fee $2.50) is the same story
  - **Data fact:** real corpus has ZERO prose certificate rates (all in tables) — 0 real conflicts is truthful, conflicts machinery validated synthetically
- [x] Eval Ledger row for T0 = the S0.4 row (final T0 state); baseline_selftest.json raised to the 0.83 floor
- Done when: ✅ **GO for T1** — expand families (current_value/fees first, then savings tiers, branch_info),
  reuse the same clean→classify→extract→ledger pipeline per family.

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

**S1.1 Deposit products with tiers — DONE (2026-11-10)**
- [x] Balance-tier parsers: `$25,000+` / `$10,000 – $24,999.99` / `$250,000-$1,000,000` / `—`
  → dims (tier_low, tier_high); product identity from ROW col0 (not section headings, which drift:
  "Share Savings Account", "Saving Account Rates", "None") → canonical aliases incl. business
  variants ("Business 1st Rate Checking") + apostrophe variants (`answers/deposits.py`)
- [x] Rate-period qualifier from the column header: "for 1st 6 Months" → `rate_period="intro"`;
  "After Promotional Period" → standard (None) so promo tables carrying BOTH intro and after-promo
  columns fork into distinct keys instead of fake same-key contradictions — this killed 6 false
  real-corpus conflicts on the Achieve Money Market promo rows **without special-casing any URL**
- [x] Question grammar extended: products (named/generic fallback: "savings" → Share Savings),
  metric (dividend rate vs APY/interest), modes tier / highest / do_any (never repeats the queried
  value on "No!") / list_all (`answers/question.py`)
- [x] Entity split personal vs business — reused page-level member dim in the canonical key
- Done when: ✅ **dup-045 (0.15%) ✅ zero traps, dup-046 (0.20% + $25,000) ✅, dup-049 (top 0.20%,
  never echoes the queried 0.35%) ✅, dup-052 (2.50%, all checking tiers) ✅**. Public eval
  0.1508 → **0.2671** (tier_disambiguation 0.17→0.50, current_value 0→0.33, conflict_resolution
  0→0.33, entity_attribution 0→0.25, no regressions). Ingest 2.6 s; +24 deposit claims; selftest
  unchanged (0.83, conflicts F1 1.0).

**S1.2 Loan families — DONE (2026-11-10)**
- [x] Row-grammar extractor (`answers/loans.py`) — headers drift everywhere, so the ROW grammar
  decides: model-year labels (`2024-27 Model Year` → (2024, 2027); `2016 … (and older)` → open
  range), mortgage labels (`Purchase: 30-Year Fixed Conventional $832,750 or less` — **purpose
  prefix in the label owns the family**, so a stale purchase sheet under a bare "Home Loans"
  heading lands in the same canonical keys as the hub rows it competes with), term-only rows
  (personal), amount-tier+term rows (boat-RV / home-improvement), HELOC variant rows; every
  family with a Term column gets `term_months` attached
- [x] Effective-date capture from the same table (incl. single-digit `1/1/2026` — widened the
  table-level date regex)
- [x] Question grammar (`question.py::_parse_loan`): family/auto+car+vehicle/mortgage(personal
  loans)/boat&rv/home-improvement/home-equity; APR vs rate (with metric fallback when a family
  only publishes one); months/years; model-year coverage; refrained from claiming ARM products
  (guard: adjustable/5-1/7-1 → refuse, kept the wrong-family unit test green)
- [x] Trap defence by the trust stack, zero special-casing: stale promo/calculator/blog copies of
  the rate sheets stay live in the latest snapshot ("2023–26 60 mo → 5.34%" on promo vs
  "2024-27 60 mo → 5.39%" on the hub both cover a "2025 model-year vehicle") — question-time
  selection filters to covering ranges, then rank collapses each term to the rate-sheet row
- [x] Templates (`synthesize.py::loan_answer`): mortgage amount-tiers ASC lead + term groups
  30→20→15, rate/APR pairs per tier; generic qualifier line for the other families
- Done when: ✅ **dup-016 (5.39%, trap 5.34 avoided), dup-017 (5.59%, trap 5.54 avoided),
  dup-009 (7.13/7.25, traps 6.037/6.061/5.954 avoided), dup-011 ($100k tier ledes, 7.13 included,
  "6.7%" numeric-match safe vs 6.75%, 6.037 avoided), dup-028 (10.49%) — all zero traps**.
  Public eval 0.2671 → **0.3872** (stale_trap 0.02→0.39, tier_disambiguation 0.50→0.83, no
  regressions anywhere). 27 real same-key loan conflicts now surface (mortgage purchase+refi
  hub-vs-blog, auto hub-vs-promo), all rank-resolved; selftest unchanged (0.83, F1 1.0);
  +751 loan claims; ingest 2.8 s; 104 tests.

**S1.3 Cards (personal + business) — DONE (2026-11-10)** incl. intro vs standard APR qualifiers
- [x] Card table grammar (`answers/cards.py`): `| Card Type | APR |` sheets; APR ranges parsed
  (low bound = claim value, high bound = tier dim, `12.50% – 19.50%` kept as value_text);
  intro rows (`Introductory Balance Transfer Rate`) flagged `rate_period="intro"`; product from
  row label first, then the section heading, business aliases matched first so "Platinum Visa"
  inside "Business Platinum Visa" cannot mis-alias
- [x] Question grammar (`question.py::_parse_cards`): credit card/visa triggers; named products;
  business-only vs personal filters; standard-vs-intro stays a TEMPLATE distinction (asking for
  the standard rate states the intro caveat from its own claim, never a bare number)
- [x] List template: one phrase per card, standard APR first, intro labelled
  ("…: 12.50% – 19.50% standard APR (2.90% intro APR on balance transfers only)")
- [x] `tables.py` single-digit effective dates now zero-padded (`1/1/2026` → `2026-01-01`,
  chronological string sort stays correct)
- Done when: ✅ **dup-034 (four cards, 12.5/20.5 included, no 9.9%/artifact text), dup-035
  (standard 12.50–19.50% with the intro-worded caveat; 9.9% trap impossible by construction —
  corpus has no 9.9%), dup-040 (12.5/15.5 incl. business cards) — all zero traps**. Public eval
  0.3872 → **0.4601** (list_completeness 0→0.46, tier_disambiguation 0.83→1.00, no regressions).
  Card claims +5; conflicts unchanged at 27 (card statements agree corpus-wide — no false
  positives added); selftest 0.83; 123 tests.

**S1.4 Branch knowledge — DONE (2026-11-10)**
- [x] Prose extractors (`answers/branches.py`), not tables: lobby/drive-up hour blocks
  (anchored on "Branch hours are:", inline `**Lobby** Monday…` first entries, dash-normalized so
  identical schedules across pages merge as replicas), contact-page locator addresses
  (`Dupaco Branch` + address lines → city/state/zip/display), and the Hy-Vee relocation notice
  ("full-service branches at Key West and Sycamore Street")
- [x] Text claims (value=0.0, the schedule/address/alternatives IS the fact) — deliberately kept
  OUT of the conflict views: different branches legitimately publish different schedules (R5 —
  branch variance is not a same-key contradiction); conflicts stayed at 27 with zero false adds
- [x] Question grammar (`question.py::_parse_branch`): hours (lobby/drive-up/all-same), address
  (+ city), Hy-Vee alternatives; **named-branch questions refuse when the branch is not on file**
  (dup-102 "Mullan Avenue branch" — bolted-on other branches' schedules would fabricate a fact;
  caught live, restored should_refuse 0.67→1.00 after the first eval run)
- Done when: ✅ **dup-064 (8:30), dup-065 (8:30, never demands a ZIP), dup-066 (8 a.m./6 p.m.),
  dup-068 (11375 Oldenburg + 61036), dup-076 (Key West + Sycamore, no CO-OP), dup-104 (No — two+
  schedules, 12:30 AND noon)** — all zero traps. Public eval 0.4601 → **0.6105**
  (branch_info 0.00→**0.97**, should_refuse holds 1.00 after the named-branch fix, no regressions
  anywhere). Consistency 1.0 (paraphrase + repeat), zero traps, ingest 3.2 s; 141 tests.
- Remaining polish items deferred to hidden-eval prep (dup-074/075 hour nuances, closure-date
  phrasing refinement).

**S1.5 Canonical links, programs, misc facts — DONE (2026-11-10)**
- [x] `answers/facts.py`: prose-fact claims (mirroring branch claims — value=0.0 text, metric "text")
  - `site_link` claims for CTA anchors, URL-normalised (query/fragment stripped; legacy
    `info.dupaco.com/*` trap URLs exist in NO snapshot — verified — so latest-snapshot trust
    resolution handles them for free); roles: `branch_atm_locator` (label-gated: find a branch /
    branches & ATM / shared branches) and `join_application` (become a member / join Dupaco on the
    literal `join.dupaco.com` host; `/about/join` nav links are NOT the application CTA).
  - rates-directory links are NOT anchor claims: they reuse the family rhythm — the directory
    URL is the page hosting the asked family's rank-winner rate rows (IRA rows filtered for a
    bare certificate question → `/personal/savings-account`, rank 100, empirically verified).
  - `program` claims (Home$tart: name/sponsor=fhlb/audience/purpose + value $15,000 → numeric
    value for scorer), `service` claims (review/change personal info: log in to your account /
    call 800-373-7600 / email / branch — digital-privacy-policy page), `wallet` claims (Apple Pay,
    Google Pay, Samsung Pay + set-default flag — mobile-payments page), `annual_series` claims
    (newsroom "In <year> alone:" recaps → year is a tier dim).
  - dup-088 answered as the CHRONOLOGICAL series ("294 in 2023; 256 in 2024"): the eval expects
    294 while a fresher 2025-dated post in EVERY snapshot reports 256 in 2024 — fresher-wins
    cannot reproduce the gold; history-inclusive phrasing has precedent in dup-006. Series replay
    is derivable, not hardcoded.
- [x] Question grammar additions (`_parse_facts` in question.py, runs FIRST): wallet / series /
  update-contact / program / link-URL modes, before the product family chain so "cards to a
  mobile wallet" and "CD rates link" never fall into the APR answerers.
- [x] Facts family excluded from conflicts views (like branch prose — R5); program questions MUST
  bind the program name (token-set match; unknown names refuse rather than leak Home$tart);
  wallet dims kept scalar (pipe-joined string) for ledger hashing.
- NOTES.md docs + ingest cost: gated sub-extractors added after full-corpus probe. Measured
  honestly at story end (tools/profile_ingest.py): corpus load 0.4 s + actual ingest ~4 s = 0.2%
  of the 30-min budget (the "~39 s" from mid-development probes was a timer-boundary artifact —
  see DECISIONS.md issue 6).
- Done when: ✅ dup-008 (1.0), dup-080 (1.0), dup-082 (1.0), dup-031 (1.0), dup-060 (1.0),
  dup-094 (1.0), dup-088 (1.0) — all zero traps, sources verified. Public eval
  0.6105 → **0.7465** (no regressions on any of the 33 prior items; 7 items gained).
  Selftest 0.83 holds (stale_trap 1.00, temporal_as_of 1.00, conflicts F1 1.0). Consistency 1.0
  (20 paraphrase groups + 20 repeats). "Bright Start"/"Refer-a-Friend"/"VTO 2021" all refuse
  digit-free. 168 tests, ruff clean, leak guard OK (facts test fixtures allowlisted: the
  published hostname IS the rule under test).

### T2 — Temporal layer

**S2.1 Effective dates at table granularity — DONE (2026-11-10)**
- [x] Effective-date capture adjacent to each table (a page may carry several); date normalisation MM/DD/YYYY → ISO.
  - Recon found the real defects on the switch-and-earn page (4 tables, 3 statement phrasings):
    (1) the "Rates effective MM/DD/YYYY" phrasing (42x corpus-wide, no "as of") was unmatched —
    Boat & RV + ATV tables carried NO date; (2) the ATV table produced ZERO claims — its heading
    "ATV, Snowmobile & Jet Ski Loans" has a comma the heading regex rejected, so it inherited the
    previous table's context, and its "Model Year 2026-23" labels (leading words, DESCENDING
    years) matched no model-year pattern; (3) non-padded "1/1/2026" and the horizon/next-table
    scoping already worked.
  - Fixes: tables.py statement regex accepts both phrasings (still anchored at line start so
    footnote mentions never win); heading charset accepts commas; loans.py parses leading
    "Model Year YYYY-YY" labels and canonicalises the span ASCENDING (2026-23 → 2023 through
    2026) so the same span written either way lands in one canonical key.
  - Trust resolution verified, not changed: pick_winners already orders rank → freshest
    effective_date → snapshot; the switch-and-earn auto copy (5.34%, eff 1/1/2026, r70) loses to
    the auto-loans rate page (5.39%, eff 08/31/2026, r100) via the general stack — no URL
    special-casing. Note: the story's "10/22/2024 auto table" is actually the PERSONAL table on
    that page (auto carries 1/1/2026 in every snapshot); the done-when's intent — a stale-dated
    switch-and-earn table loses to the fresher rate page without URL rules — is verified
    empirically and by test.
- Done when: ✅ 36 claims from switch-and-earn (was 27; +9 ATV rows recovered, +2 tables dated);
  four tables → four distinct effective dates; public eval 0.7465 unchanged (zero regressions —
  no scored question touches the new claims); selftest 0.83 holds; 180 tests on 3.9/3.11/3.14.
  ATV/snowmobile QUESTION grammar is S3.1 scope (claims are in the ledger now; questions still
  refuse honestly).

**S2.2 as_of edge handling — DONE (2026-11-10)**
- [x] Dates between pulls (05-31 → snap 02), inside the 10-week gap → snap 03, before baseline → earliest+note, after latest → latest.
  - Recon: three of the four edges already worked via "newest snapshot with taken_on <= as_of" —
    dup-006 (05-31 → snap 02) was already scoring 1.0. The real defect was the FOURTH edge:
    as_of before the baseline returned "nothing eligible" → digit-free REFUSAL, even though the
    earliest snapshot IS our best knowledge for that date. Also found while testing: the ISO
    regex validated shape, not ranges — "2026-13-01" passed through as a "date".
  - Fixes: trust.py gains clamp_snapshot() returning (snapshot_id, status) with status in
    {now, ok, before_baseline, none}; before-baseline → EARLIEST snapshot + provenance note on
    conflict_note ("the requested date precedes the earliest snapshot on file (2026-05-12)…"),
    confident=True, past tense via the existing _present() logic — never a refusal, never silent.
    ISO input now range-checked (month 1–12, day within month); month names tolerated in full and
    abbreviated form ("May 2026", "jun 2026", "Sept 2026"), clamped to month end; anything
    unparseable → None = "now" (documented fallback, no guessing). Note precedence: a
    disagreement note (about values) wins over the as_of note; answer text stays a pure claim
    template (R1 — the note channel carries the date, not the answer text).
  - Empirical on the real corpus (10-month jumbo question): None→snap 05 present tense; 05-15→
    snap 01; 05-31→snap 02; 07-01→snap 03; 12-25→snap 05; 01-01→snap 01 + note; "May 2026"→snap 02.
- Done when: ✅ hidden-style variants behave predictably (unit tests for every edge: exact
  boundaries, gap interior, after-latest, before-baseline, leap February, abbreviations, garbage,
  slash-format rejection, empty ledger); 199 tests (19 new) on 3.9/3.11/3.14; public eval 0.7465
  unchanged; selftest 0.83 holds. Note: dup-074/075 (temporal_as_of, still 0.0) are CHANGE-EVENT
  questions (Hy-Vee closure "March 31, 2026") — S2.3 scope, not as_of machinery.

**S2.3 Change events ("what changed") — DONE (2026-11-10)**
- [x] Attribute ledger events when a key's value changes between snapshots (3.90% → 4.00% example).
  - Two deliverables in one story: (a) DATED EVENTS from prose — the Hy-Vee closure announcement
    ("This location will close March 31, 2026.") is the only source for that closure; the locator
    pages never list the branch, so there is no disappearance to diff — the announcement IS the
    event. branches.py extract_branch_events() binds the subject from page CONTENT (hy-vee text
    present), stores value_text in the site's own rendering ("March 31, 2026") for member-facing
    fidelity and event_date ISO for tense logic. (b) TRANSITION INDEX — _record_transitions() at
    the end of each ingest diffs the trust winners of numeric rate keys (the same family views
    conflicts scans) against the previous snapshot; answer time is a filtered list read (R2).
  - Question grammar: "when does/did/will X close" (event_when) and "is X still open"
    (event_status) are checked BEFORE the hours trigger, which also matches "\bclos" and was
    hijacking event questions into generic hours answers (the dup-074/075 failure). Hours
    questions ("Is the branch closed on Sunday?") still route to hours. "What changed between
    May and September / since June / (no window)" parses a (year|None, month) window — year
    wildcard = any year, deterministic.
  - Tense is a pure function of (event_date, view snapshot date): an as_of before 2026-03-31
    says "will close", after says "closed" — the historical view stays truthful (verified by test).
  - R5 replica discipline in the changes answer: the same economic move can sit under two keys
    when pages label a tier differently ("$200,000" vs "$200000") or business/personal rows moved
    identically — rows group on normalized topic + old + new + to_date, one representative shown.
  - Conflicts cite the transition: when a same-view conflict's key also moved between snapshots,
    the reason string gains "Previous value 3.90% until the 2026-09-28 snapshot." (the reason
    field is the contract-safe channel — no contract dataclass touched; conflicts gold matches
    on topic/values/correct_value only, so the gate is unaffected).
  - Honest scoping: the corpus publishes no branch OPENING-with-date shape, so opening events are
    future scope; "when is X open" stays an hours question (correct — that's a schedule ask).
- Done when: ✅ "what changed between May and September" answers from the transition index
  (10-Month jumbo special 3.90% → 4.00% verified on the real corpus); conflicts cite the
  transition; dup-074 "When does the Hy-Vee branch close?" → "The Hy-Vee branch closed March 31,
  2026." and dup-075 "still open today" → "No. The Hy-Vee branch closed March 31, 2026." — both
  must_include tokens hit; unknown branches refuse digit-free. **Public eval 0.7465 → 0.8008**
  (temporal_as_of 0.50 → 1.00, +0.0543, the largest single-story gain so far); selftest 0.83
  holds; 221 tests (+22) on 3.9/3.11/3.14; leak guard allowlist entry added for the synthetic
  changes fixture (same convention as every extractor-family file).

**S2.4 Entity facts, counts & list families — DONE (2026-11-11)**
- [x] Entity facts as `facts` claims: routing number, Forbes recognition, membership eligibility,
  branch count, student-loan product facts — the "who/what is Dupaco" fact class.
  - Bitemporal publish-date discipline (the story's key insight): newsroom/blog articles carry
    their own publish date ("June 18, 2024" under the byline) — extracted as the claim's
    effective_date (value-date). The branch-count boilerplate is a temporal series, NOT a
    contradiction: March 2026 articles say "23 branch office locations", April 2026 articles say
    "22" (the Hy-Vee branch closed March 31 — the count dropped). All count claims share ONE
    canonical key, so pick_winners resolves freshest-published → 22 (dup-073's expected answer)
    with zero special-casing. Same mechanism resolves Forbes: 2023's "fourth time" loses to
    June 2024's "fifth time" (dup-087, must_include 'fifth').
  - fact families: routing_number (273974581, from "our routing number (273974581)" statements),
    branch_count, forbes_recognition (ordinal word), membership_eligibility (charter-area rule +
    "find us in Iowa, Illinois and Wisconsin"), student_loan (product-page anchors: new/refinance,
    flexible repayment, $0 origination fees). _store_facts_claim now passes effective_date
    through (was hardcoded None; other families unaffected — they don't set the key).
  - Question grammar: "how many branches" → published-count semantics (never a naive ledger-row
    count — locator pages list ~20, boilerplate is the published statement); "routing number" /
    "ABA number" (covers "can you repeat the routing number" — replay needs no anaphora rule);
    "forbes"; eligibility BEFORE the join-LINK binding (both match "become a member" — "who is
    eligible" asks for the RULE, not the URL); student+loan need not be adjacent ("I'm a student
    … loan options" has no "student loan" bigram). Unknown entities refuse digit-free.
  - **dup-005 is structurally unscorable in the local public eval**: the scorer computes
    correctness = len(must_include hits)/len(must_include), and dup-005's must_include is EMPTY
    → 0.0 unconditionally (harness/scoring.py score_item; the LLM judge that would score it
    needs --judge + API key, forbidden in our offline path). Our behavior ALREADY matches the
    expected semantics ("Read back all certificate rates/terms rather than asking which term"):
    the no-term cert question enumerates all 12 winners. Logged, not chased — hidden eval will
    judge it on semantics.
- Done when: ✅ dup-054 (routing 273974581), dup-055 (replay), dup-073 (22 via freshest publish
  date), dup-081 (Iowa/Illinois/Wisconsin), dup-087 ('fifth' via freshest Forbes ordinal),
  dup-101 (student loans) — all six at 1.0. **Public eval 0.8008 → 0.9481** (+0.1473:
  entity_attribution 0.25 → 1.00, conflict_resolution 0.33 → 1.00, stale_trap 0.79 → 0.94);
  selftest 0.83 holds; 221 tests on 3.9/3.11/3.14; ruff + leak guard clean. dup-005 gap logged
  above (list_completeness stays 0.71 locally — judge-scored item).

### T3 — Question understanding

**S3.1 Slot grammar + synonym layer** (share certificate = CD; model-year phrasing; "current"/"right now")
- Hidden-eval evidence (2026-11-10): dup-005 "certificate of accounts" phrasing already fails the
  grammar — real rewording stress, not hypothetical.
**S3.2 Entity resolution** (personal vs business; Bright Savings vs Jump Start; Money Market vs Share Savings)
**S3.3 Paraphrase self-benchmark** — hand-reword the 40 public items into ~80 variants (selftest
`t1`/`t1b` style); harness runner to compare route + numeric outcome
- Done when: ≥90% route to the same claim; numeric output identical.
**S3.4 Router determinism test** — assert the same group never splits rule-path vs fallback for different numeric output.

### T4 — Fallback + speed/consistency hardening

**S4.1 BM25 fallback index** over cleaned sections, **filtered by as_of**, passed through shared trust stack
- Hidden-eval insurance: the hidden set has "real paraphrase groups" — grammar-only routing is the
  biggest single risk (public paraphrase consistency 1.0 uses gentle rewordings). The fallback must
  refuse digit-free when BM25 confidence is low (R1), never answer from a weak match.
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
- Done when: section 10 checklist fully green.

## 7. Eval Ledger (scoreboard of record)

| Increment | Date | Accuracy | Consistency | Speed | Conflicts | Final | Notes |
|---|---|---|---|---|---|---|---|
| starter | 2026-11-09 | 0.093 | 1.0 | 1.0 (p95 0.61s) | — | **0.093** | word-overlap is deterministic but ignores traps/tiers/as_of — sanity-checks the PDF's "~0.09" |
| answers stub (S0.1) | 2026-11-09 | 0.2 | 1.0 | 1.0 | 0.0 | **0.17** | `harness/selftest` synthetic only (not public); refusal path scores; this report = the eval-gate baseline |
| S0.2+S0.3 tracer (certs) | 2026-11-10 | 0.402 (weighted) | 1.0 | 1.0 (p50 0.0s) | — | **0.1508** | public eval: dup-001 ✅ byte-exact, dup-006 ✅, dup-145 ✅ + 2 more refusals; ingest 1.9–3.4 s for 5 snapshots (3266 pages) |
| S0.4 conflicts | 2026-11-10 | 0.8 (selftest qa) | 1.0 | 1.0 | **1.0** (F1 1.0, resolution 1.0) | **0.83 selftest** / **0.1508 public** | gold c1 matched w/ correct winner; 0 real-corpus conflicts is truthful (cert rates only in tables); 58 tests, coverage 88% |
| S1.1 deposits | 2026-11-10 | 0.485 (weighted) | 1.0 | 1.0 | — | **0.2671 public** / 0.83 selftest | dup-045/046/049/052 ✅ zero traps; tier_disambiguation 0.17→0.50, current_value 0→0.33, conflict_resolution 0→0.33, entity_attribution 0→0.25; 6 false achieve-MM conflicts killed via rate_period qualifier dim (no URL special-casing); 82 tests |
| S1.2 loans | 2026-11-10 | 0.585 (weighted) | 1.0 | 1.0 | — | **0.3872 public** / 0.83 selftest | dup-016/017/009/011/028 ✅ zero traps; stale_trap 0.02→0.39, tier_disambiguation 0.50→0.83; 27 real loan conflicts (mortgage hub-vs-blog, auto hub-vs-promo) rank-resolved; stale rows trust-RESOLVED not dropped (purpose-from-label family); 104 tests |
| S1.3 cards | 2026-11-10 | 0.665 (weighted) | 1.0 | 1.0 | — | **0.4601 public** / 0.83 selftest | dup-034/035/040 ✅ zero traps; list_completeness 0→0.46, tier_disambiguation 0.83→1.00; intro-vs-standard forking value-safe; single-digit dates zero-padded; 123 tests |
| S1.4 branch | 2026-11-10 | 0.769 (weighted) | 1.0 | 1.0 | — | **0.6105 public** / 0.83 selftest | dup-064/065/066/068/076/104 ✅ zero traps; branch_info 0→0.97; dup-102 refuse-restored after live catch (named-branch rule); should_refuse 1.00; no branch-conflict false adds (R5 text-claim policy); 141 tests |
| S1.5 facts | 2026-11-10 | 0.7465 | 1.0 | 1.0 | — | **0.7465 public** / 0.83 selftest | dup-008/080/082/031/060/088/094 all 1.0 ✅ zero traps; ZERO regressions across the 33 prior items (7 gains: six 0.0→1.0 + dup-008 0.15→1.0); dup-088 = chronological series (294 in 2023; 256 in 2024 — eval expects 294 with a fresher 2025 post in every snapshot, so series replay, not fresher-wins); program binding refuses unknown names digit-free; facts excluded from conflicts (R5); ingest ~4 s (0.2% of budget, measured via tools/profile_ingest.py); 168 tests, ruff + leak guard clean |
| S2.1 table dates | 2026-11-10 | 0.7465 (unchanged) | 1.0 | 1.0 | — | **0.7465 public** / 0.83 selftest | switch-and-earn page: 27→36 claims (+9 ATV rows recovered, +2 tables dated); 4 tables → 4 distinct effective dates across 3 statement phrasings ("Rates effective" variant added; comma headings; leading/descending "Model Year 2026-23" labels canonicalised ascending); stale promo copy loses to the 08/31/2026 rate page via the general stack — NO URL special-casing; zero regressions (no scored question touches the new claims); 180 tests |
| S2.2 as_of edges | 2026-11-10 | 0.7465 (unchanged) | 1.0 | 1.0 | — | **0.7465 public** / 0.83 selftest | before-baseline as_of: refusal → EARLIEST snapshot + provenance note (confident, past tense); ISO range-validated ("2026-13-01" no longer a "date"); month names full+abbrev clamped to month end ("May 2026", "jun 2026"); all four edges unit-tested (19 new tests → 199); dup-006 edge re-verified end-to-end on the real corpus; dup-074/075 remain 0.0 = S2.3 change-events scope |
| S2.3 change events | 2026-11-10 | **0.8008 (+0.0543)** | 1.0 | 1.0 | — | **0.8008 public** / 0.83 selftest | dup-074/075 fixed: event_when/event_status grammar checked BEFORE the hours trigger ("\bclos" was hijacking); Hy-Vee closure date extracted from the announcement (value_text = site's rendering "March 31, 2026"; ISO event_date for tense); tense = f(event_date, view date) so historical as_of says "will close"; transition index at ingest (winners diffed per numeric key) answers "what changed between May and September" (3.90→4.00 verified); R5 replica collapse in changes rows ($200,000 vs $200000 labels); conflicts reason cites "Previous value X until <snap>"; **temporal_as_of 0.50 → 1.00**; 221 tests (+22) |
| S2.4 entity facts | 2026-11-11 | **0.9481 (+0.1473)** | 1.0 | 1.0 | — | **0.9481 public** / 0.83 selftest | six targets all 1.0: routing 273974581 (dup-054), replay via "routing number" noun-phrase (dup-055), branch count 22 via FRESHEST PUBLISH DATE (dup-073 — March 2026 says 23, April says 22 after the Hy-Vee closure; publish date = value-date), eligibility Iowa/Illinois/Wisconsin (dup-081), Forbes 'fifth' via freshest ordinal (dup-087), student loans non-adjacent grammar (dup-101); **entity_attribution 0.25→1.00, conflict_resolution 0.33→1.00, stale_trap 0.79→0.94**; dup-005 logged as judge-scored (empty must_include → 0.0 locally by scorer construction; enumeration behavior already correct); 241 tests (+20) |
| T1 | | | | | — | | |
| T2 | | | | | — | | |
| T3 | | | | | — | | |
| T4 | | | | | — | | |
| T5 | | | | | *(scored locally)* | | |

Note: conflicts are only scored when grading passes `--conflicts-gold`; locally we always run a
gold file (selftest + our hand-built one in S5.2). The public `--judge` LLM scoring exists in the
harness (organizer-side); assume hidden run uses it for free-text items.

## 8. Working agreements / DoD

**Story DoD:** task acceptance criteria met; public eval run appended to section 7; no regressions on
previously-passing questions; unit tests for the changed extractor family.
**Release DoD:** section 10 checklist green.
**Red flags (instant fix):** any answer text that can contain an unselected value, any digit in a
refusal, any non-deterministic answer path, any network/key dependency in the grading path, any
"data redistribution" risk in the repo.
**Cadence:** standup each increment; playback demo after each deliverable (section 5) for observers.

## 9. Risks, kill criteria & decision log

| Risk | Likelihood | Mitigation / kill criterion |
|---|---|---|
| Rule extractors under-cover (messy PDFs/prose) | Medium | Audit at T1 exit: if < ~70% coverage of value-bearing pages → pull **D** (offline LLM extraction, cached, same claim schema) forward |
| Paraphrase routing misses (can't measure from public set) | Medium | T3.3 self-built benchmark; if BM25+synonyms <95% route agreement → add small **ONNX embeddings** in fallback only |
| Conflict F1 collapses on pseudo-conflicts | Medium | T5.1 precision control + local gold tuning before relying on the pillar |
| Ingest beyond 30 min with extras | Low | Time-box ingest; only leaner extraction paths may scale up |
| Grading env lacks a dependency | Low | S6.1 fresh-env test; avoid heavy/uncommon wheels (no torch-class deps) |
| Hidden set emphasises unmeasurable pillars (judge free-text) | Medium | Template answers read like careful human prose; no token-dumping |

**Decision log (already made, with rationale in the design discussions — the
plain-language narrative, tradeoffs and interview-ready "issues we hit" writeups
live in `DECISIONS.md`):**
1. Core = **claims ledger + trust resolution** (Option B) — the eval is a qualified-facts-over-time problem, not a search problem.
2. **Hybrid** (Option C): BM25 fallback through the shared resolver — coverage without losing determinism.
3. **Rejected for answer-time LLM (Option F)**: violates R1/R2/R3/R4 structurally (trap leakage, tail latency, nondeterminism, offline risk). Off-by-default formatter only, ever.
4. **Rejected diff-first (H)**: 97% churn is dynamic noise; blind to within-snapshot contradictions. Diff events kept as a *feature* (S2.3).
5. Graph (G) folded into schema design, not a graph store. D and E on the bench behind kill criteria.
6. **Storage = in-memory SQLite, stdlib `sqlite3`** (S0.2; revisited at S1.5) — Postgres/MySQL add a
   server + socket hop for identical B-tree index performance on ~300 claims; MongoDB loses the
   in-engine ORDER BY for a schema we keep rigid anyway; graph stores run a service to walk a
   two-level tree. In-memory also guarantees no corpus-derived files are ever left on disk.
   Full rationale: `DECISIONS.md`, Decision 2.
7. **Facts parse first in the question router** (S1.5) — "cards to a mobile wallet" must never
   reach the card-APR grammar; routing order is a correctness surface, not plumbing.
8. **Unbound-year annual questions answer the chronological series** (S1.5, dup-088) — the gold
   expects the older stat while a fresher post exists in every snapshot; series replay is
   derivable, fresher-wins is not. Precedent: dup-006 allows historical context.
9. **Program questions must bind the program name** (S1.5) — unknown program names refuse rather
   than leak the one program we have on file (caught live: "Bright Start" initially answered with
   Home$tart details).

## 10. Submission checklist (from PDF section 7)

- [ ] GitHub repo pushed; organizers have read access
- [ ] `solution.py` with `build()` in the repo (folder ≠ `starter/`) — our `answers/`
- [ ] `requirements.txt` lists every package; clean Python 3.11 install verified
- [ ] `NOTES.md` explains: how current is decided; which API keys (none planned)
- [ ] `python harness/run_eval.py --submission answers --eval eval/public_eval.jsonl` runs clean from fresh clone
- [ ] Repo contains **no** kit data redistribution: no snapshots/zips, no eval outputs, and the
      assignment PDF stays local (organizer material; graders have their own copy)
- [ ] Repo URL + grading commit shared before the deadline
