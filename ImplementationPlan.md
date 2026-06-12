# ImplementationPlan.md — Phased Delivery Plan

**Project:** Redrob Rank Engine — Track 1
**Companion docs:** `TechSpec.md`, `Schema.md`, `Design.md`, `Rules.md`, `Tracker.md`

Four phases. Each lists deliverables, the work, and **exit criteria** that must pass before the
next phase starts. Everything is sized to the **≤300s / ≤16GB / no-network** envelope (`PRD.md`).

---

## Phase 1 — Pre-computation of Embeddings (offline)

**Goal:** turn the 465MB JSONL into compact, query-ready disk artifacts so runtime never touches
the model or the network.

**Work:**
1. Stream `candidates.jsonl` line-by-line; build `offsets.idx` (`candidate_id → byte offset/len`)
   without loading the file into memory (`Schema.md` §1, `Rules.md` §R1).
2. Confirm the real input schema against `Schema.md` (field names, the 23 signals); reconcile any
   differences in `Schema.md`.
3. Build per-candidate embedding text (`Schema.md` §2 / `TechSpec.md` §2); finalize the embedding
   model (default `all-MiniLM-L6-v2`); record the choice + dims.
4. Compute and L2-normalize embeddings → `embeddings.f32`; write `id_map.npy`.
5. Build and serialize `faiss.index` (`IndexFlatIP`).

**Deliverables:** `offsets.idx`, `embeddings.f32`, `id_map.npy`, `faiss.index`, a short
`precompute.py`, and a recorded artifact manifest (model, dims, N, checksums).

**Exit criteria:**
- All four artifacts exist; `N == 100000`; embedding dim consistent across artifacts.
- Peak RAM during precompute stays bounded (streamed, not full-load).
- Round-trip check: a random `candidate_id` lazy-seeks to the correct record via `offsets.idx`.

---

## Phase 2 — Hard-Filter Logic & Scoring Math

**Goal:** the precision re-ranker (Pass 2) minus reasoning text.

**Work:**
1. Lazy record loader (seek/read/parse one record) used by Stages C–E.
2. Honeypot detector implementing every trip in `Schema.md` §4, each returning a reason token.
3. Hard filters (required skills, absolute ceilings) — `AppFlow.md` Stage C2.
4. Signal normalization for all 23 signals (`Schema.md` §3) in one auditable module.
5. Scoring function `final_score` (`TechSpec.md` §6) incl. mandatory job-hopper and
   consulting-only penalties (`Rules.md` §R3); deterministic tie-breaks (`Rules.md` §R7).
6. Single **config block** for all weights/thresholds (`α, β`, K, penalty coeffs, honeypot
   thresholds) — no magic numbers scattered in code.

**Deliverables:** `pass1_search`, `honeypot`, `filters`, `signals`, `scoring`, `config`.

**Exit criteria:**
- On a small sampled subset, FAISS top-K + scoring runs end-to-end and produces a Top-100 by
  `final_score` (no reasoning yet).
- Honeypots in any labeled/seeded sample are dropped; drops are logged with reasons.
- Scoring is deterministic across repeated runs (identical ordering).

---

## Phase 3 — AST Templating Engine (Zero-Hallucination Reasoning)

**Goal:** the `reasoning` column, structurally guaranteed truthful.

**Work:**
1. Define AST node types: leaf (binds to one field), composite (orders/joins), root (sentence).
2. Leaf binding rule: render only if the bound field is present & non-null; else prune
   (`TechSpec.md` §7, `Rules.md` §R2).
3. Clause order + ≤240-char surface form per `Design.md` §2.
4. Skill clauses pull **only** from the candidate's own `skills`/matched skills — never JD skills
   the candidate lacks.
5. Validator: assert every token in the output reasoning is traceable to a source field
   (fail-closed if not).

**Deliverables:** `ast_reasoning` module + `reasoning_validator`.

**Exit criteria:**
- For 100 sample candidates, every reasoning string passes the traceability validator.
- Removing a field from a record removes exactly its clause (no fabrication).
- All strings ≤ 240 chars, single line, CSV-safe.

---

## Phase 4 — Local Sandbox 5-Minute Execution Testing

**Goal:** prove the full pipeline meets every operational constraint on the real 100k dataset.

**Work:**
1. Wire Stages A–F into one CLI entrypoint that emits `team_xxx.csv` + the terminal log
   (`Design.md` §3).
2. Full run on all 100,000 records; capture wall-clock and peak RAM.
3. Verify output integrity: exactly 100 rows, schema correct, ranks contiguous, scores
   monotonic, no honeypots, no dup ids (`Design.md` §1.2).
4. Compute NDCG@10 and MAP if ground-truth labels are available; log them.
5. Network-isolation check (run with networking disabled) to prove the no-API rule.
6. Tune config thresholds (K, penalties, honeypot cutoffs) against metrics; re-run.

**Deliverables:** `run.py` (CLI), an eval script (`ndcg/map`), and a recorded benchmark report.

**Exit criteria (submission-ready):**
- End-to-end ≤ 300 s, peak RAM ≤ 16 GB (target ≤ 4 GB), **zero** network calls.
- `team_xxx.csv` passes all integrity checks in `Design.md`.
- `within_budget=YES` printed; process exits 0.
- NDCG@10 / MAP recorded (where labels exist) and trending up vs. baseline.

---

## Sequencing & Risk

- Phases run in order; Phase 4 depends on 1–3. Phase 3 can begin once Phase 2's lazy loader and
  config exist.
- **Top risks:** (a) input schema differing from `Schema.md` → mitigated by the Phase-1
  reconciliation step; (b) honeypot false positives → mitigated by conservative multi-trip flags
  + Phase-4 tuning; (c) budget overrun → mitigated by the funnel + the `within_budget` gate.

See `Tracker.md` for the atomic task board derived from these phases.
