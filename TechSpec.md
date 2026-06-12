# TechSpec.md — Technical Specification

**Project:** Redrob Rank Engine — Track 1
**Companion docs:** `PRD.md`, `AppFlow.md`, `Schema.md`, `Design.md`, `Rules.md`

---

## 1. Design Thesis: A Strict Two-Pass Pipeline

We cannot run rich rule logic, lazy JSON parsing, and reasoning generation over 100,000
records in 5 minutes. We also cannot hold 465MB of parsed Python objects in RAM safely. The
solution is a **two-pass funnel**:

```
100,000 candidates
      │   PASS 1 — cheap, vectorized, integer-ID only (semantic recall)
      ▼
   ~1,000 candidates  (Top-K from FAISS)
      │   PASS 2 — expensive, per-record, lazy JSON metadata (precision re-rank)
      ▼
     100 candidates  →  team_xxx.csv
```

**Why two passes:** Pass 1 is O(N) but each op is a single dot-product over a 384-dim vector —
trivially fast and tiny in memory. Pass 2 is expensive (JSON parse, 23-signal math, honeypot
checks, AST reasoning) but only runs on ~1,000 records, not 100,000. This keeps both the time
and memory budgets comfortably met while maximizing NDCG@10 (semantic recall first, behavioral
precision second).

---

## 2. Offline Pre-computation (Phase 1, not counted against the 5-min runtime)

Embeddings are computed **once, offline**, never at ranking time (no-network rule, `Rules.md` §R5).

- **Model:** `sentence-transformers/all-MiniLM-L6-v2` (384-dim, CPU-friendly, ~80MB). Documented
  as the default; alternatives (e5-small-v2, bge-small-en) listed as drop-in options. Final
  model choice is a Phase-1 deliverable, not fixed here.
- **Text construction per candidate:** concatenate the narrative fields (summary + experience
  titles/descriptions + project blurbs + normalized skills) into one document, truncated to the
  model's max sequence length. The exact field list is in `Schema.md`.
- **Normalization:** L2-normalize each embedding so that inner product == cosine similarity.
- **Artifacts written to disk:**
  1. `embeddings.f32` — `(N, 384)` float32 matrix (≈153MB for N=100k).
  2. `id_map.npy` — `int64[N]`, mapping FAISS row index → `candidate_id`.
  3. `faiss.index` — a serialized FAISS index built over `embeddings.f32`.
  4. `offsets.idx` — byte-offset table `candidate_id → (byte_offset, byte_length)` into the
     original JSONL, enabling O(1) lazy seeks in Pass 2 (see §5).

> The JD embedding can be precomputed too, or computed once at startup (single forward pass,
> negligible cost, no network — the model weights are on disk).

---

## 3. Pass 1 — Fast Local FAISS Vector Search (integer IDs only)

**Input:** `faiss.index`, `id_map.npy`, the JD embedding `q` (384-dim, L2-normalized).
**Output:** `top1000_ids: int64[1000]` plus their cosine scores `sem_score ∈ [-1, 1]`.

- **Index type:** `IndexFlatIP` (exact inner-product brute force). For N=100k × 384-dim this is
  a single ~153MB matrix-vector product — milliseconds on CPU and *exact* (no recall loss).
  If profiling demands more speed, fall back to `IndexHNSWFlat` (approximate, faster, slightly
  lower recall) — documented as an option, default is Flat for maximum recall.
- **Critical rule:** Pass 1 touches **only** vectors and integer IDs. It never opens the JSONL,
  never parses metadata, never allocates per-candidate Python objects. This is what keeps Pass 1
  O(N) in time and ~O(1) in incremental memory.
- **K selection:** `K = 1000` (10× the output size). Large enough to not drop relevant
  candidates before precision re-ranking; small enough that Pass 2 stays cheap. K is a tunable
  constant documented in `Rules.md` §R8.

---

## 4. Pass 2 — Lazy Metadata Load + Rule-Based Re-rank (Top ~1000 only)

For each of the ~1,000 candidate IDs from Pass 1, in order:

1. **Lazy load** the single JSON record via byte-offset seek (§5). Parse it, use it, discard it.
   Never accumulate all 1,000 raw records if it can be avoided; keep only the small scored tuple.
2. **Honeypot elimination** — run the trap-detection checks from `Schema.md`. If flagged,
   **drop** the candidate entirely (it can never reach the output). Logged with the trip reason.
3. **Hard filters** — disqualify on non-negotiable JD gates (e.g. missing a required hard skill,
   `notice_period_days` above an absolute ceiling). Dropped candidates are logged.
4. **Behavioral multiplier scoring** — compute `final_score` (§6).
5. Keep `(candidate_id, final_score, score_components)` in a bounded max-heap of size 100.

**Output:** Top 100 by `final_score`, ready for AST reasoning + CSV emission.

