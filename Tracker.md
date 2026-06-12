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
- [x] **P2-1** Lazy record loader (seek → readline → parse one record; reads `manifest.plain_jsonl`).
- [x] **P2-2** Pass 1 FAISS search wrapper (JD → top-1000 ids + sem_score via `id_map`).
- [x] **P2-3** Honeypot detector: overlapping timeline, fake expert, title mismatch (immediate Tier 0).
- [ ] **P2-4** Hard filters (required skills, absolute ceilings). _(deferred — needs real JD/schema)_
- [ ] **P2-5** 23-signal normalization module. _(deferred — current scoring uses the request's subset)_
- [x] **P2-6** `final_score` scoring (consulting-lifer ×0.1, job-hopper ×0.5, notice decay, engagement boost); deterministic tie-breaks (final↓, sem↓, id↑).
- [x] **P2-7** Central config block (K, consulting set, thresholds, multipliers) — no magic numbers.

### Phase 3 — AST Reasoning
- [x] **P3-1** AST node types (`Lit`/`Field`/`Skills` leaves, `Seq`/`Choice` composites).
- [x] **P3-2** Leaf binding rule: render only on present, non-null fields; prune otherwise.
- [x] **P3-3** Rank-tiered tone + concern clauses + ≤240-char surface form (`Design.md` §2).
- [x] **P3-4** Skill clauses restricted to candidate's own skills (matched-against-JD subset).
- [x] **P3-5** Fail-closed grounding validator (rejects `{}` or any number not in the record).

### Phase 4 — Sandbox & Submission
- [ ] **P4-4** NDCG@10 + MAP eval script (blocked: synthetic mock data has no relevance labels).
- [ ] **P4-6** Threshold/weight tuning vs metrics; re-run; record benchmark report. (blocked on P4-4 labels.)

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
- [x] **P4-1** CLI entrypoint (`engine/run_ranker.py`) wiring Stage 0 mock-gen → Stage 1 precompute
  → Stage 2/3 rank+reasoning → `team_xxx.csv` + timestamped terminal log + resource profile.
- [x] **P4-3** Output integrity + VERDICT block (row count, schema, monotonic `score`, dup-id guard,
  Top5/Bottom5 preview); validated on smoke runs (200/600/1k records).
- [x] **P4-5** Network air-gap for the ranking stage (`network_air_gap` monkeypatches
  socket.connect/create_connection allowing only loopback; `HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE`;
  `prove_isolation()` probe) — `--network-off` / `NETWORK_OFF=1`; smoke-tested offline.
- [x] **X-2** `within_budget` VERDICT (RAM/ranking-wall/total thresholds) in the CLI.
- [x] **P4-ENG** Multi-core embedding made robust: resumable shard pool (per-shard `.npy`/`.json`
  + `.ok` stale-artifact marker, skip-completed) + retry-on-OOM; validated byte-identical to
  single-process (vectors diff 0.0).
- [x] **P4-2** Full 100k run COMPLETE (rich mock ~412MB, 9 shards, workers=1): **ranking wall-clock
  = 4.34s** (hard ≤5min budget → PASS), parent peak RAM 405MB / embedder ~3GB (well under 16GB).
  Offline precompute = 3989s (~66min) single-core under this 8GB+contended sandbox; far faster on
  the 16GB grader. Output `engine/data/team_xxx.csv`: 100 rows, schema `candidate_id,rank,score,
  reasoning`, scores monotonic (1.586→1.219), no dup ids, reasoning 100% populated + rank-tiered.

---

## Milestones

| Milestone | Depends on | Done when |
|-----------|-----------|-----------|
| M1: Artifacts ready | P1-1…P1-5 | Phase 1 exit criteria pass |
| M2: Re-ranker working | M1, P2-1…P2-7 | Top-100 produced (no reasoning) |
| M3: Reasoning grounded | M2, P3-1…P3-5 | All reasoning passes validator |
| M4: Submission-ready | M3, P4-1…P4-6 | ≤300s/≤16GB/no-net + valid CSV + metrics |
