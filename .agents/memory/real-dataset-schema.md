---
name: Real Redrob dataset schema
description: Field layout of the real candidates.jsonl and how the embedding text is built from it
---

# Real candidates.jsonl schema (Redrob)

The REAL dataset differs from the early synthetic mock. Each line:

- `candidate_id` (top-level str, e.g. `"CAND_0000001"`) — this is `ID_FIELD`.
- `profile` (dict): `headline`, `summary`, `location`, `country`,
  `years_of_experience`, `current_title`, `current_company`,
  `current_company_size`, `current_industry`.
- `career_history` (list of dict): `company`, `title`, `start_date`, `end_date`,
  `duration_months`, `is_current`, `industry`, `company_size`, `description`.
- `education` (list of dict): `institution`, `degree`, `field_of_study`,
  `start_year`, `end_year`, `grade`, `tier`.
- `skills` (list of dict): `name`, `proficiency`, `endorsements`, `duration_months`.
- `certifications`, `languages` (lists).
- `redrob_signals` (dict): engagement/quality signals —
  `profile_completeness_score`, `github_activity_score`,
  `recruiter_response_rate`, `interview_completion_rate`,
  `offer_acceptance_rate`, `skill_assessment_scores` (dict per topic),
  `open_to_work_flag`, `notice_period_days`, `expected_salary_range_inr_lpa`,
  `preferred_work_mode`, `willing_to_relocate`, verified flags, etc.

100,000 records, ~487MB uncompressed.

## Embedding text (phase1 `build_text`)
The mock's flat `TEXT_FIELDS` (`current_title`/`skills`/`experience_summary`) do
NOT exist at top level in real data — a flat `record.get(field)` returns empty and
embeds garbage. `build_text` now reads the nested fields directly: headline,
`current_title` at `current_company`, industry, skill names, summary, career
titles + descriptions, education field_of_study. Capped at `EMBED_MAX_CHARS=2000`
(MiniLM truncates ~256 tokens anyway).

**Why:** running the ~60min offline build on the wrong field names silently wastes
the whole build.
**How to apply:** any new text source for embeddings must be added inside
`build_text`, not by appending flat names to `TEXT_FIELDS` (that tuple is now
documentary only).

## NOT yet reconciled
Phase 2 (rerank feature extraction) and Phase 3 (reasoning grounding) still assume
the mock schema (e.g. they reference flat company/signal fields). Before a full
ranking run is correct on real data, their extractors must be pointed at
`redrob_signals.*`, `career_history[]`, `skills[]`, etc.

## Stale-artifact caveat
The phase1 shard `.ok` marker keys on (byte-range, model, count) — NOT on input
file identity/hash. A leftover shard from a different input with a matching range
could be silently reused. Always clear `engine/data/` (gitignored) before building
on a different input.
