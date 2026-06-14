# Redrob Rank Engine — Track 1

A **CPU-only** candidate ranking system built for the Redrob "India Runs AI"
Hackathon (Track 1). It scores 100,000 synthetic candidate profiles against a
job description and emits the **Top 100** as `team_vibecoder.csv` — entirely
within a **≤5-minute / ≤16 GB RAM / no-network** runtime budget.

## What it does

A two-pass retrieval-and-rerank pipeline with structurally truthful reasoning:

1. **Phase 1 — Pre-compute (offline).** Streams the candidate dataset, builds
   per-candidate embeddings (`all-MiniLM-L6-v2`, 384-dim, via `fastembed` /
   ONNX CPU), and serializes a FAISS `IndexFlatIP` plus a byte-offset index for
   lazy record loading. Not counted against the ranking budget.
2. **Phase 2 — Filter & score.** FAISS recall → hard filters → honeypot
   detection (overlapping timelines, fabricated seniority, off-domain titles) →
   a bounded, transparent `final_score` with behavioral multipliers
   (consulting-lifer, job-hopper, notice-period decay, engagement boost) and
   deterministic tie-breaks.
3. **Phase 3 — Reasoning.** An AST templating engine generates the `reasoning`
   column with **zero hallucination by construction** — every clause binds to a
   present, non-null source field and is fail-closed validated.

## Output contract

`team_vibecoder.csv` — exactly 100 rows, schema
`candidate_id,rank,score,reasoning`, scores monotonic non-increasing in `[0,1]`,
unique ids, and 100% grounded reasoning. The submission is **deterministic**
(byte-reproducible across runs).

## Run

```bash
# Phase 1 — precompute artifacts (offline, one-time)
python engine/phase1_precompute.py

# Phase 2/3 — rank + reason, write the submission CSV
python engine/phase2_ranker.py \
  --artifacts engine/data --jd-file job_description.docx \
  --out team_vibecoder.csv

# Validate the submission
python engine/validate_submission.py team_vibecoder.csv \
  --artifacts engine/data --jd-file job_description.docx
```

A live dashboard for browsing the ranked results is available via Streamlit:

```bash
streamlit run app.py
```

## Project layout

- `engine/` — the Python ranking engine (precompute, ranker, reasoning,
  validator, CLI runner).
- `app.py` — Streamlit dashboard for the ranked results.
- `team_vibecoder.csv` — the graded Top-100 submission.
- `job_description.docx` — the runtime job description input.
- Architecture docs (source of truth): `PRD.md`, `TechSpec.md`, `AppFlow.md`,
  `Design.md`, `Schema.md`, `Rules.md`.

## Guardrails

The engine obeys the invariants in `Rules.md` (R1–R10) — CPU-only, no network at
rank time, deterministic output, grounded reasoning, fail-loud on bad data, and
mandatory behavioral penalties. `Rules.md` takes precedence over every other
document.
