# CTO_Polish_Plan.md — Production Polish Pass (CTO Audit)

**Project:** Redrob Rank Engine — Track 1
**Scope:** non-behavioral, production-quality polish across the Python engine and
the Streamlit dashboard — (1) UI/perf polish in `app.py`, (2) strict type hints on
every engine function, (3) Google-style docstrings on every engine function, and
(4) migration of diagnostic `print` helpers to a shared `logging` facility.
**Companion docs:** `Rules.md` (invariants R1–R10), `Schema.md` (real record
shape + honeypot catalog), `V4_Hotfix_Plan.md` (prior behavioral pass).

This pass is **deliberately non-behavioral**. It does **not** touch the Phase-1
artifacts (FAISS index, byte-offset index, id_map), scoring weights, recall-K,
honeypot logic, the reasoning grammar, or the output schema. The single hard
gate is that `team_vibecoder.csv` must remain **byte-identical** (sha256
`dc3432e2815a99951f80ffecee3e8169c956c2681b33a834da7cedfe142e6952`).

---

## Provenance — a "Google-level production polish" review

The audit framed four workstreams as a CTO readiness review. Vetted honestly
against the **real code** before any edit: the codebase was already largely typed
and the dashboard already cached and reasonably presented, so this pass *closes
gaps and standardizes* rather than rebuilding. Each workstream is scoped so it
cannot alter engine output.

---

## Why these changes are provably byte-safe

1. **Type hints + docstrings are runtime no-ops.** Every engine module carries
   `from __future__ import annotations`, so annotations are never evaluated at
   runtime; docstrings only populate `__doc__`. Neither can affect the data path.
2. **Logging routes to stderr only.** The new logger writes to **stderr**; the
   CSV is written to a file and the machine-readable CLI contracts
   (`validate_submission`'s `RESULT:` line, `run_ranker`'s RESOURCE PROFILE /
   rule banners / CSV preview) are kept on **stdout** unchanged.
3. **`app.py` edits are presentational.** Only CSS, layout, and empty-state copy
   changed; all displayed data values are read straight from the CSV untouched.

---

## Workstream 1 — `app.py` UI/perf polish (presentational only)

**Change.** Added scoped CSS (tighter container width, refined metric cards in the
sidebar, rounded dataframe, heading letter-spacing), a section divider above the
filter, an explicit **empty-results** state when a filter matches nothing, and a
footer caption. The existing `@st.cache_data` load remained the perf backbone.

**Invariant check.** No data transformation added or removed; metric values
(`Candidates Ranked`, `Top Score`, `Cutoff Score #100`) and the table are
rendered from the same `load_rankings` DataFrame as before.

---

## Workstream 2 — strict type hints on every engine function

**Change.** Closed all remaining annotation gaps (argument + return types) across
`phase1_precompute.py`, `phase2_ranker.py`, `phase3_reasoning.py`,
`run_ranker.py`, `validate_submission.py`, and `main.py`, including nested
closures (the air-gap `guarded_connect`/`guarded_create`/`_host_of`), the
`network_air_gap` context manager (`Iterator[None]`), and the reasoning AST node
classes. `TYPE_CHECKING`-guarded imports are used for heavy optional deps
(`faiss`, `numpy`) so typing adds no import cost.

**Invariant check.** Annotations are not evaluated at runtime (future-annotations);
zero behavioral effect. Verified by AST audit: every function has a return
annotation and fully-annotated args.

---

## Workstream 3 — Google-style docstrings on every engine function

**Change.** Added concise Google-style docstrings to every engine function and
method, documenting purpose, grounding/contract notes (R2/R10 call-outs where
relevant), and return semantics. Trivial AST-node `render`/`__init__` overrides
get one-line summaries so the audit is uniformly clean.

**Invariant check.** Docstrings only set `__doc__`; no behavioral effect.

---

## Workstream 4 — migrate diagnostic prints to `logging`

**Change.** Added `engine/logging_util.py` — a shared, idempotent
`get_logger(name)` under the `redrob` namespace that emits to **stderr**. The
per-module `log()` print-helpers in `phase1`, `phase2`, and `run_ranker` now
delegate to the logger, mapping `ERROR`/`WARN`-prefixed messages to the matching
levels.

**Deliberately kept on stdout (CLI contracts):**
- `validate_submission.py` → the `RESULT: PASS/FAIL` line other tooling greps.
- `run_ranker.py` → the RESOURCE PROFILE table, `_rule` banners, and CSV preview
  (the human-facing benchmark report / deliverable output).

**Invariant check.** Diagnostic stream moved stdout→stderr; the data file and the
machine-readable stdout contracts are unchanged, so no consumer breaks.

---

## Validation plan (post-edit)

1. **Byte-identity gate (primary).** Regenerate from existing artifacts:
   `python engine/phase2_ranker.py --artifacts engine/data
   --jd-file job_description.docx --out team_vibecoder.csv` and confirm sha256 ==
   `dc3432e2815a99951f80ffecee3e8169c956c2681b33a834da7cedfe142e6952`.
2. **Determinism (R7).** Run the ranker twice and `diff` the two CSVs → must be
   byte-identical.
3. **Acceptance.** `engine/validate_submission.py team_vibecoder.csv --artifacts
   engine/data --jd-file job_description.docx` → expect PASS (header, 100 rows,
   unique ids, contiguous/monotonic rank, score∈[0,1], 100% grounded reasoning).
4. **Compile + audit.** `python3 -m py_compile engine/*.py main.py app.py` and an
   AST sweep asserting every function has full type annotations and a docstring.
5. **UI smoke.** Start the Streamlit workflow and confirm the dashboard renders
   with all metric values intact.

**Outcome (this pass):** sha256 matched baseline (byte-identical), two runs were
byte-identical (deterministic), validator returned PASS with 100% grounding, all
modules compiled, the AST audit reported CLEAN across every file, and the
dashboard rendered correctly.
