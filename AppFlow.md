# AppFlow.md — Application & Data Flow

**Project:** Redrob Rank Engine — Track 1
**Companion docs:** `TechSpec.md`, `Schema.md`, `Design.md`, `Rules.md`

---

## 1. End-to-End Data Flow Diagram

```
                         ┌──────────────────────────────────────────────┐
   OFFLINE (Phase 1)     │  candidates.jsonl  (~465MB, 100,000 records)  │
   not in 5-min budget   └───────────────────────┬──────────────────────┘
                                                  │ stream line-by-line
                                                  ▼
                         ┌──────────────────────────────────────────────┐
                         │  PRE-COMPUTE                                   │
                         │  • build embeddings.f32  (N×384, L2-norm)      │
                         │  • build id_map.npy      (row → candidate_id)  │
                         │  • build faiss.index     (IndexFlatIP)         │
                         │  • build offsets.idx     (id → byte offset)    │
                         └───────────────────────┬──────────────────────┘
                                                  │
====================  R U N T I M E  (≤ 300s, ≤16GB, no network)  ===============
                                                  │
   [JD text] ──► JD embed (1 fwd pass) ──► q (384-dim, L2-norm)
                                                  │
        STAGE A — DATA STREAMING INGESTION        │
        load faiss.index + id_map + offsets.idx   │
                                                  ▼
        STAGE B — VECTORIZATION / SEMANTIC RECALL  (PASS 1)
        FAISS search(q, K=1000)  ──►  top1000_ids[] + sem_score[]
        (integer IDs ONLY — no JSON touched)
                                                  │
                                                  ▼   for each id (lazy seek → 1 JSON record)
        STAGE C — HONEYPOT ELIMINATION
        run trap checks (Schema.md) ─► DROP traps (logged)
                                                  │  survivors
                                                  ▼
        STAGE C2 — HARD FILTERS
        required-skill / absolute-ceiling gates ─► DROP fails (logged)
                                                  │  survivors
                                                  ▼
        STAGE D — BEHAVIORAL MULTIPLIER SCORING
        final_score = f(sem_score, 23 signals, penalties, bonuses)
        keep Top 100 in bounded heap
                                                  │
                                                  ▼
        STAGE E — AST REASONING GENERATION
        build grounded reasoning string per candidate (Top 100)
                                                  │
                                                  ▼
        STAGE F — FINAL 100-ROW CSV OUTPUT
        write team_xxx.csv  [candidate_id, rank, score, reasoning]
                                                  │
                                                  ▼
                              ┌───────────────────────────────┐
                              │  team_xxx.csv  (exactly 100)   │
                              └───────────────────────────────┘
```

---

## 2. Stage-by-Stage Contract

| Stage | Name | Input | Output | Reads JSONL? | Constraint enforced |
|------|------|-------|--------|--------------|---------------------|
| A | Data Streaming Ingestion | disk artifacts + JD | in-memory index, JD vector | offsets only (offline build streamed) | `Rules.md` §R1 (no full load) |
| B | Vectorization / Recall (Pass 1) | FAISS index, `q` | `top1000_ids`, `sem_score` | **No** (IDs + vectors only) | O(N) time, ~O(1) memory |
| C | Honeypot Elimination | 1,000 lazy records | survivor IDs | Yes (lazy, 1 at a time) | `Rules.md` §R4 (drop traps) |
| C2 | Hard Filters | survivors | filtered survivors | (reuses parsed record) | JD non-negotiables |
| D | Behavioral Multiplier Scoring | survivors + signals | Top-100 heap | (reuses parsed record) | `Rules.md` §R3 (bias penalties) |
| E | AST Reasoning Generation | Top 100 | grounded reasoning strings | (reuses parsed record) | `Rules.md` §R2 (no hallucination) |
| F | Final CSV Output | Top 100 + reasoning | `team_xxx.csv` | No | `Design.md` schema (exactly 100 rows) |

> Stages C → E operate on the **same** lazily-loaded record per candidate, so each of the ~1,000
> records is parsed **once**. The record is scored, optionally turned into reasoning, then
> released — never all buffered together as raw JSON.

---

## 3. Where Each Constraint Lives

- **No full-file load (≤16GB):** the byte-offset index (Stage A build) + Pass 1 working on
  vectors/IDs only (Stage B) + lazy per-record seeks (Stages C–E). See `TechSpec.md` §5.
- **≤ 300s wall-clock:** the funnel collapses 100k → 1k → 100, so the expensive per-record work
  runs ~1,000 times, not 100,000. Budget table in `TechSpec.md` §8.
- **No network:** all model inference is offline (embeddings on disk); runtime only reads local
  files. See `Rules.md` §R5.
- **Zero hallucination:** AST leaves bind only to present fields (Stage E). See `TechSpec.md` §7.
- **Determinism:** no randomness; stable tie-breaks. Same input ⇒ identical CSV. `Rules.md` §R7.

---

## 4. Failure & Edge Handling (flow level)

- **Fewer than 100 survivors after filtering:** widen K and re-run Pass 2 on the larger recall
  set (documented fallback); log the widening. Output must still contain exactly 100 rows if at
  all possible per `Design.md`.
- **Malformed JSON line on lazy seek:** skip the record, log a warning with `candidate_id`,
  continue. Never abort the whole run for one bad record.
- **Missing signal fields:** treated as "unknown" → neutral normalization, and that signal is
  simply omitted from the AST reasoning (never invented).

See `Design.md` for the exact terminal log lines emitted at each stage transition.
