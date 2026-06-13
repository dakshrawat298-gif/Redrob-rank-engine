# V4_Hotfix_Plan.md — V4 Edge-Case Hotfixes

**Project:** Redrob Rank Engine — Track 1
**Scope:** two targeted edge-case fixes in `engine/phase2_ranker.py` and
`engine/phase3_reasoning.py`, plus regeneration + revalidation of
`team_vibecoder.csv` and recompilation of the master audit bundle as
`NotebookLM_Master_Codebase_V4.txt`.
**Companion docs:** `Rules.md` (invariants R1–R10), `Schema.md` (real record
shape + honeypot catalog), `Stage4_Hotfix_Plan.md` (prior pass).

These changes are surgical. They do **not** touch the Phase-1 artifacts (FAISS
index, byte-offset index, id_map), scoring weights, recall-K, or the output
schema. The CSV is regenerated from the existing artifacts with the phase-2
entrypoint.

---

## Provenance — a V3 NotebookLM audit raised three findings

Each finding was vetted against the **real code** before any edit. The verdict:
two are valid (Zero-Span, Fallback crash) and are fixed below; one (substring
`match_skills`) is a **false and harmful** finding and is explicitly **rejected**
with reasoning, so a future reader does not "re-fix" it.

---

## Finding #1 — Zero-Span honeypot bypass (VALID → Fix A)

**Problem.** The fabricated-profile checks in `detect_honeypot`
(`overlapping_timeline` and `experience_inflation`) are both gated on
`span > 0`. A honeypot whose `career_history` carries dates that collapse to a
**zero-month** calendar window (e.g. identical start/end, or end before start
clamped to 0) therefore *bypasses both checks* — the very profiles most likely
to be fabricated slip through.

**Root cause.** `span > 0` was meant to guard against *missing* date data, but
it conflates two distinct cases:
- `span is None` — no parseable dates at all → genuine no-data, must be skipped
  so we never false-drop (R10 spirit: don't punish missing data).
- `span == 0` — dates **are** present but describe an impossible zero-length
  career → this is itself a fabrication signal and must be caught.

**Fix A.** In `detect_honeypot`, compute a single
`effective_span = max(span, 1) if span is not None else None` immediately after
`_career_span_and_tenure_months`. Both ratio checks now use `effective_span`:
- `span is None` → `effective_span is None` → both checks skip (unchanged,
  no new false drops).
- `span == 0` → `effective_span == 1` → the ratio checks fire, catching the
  Zero-Span honeypot via `overlapping_timeline` (any real tenure) or
  `experience_inflation` (any real `years_of_experience` claim).

**Invariant check.** R4 (honeypot dropped + reason logged). R10 preserved:
missing-data profiles are still skipped, so no genuine candidate is false-dropped
by the change. The fix is applied to **both** `overlapping_timeline` and
`experience_inflation` because they share the identical `span > 0` guard — fixing
only one would leave a parallel bypass.

---

## Finding #2 — substring `match_skills` (FALSE & HARMFUL → REJECTED)

**The audit claimed** `match_skills` uses naive substring (`in`) matching and
should be "fixed", and cited a "Multi-Word Trap" like *Marketing Manager*.

**Why this is wrong (do NOT implement):**
1. **It mischaracterizes the code.** `match_skills` (`engine/phase3_reasoning.py`)
   already uses **whole-word** matching via `_jd_contains_word`, *not* `in`. The
   substring class of bug it warns about is already prevented.
2. **Switching to substring would reintroduce a hallucination bug (R2 harm).**
   Substring matching is exactly what causes false positives like "Go" matching
   inside "category" or "Rust" inside "trust" — the opposite of grounded
   reasoning. This would directly violate R2.
3. **It targets the wrong function.** *Marketing Manager* is a **title**, not a
   skill. Off-domain titles are already dropped upstream in Pass-2 by
   `TITLE_DENY_LIST` / `_title_denied` (`domain_mismatch`, added in Stage 4), and
   `SKILL_DENY_LIST` strips non-technical trap keywords from skills. The trap the
   finding describes is already handled — by the correct mechanism.

**Decision.** No change. Documented here so the rejection is durable. If the user
still wants substring behavior after this rationale, it must be a separate,
explicit decision that accepts the R2 regression.

---

## Finding #3 — Fallback collision crash (VALID w/ caveat → Fix C)

**Problem.** `_resolve_collision` walks the `FALLBACK_POOL` (≥24 entries), then a
title-differentiated pass; if **both** are exhausted it raises `RuntimeError`,
crashing the whole run (R10 fail-loud). With ≤100 rows and a ≥24-entry pool this
is "unreachable" in normal data, but it is a latent hard-crash on adversarial or
degenerate inputs (e.g. many rows sharing a blank title and a saturated pool).

**Caveat that shapes the fix.** The obvious failsafe — append the
`candidate_id` — does **not** work naively: `candidate_id` digits (e.g. the
`0066985` in `CAND_0066985`) are **not** in `_allowed_digit_tokens`, so the
appended string would fail `_is_grounded` (R2) and we'd be back to a crash or,
worse, an ungrounded row.

**Fix C.** Add a last-resort branch in `_resolve_collision`, **before** the final
`raise`, that differentiates entries using the globally-unique `candidate_id`
(`"… (ref CAND_XXXXXXX)"`). Uniqueness is guaranteed because `candidate_id` is
unique. To keep R2, extend `_is_grounded` with an optional `extra_allowed` digit
whitelist and pass the candidate_id's own digit tokens (the id **is** a present
field of the record, so its digits are legitimately grounded).

The terminal `raise RuntimeError` is **kept** for the truly impossible case
(every variant over the 240-char budget), preserving R10's "fail loud, never
fake" intent — we never emit a duplicate or an ungrounded string.

**Invariant check.** R9 (100 unique rows) strengthened — uniqueness no longer
depends on pool size. R2 preserved — only the candidate's own id digits are
whitelisted, and only on the last-resort path. R10 preserved — a genuine
impossibility still fails loud. R7 preserved — the branch is deterministic
(fixed pool order, stable start index, deterministic id).

---

## Validation plan (post-edit)

1. Regenerate from existing artifacts:
   `python engine/phase2_ranker.py --artifacts engine/data
   --jd-file job_description.docx --out team_vibecoder.csv`.
2. Run `engine/validate_submission.py team_vibecoder.csv --artifacts
   engine/data --jd-file job_description.docx` → expect PASS (header, 100 rows,
   unique ids, contiguous/monotonic rank, score∈[0,1], 100% grounded).
3. Assert **100 unique** `reasoning` strings.
4. Confirm ≥1 hopper concern clause still appears (R3 honesty).
5. **Determinism (R7):** run the ranker twice and `diff` the two CSVs → must be
   byte-identical.
6. Recompile `NotebookLM_Master_Codebase_V4.txt` (adds this plan to the bundle,
   appends the regenerated CSV last).
