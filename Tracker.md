# Tracker.md — Kanban Board

**Project:** Redrob Rank Engine — Track 1
**Companion docs:** `ImplementationPlan.md`, `Rules.md`

Atomic, checkable tasks grouped by status. Each task is tagged with its phase (P1–P4) and a
short id. Move a card across columns as work progresses. Definition of Done = the relevant
**exit criteria** in `ImplementationPlan.md` are met.

Legend: `[ ]` not started · `[~]` in progress · `[x]` done.

---

## To-Do

### Phase 1 — Pre-computation
- [x] **P1-1** Stream JSONL (binary, line-by-line), build `byte_offset_index.json` per `candidate_id` without full load.
- [ ] **P1-2** Reconcile real input schema vs `Schema.md` (fields + 23 signals); update doc if needed. _(pending real dataset)_
- [x] **P1-3** Build per-candidate embedding text from `current_title` + `skills` + `experience_summary`.
- [x] **P1-4** Embed via fastembed (all-MiniLM-L6-v2, 384-dim, ONNX/CPU) + L2-normalize; write `id_map.json`.
- [x] **P1-5** Build + serialize `candidate_embeddings.faiss` (`IndexFlatIP`); write `manifest.json`.

### Phase 2 — Filters & Scoring
- [ ] **P2-1** Lazy record loader (seek → read → parse one record).
- [ ] **P2-2** Pass 1 FAISS search wrapper (q → top-1000 ids + sem_score).
- [ ] **P2-3** Honeypot detector: implement all trip reasons from `Schema.md` §4.
- [ ] **P2-4** Hard filters (required skills, absolute ceilings).
- [ ] **P2-5** 23-signal normalization module.
- [ ] **P2-6** `final_score` scoring incl. job-hopper + consulting-only penalties; deterministic tie-breaks.
- [ ] **P2-7** Central config block (weights, K, thresholds) — no magic numbers.

### Phase 3 — AST Reasoning
- [ ] **P3-1** AST node types (leaf / composite / root).
- [ ] **P3-2** Leaf binding rule: render only on present, non-null fields; prune otherwise.
- [ ] **P3-3** Clause ordering + ≤240-char surface form (`Design.md` §2).
- [ ] **P3-4** Skill clauses restricted to candidate's own skills.
- [ ] **P3-5** Reasoning traceability validator (fail-closed on any ungrounded token).

### Phase 4 — Sandbox & Submission
- [ ] **P4-1** CLI entrypoint wiring Stages A–F → `team_xxx.csv` + terminal log.
- [ ] **P4-2** Full 100k run; capture wall-clock + peak RAM.
- [ ] **P4-3** Output integrity checks (100 rows, schema, monotonic score, no honeypots, no dup ids).
- [ ] **P4-4** NDCG@10 + MAP eval script (when labels available).
- [ ] **P4-5** Network-isolation run (prove zero API calls).
- [ ] **P4-6** Threshold/weight tuning vs metrics; re-run; record benchmark report.

### Cross-cutting
- [ ] **X-1** Enforce `Rules.md` guardrails in code review checklist.
- [ ] **X-2** `within_budget=YES/NO` verdict + non-zero exit on breach.
- [ ] **X-3** `README` / run instructions for the final CLI.

---

## In Progress

- [~] **P1-2** Schema reconciliation — blocked until the real `candidates.jsonl(.gz)` arrives;
  field names are isolated as constants (`TEXT_FIELDS`, `ID_FIELD`) for a one-line change.

---

## Complete

- [x] **DOC-0** Architecture foundation: 8 planning docs (`PRD`, `TechSpec`, `AppFlow`, `Design`,
  `Schema`, `ImplementationPlan`, `Tracker`, `Rules`) drafted for review.

---

## Milestones

| Milestone | Depends on | Done when |
|-----------|-----------|-----------|
| M1: Artifacts ready | P1-1…P1-5 | Phase 1 exit criteria pass |
| M2: Re-ranker working | M1, P2-1…P2-7 | Top-100 produced (no reasoning) |
| M3: Reasoning grounded | M2, P3-1…P3-5 | All reasoning passes validator |
| M4: Submission-ready | M3, P4-1…P4-6 | ≤300s/≤16GB/no-net + valid CSV + metrics |