---

## 5. Lazy Loading via Byte-Offset Index (the anti-OOM mechanism)

This is the concrete enforcement of `Rules.md` §R1 ("never load the whole JSONL into memory").

- **Build (offline / Phase 1):** stream the JSONL **line by line**, tracking the running byte
  offset and length of each line, and read just enough of each line to extract `candidate_id`.
  Write `offsets.idx` = `{candidate_id: (offset, length)}`. Memory cost ≈ the offset table only
  (a few MB), never the records.
- **Use (Pass 2):** for each needed `candidate_id`, `file.seek(offset)`, `file.read(length)`,
  `json.loads(...)`. Random access to exactly the ~1,000 records we need; the other ~99,000 are
  never parsed.
- This makes Pass 2 metadata cost proportional to **K (1,000)**, not **N (100,000)**.

---

## 6. Scoring Math (Behavioral Multipliers)

`final_score` is a bounded, transparent composite. All component weights live in one config
block (see `ImplementationPlan.md` Phase 2) so they are tunable and auditable.

```
base        = semantic_fit          # rescaled cosine from Pass 1, mapped to [0, 1]
behavioral  = Σ_i ( w_i * norm(signal_i) )   over the 23 redrob_signals   # → [0, 1]
penalty     = job_hopper_penalty + consulting_only_penalty + other_bias_penalties  # ≥ 0
bonus       = referral/endorsement/freshness bonuses                               # ≥ 0

raw_score   = (α * base) + (β * behavioral) + bonus - penalty
final_score = clamp(raw_score, 0.0, 1.0)        # then formatted per Design.md
```

- **`α`, `β`** balance semantic fit vs behavioral fit (default α=0.6, β=0.4; tunable).
- **`norm(signal_i)`** maps each raw signal to `[0,1]` with the per-signal direction and
  normalization defined in `Schema.md` (e.g. higher `recruiter_response_rate` is better; lower
  `notice_period_days` is better).
- **JD-bias penalties (mandatory, per `Rules.md` §R3):**
  - **Job hopper:** triggered by short `avg_tenure_months` and/or high `job_changes_last_3y`.
    Penalty scales with severity.
  - **Consulting-only:** triggered by high `consulting_ratio` with no permanent/product roles.
    Penalty scales with severity.
- Determinism: no randomness anywhere. Same input ⇒ same output (`Rules.md` §R7). Ties broken by
  `sem_score`, then by ascending `candidate_id`.

---

## 7. AST Reasoning Generation (Zero-Hallucination)

For each of the final 100 candidates, build the `reasoning` string from an **AST of template
nodes**:

- **Leaf nodes** bind to a single concrete field (e.g. `years_experience`, `notice_period_days`,
  a matched skill from the candidate's own skill list, a `redrob_signal` value).
- **A leaf renders only if its bound field is present and non-null.** Missing data ⇒ the node is
  pruned, never fabricated. This is the structural guarantee behind `Rules.md` §R2.
- **Composite nodes** order and join rendered leaves into a fluent, bounded-length sentence
  (e.g. "Strong semantic match (0.81); 8y backend incl. Go, Kafka; notice 15d;
  recruiter_response_rate 0.92.").
- The reasoning never references skills the candidate does not list, and never invents signal
  values. Every token is traceable to the source record. Format details in `Design.md`.

---

## 8. Time & Memory Budget (runtime, ≤300s / ≤16GB)

| Stage | Work | Time budget | Peak incremental memory |
|------|------|-------------|--------------------------|
| Startup | load FAISS index, id_map, JD embed | ~15–30 s | ~200 MB (index) |
| Pass 1 | FAISS top-1000 search | < 10 s | negligible |
| Pass 2 ingest | 1,000 lazy JSON seeks + parse | ~20–40 s | ~tens of MB (one record at a time) |
| Honeypot + hard filters | per-record checks on 1,000 | < 10 s | negligible |
| Scoring | 23-signal math on ≤1,000 | < 5 s | negligible |
| AST reasoning | 100 strings | < 5 s | negligible |
| CSV write | 100 rows | < 1 s | negligible |
| **Total** | | **≈ < 90 s typical, hard cap 300 s** | **design target ≤ 4 GB** |

Comfortable margin against both the 5-minute and 16GB ceilings. Phase 4 (`ImplementationPlan.md`)
validates these numbers in a local sandbox.

---

## 9. Tech Stack

- **Language:** Python 3.11+ (stdlib `json`, `csv`, `mmap`/`seek`, `heapq`).
- **Vectors/ANN:** `numpy`, `faiss-cpu`.
- **Embeddings (offline only):** `sentence-transformers` (or ONNX export for speed).
- **No** runtime web/LLM client. **No** database. Pure local files in/out.

See `AppFlow.md` for how these stages connect, and `Rules.md` for the invariants every stage
must honor.
