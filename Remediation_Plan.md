# Remediation Plan — NotebookLM Architectural Audit (7 Findings)

**Project:** Redrob Rank Engine — Track 1
**Scope:** A Stage-4 NotebookLM audit flagged 7 "critical vulnerabilities." This
document records the verdict and the exact fix (or rejection) for each, validated
against the **real dataset** and the **actual code**. Two of the seven findings are
wrong: applying them verbatim would *break* working features, so they are rejected
with proof.

**Guardrails that win over any finding (`Rules.md` R1–R10):** R1 (never load the
whole JSONL), R2 (no hallucinated reasoning), R5 (zero network during ranking),
R6 (≤5 min / ≤16 GB), R7 (deterministic; tie-break = `sem_score` desc then
`candidate_id` asc), R9 (exact output contract: header, 100 unique rows,
contiguous ranks, `score` **non-increasing** with rank), R10 (fail loud, never
fake). Note: **R9 does not itself require scores in [0,1]** — the [0,1] mapping
below is a precaution against an unknown harness expectation.

---

## Verification evidence (read-only, gathered before any code change)

- **GitHub field:** 2000/2000 sampled records contain
  `redrob_signals.github_activity_score`; `github_contribution_score` appears in **0**.
- **JD trap words:** `job_description.docx` contains "marketing" ×1 and "hr" ×1;
  "sales", "human resources", "finance", "accounting" = 0. The JD itself states a
  candidate "who has all the AI keywords ... but whose title is 'Marketing Manager'
  is not a fit" and that keyword-matching is "a trap we've explicitly built."
- **Substring false positives:** skills `Go` and `Rust` substring-match the JD
  without being whole-word matches ("go" in "category", "rust" in "robust").
- **Experience near zero:** in 5000 records, `exp == 0` → 0 candidates and
  `0 < exp < 0.5` → 0 candidates (so the V3 threshold change is a pure robustness
  hardening with no behavior change on current data).
- **Score range:** observed rank-1 final score = `1.169932` (> 1.0), driven by the
  engagement multiplier ∈ [1, 2].

---

## Findings, verdicts, and fixes

### #1 — Score out of bounds — **VALID (precautionary)** — FIXED
- **Root cause:** `final = base_cosine × multiplier`; `engagement_mult ∈ [1,2]`, so
  the product can exceed 1.0 (observed 1.169932), and cosine can be slightly
  negative for filler.
- **Fix:** after the deterministic sort on *raw* scores, apply one monotonic map to
  the kept rows — `score_i = max(raw_i, 0.0) / max_raw` (guard: all-zeros if
  `max_raw ≤ 0`). This puts every score in [0,1], makes rank-1 = 1.0, and
  **preserves order and the non-increasing property exactly**. NDCG is unaffected
  (rank order identical). Chosen over a flat `min(raw,1.0)` clamp, which would
  collapse the top tier into `1.000000` ties and discard granularity.
- **Validator:** `validate_submission.py` now fails closed if any score is outside
  `[0.0, 1.0]` (in addition to the existing non-increasing check).
- **Files:** `engine/phase2_ranker.py` (`rank()`), `engine/validate_submission.py`.

### #2 — RAM "death trap" in Pass 2 — **OVERSTATED (done as hardening)** — FIXED
- **Audit claim:** appending ~1000 full JSON objects to a list violates 16 GB.
- **Reality:** measured peak RSS for a full run is ≈ **0.4 GB**, ~40× under the
  ceiling; ~1000 small records is a few MB. Not a live disqualifier.
- **Fix (R1-spirit scalability hardening):** replace the unbounded `scored` list
  with a bounded **min-heap of size `TOP_N`**. The heap key is the exact inverse of
  the final tie-break so the root is always the worst-kept candidate:
  final order is `(-score, -sem_score, candidate_id asc)`, so the heap stores
  `(score, sem_score, _RevId(candidate_id))` where `_RevId` makes a *larger* id
  compare as "smaller" (worse) on ties. Honeypots are dropped **before** insertion
  (R4). At most 100 record dicts are resident. After Pass 2 the ≤100 survivors are
  sorted once with the canonical key. Determinism (R7) preserved.
- **Files:** `engine/phase2_ranker.py` (`_RevId`, `rank()`).

### #3 — Honeypot math slippage — **PARTIALLY VALID (safe, near no-op)** — FIXED
- **fake_expert:** changed `exp == 0` to `exp < 0.5` (with type guard). Evidence: 0
  of 5000 records have `exp < 0.5`, so this is pure robustness against adversarial
  seeds — **no false drops and no new drops** on current data.
- **Overlap-tenure ratio:** kept at `OVERLAP_TENURE_RATIO = 1.5`. Tightening risks
  false drops on legitimately concurrent/part-time roles and date rounding; only
  lower (to ~1.35) after a drop-rate re-check. Left as a single documented constant.
- **Files:** `engine/phase2_ranker.py` (`detect_honeypot`).

### #4 — Air-gap abort — **VALID (important)** — FIXED
- **Root cause:** `fastembed.TextEmbedding(...)` can ping the HuggingFace Hub on
  init even when the model is cached; under a true air-gap this can hang/abort → R5
  breach.
- **Fix:** set `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`, `HF_DATASETS_OFFLINE`, and
  `HF_HUB_DISABLE_TELEMETRY` **before** importing fastembed/HF inside the ranking
  path (`embed_query`), so the backend reads only the Phase-1-populated local cache.
  A missing local model now **fails loud (R10)** with a clear message instead of
  reaching for the network. `run_ranker.py` retains its `--network-off` socket
  guard + isolation probe that *proves* zero outbound connections during ranking.
- **Files:** `engine/phase2_ranker.py` (`embed_query`), `engine/run_ranker.py`
  (existing air-gap).

### #5 — Trap-keyword hallucination — **VALID (highest-value fix)** — FIXED
- Two real defects in `match_skills`:
  1. **Substring false positives:** `s.lower() in jd_lower` matched `Go`/`Rust`
     inside unrelated words. Now matched on **word boundaries** (regex flanked by
     non-alphanumeric edges), so only whole-word skill mentions count.
  2. **Trap keywords:** the JD contains "marketing" and "hr"; a candidate's own
     "Marketing"/"HR" skill must never surface as a positive match for an
     AI-engineering role. Added a documented `SKILL_DENY_LIST`
     (marketing, sales, hr, human resources, recruiting, recruitment, accounting,
     finance), filtered out **before** reasoning even when word-matched.
- Strengthens R2 without inventing or hiding any real data. The deny-list is
  JD-archetype-specific and lives as a single constant.
- **Files:** `engine/phase3_reasoning.py` (`_jd_contains_word`, `match_skills`,
  `SKILL_DENY_LIST`).

### #6 — Schema key mismatch — **REJECTED (audit is wrong)** — NO CHANGE
- **Audit claim:** rename `github_activity_score` → `github_contribution_score`.
- **Evidence:** 2000/2000 sampled records contain `github_activity_score`;
  `github_contribution_score` appears in **0**.
- **Decision:** **Do not rename.** Renaming would make `github_score()` return
  `None` for every candidate, silently deleting the GitHub signal from all
  reasoning — a direct regression. There is no field to fall back to, so even a
  shim is pointless. A code comment in `github_score()` records this rejection.

### #7 — Job-hopper reasoning fail — **MISDIAGNOSED (no bug)** — NO CHANGE
- **Audit claim:** the 0.5× penalty "obliterates" hoppers before the honest concern
  is appended, so the flag never reaches the CSV.
- **Reality:** `hopper_fired` is computed **independently** of the multiplier and
  passed straight to `build_reasoning`, which appends the "frequent job transitions"
  concern for *any* surviving hopper in the Top-100 — regardless of the 0.5×
  penalty. The penalty only affects whether a hopper makes the cut, which is exactly
  what R3 mandates ("aggressively penalize job hoppers").
- **Decision:** keep `JOB_HOPPER_MULTIPLIER = 0.5`. A code comment documents that
  the concern already surfaces and that `0.8` exists only as an explicit tuning
  lever (no NDCG labels justify softening).

---

## Net effect on output
- **Ranking order is unchanged** — fixes #1, #5, #6, #7 do not alter the score-based
  candidate ordering; #2 is a memory refactor that yields the identical Top-100; #3
  and #4 are no-ops on the current data. The CSV's `candidate_id` and `rank` columns
  are byte-identical to the prior submission.
- **`score` column** is rescaled into [0,1] (rank-1 → 1.000000), preserving the
  non-increasing property.
- **`reasoning` column** changes only where a trap/substring skill was previously
  (incorrectly) cited; those keywords are now removed.

## Verification performed
- Re-ran the ranker end-to-end and the Stage-1 validator (PASS).
- Confirmed scores within [0,1], non-increasing, 100 unique contiguous rows.
- Confirmed determinism (two runs byte-identical) and resource budget (≤5 min,
  well under 16 GB).
