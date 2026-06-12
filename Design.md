# Design.md — Output Contract & Logging Interface

**Project:** Redrob Rank Engine — Track 1
**Companion docs:** `TechSpec.md`, `AppFlow.md`, `Schema.md`, `Rules.md`

This document is the **source of truth** for the output file format and the terminal debug
interface. Any change here must be reflected in `AppFlow.md` Stage F and the CSV writer.

---

## 1. Output File: `team_xxx.csv`

- **Filename:** `team_xxx.csv`, where `xxx` is replaced by our assigned team number/id at submit
  time. The filename is the only place the team id appears.
- **Encoding:** UTF-8, no BOM.
- **Line endings:** `\n` (Unix).
- **Delimiter:** comma. Standard RFC-4180 quoting (fields containing `,`, `"`, or newlines are
  double-quoted; embedded quotes are doubled).
- **Header:** present, exactly: `candidate_id,rank,score,reasoning`
- **Row count:** **exactly 100** data rows (plus the 1 header row). No more, no fewer.

### 1.1 Column Schema

| # | Column | Type | Constraints |
|---|--------|------|-------------|
| 1 | `candidate_id` | string/int (as in source) | The candidate's original `candidate_id` from the JSONL. Must exist in the input. Unique across the 100 rows. |
| 2 | `rank` | integer | 1…100, **contiguous and unique**. `rank=1` is the best candidate. Strictly increasing down the file. |
| 3 | `score` | float | The `final_score` from `TechSpec.md` §6, in `[0.0, 1.0]`, formatted to **6 decimal places**. Monotonic with rank: a lower `rank` (better) always has a `score` ≥ the next row's. |
| 4 | `reasoning` | string | Grounded, human-readable explanation built by the AST engine (`TechSpec.md` §7). Single line. **Max 240 characters.** No invented skills or signal values. Properly CSV-quoted. |

### 1.2 Ordering & Integrity Rules

- Rows are sorted by `score` descending; `rank` is assigned 1…100 in that order.
- **Tie-breaking** (deterministic, per `Rules.md` §R7): equal `score` → higher `sem_score` first
  → then ascending `candidate_id`.
- No Honeypot-flagged candidate may appear (`Rules.md` §R4).
- No duplicate `candidate_id`.
- `score` is non-increasing as `rank` increases.

### 1.3 Example (illustrative values)

```csv
candidate_id,rank,score,reasoning
C0098431,1,0.913742,"Semantic fit 0.86; 9y backend incl. Go, Kafka, PostgreSQL; notice 15d; recruiter_response_rate 0.94; offer_acceptance_rate 0.88."
C0017265,2,0.901118,"Semantic fit 0.84; 7y distributed systems incl. Rust, gRPC; notice 30d; avg_tenure 34mo; referral_count 3."
C0042900,3,0.889305,"Semantic fit 0.82; 6y backend incl. Java, Spring; notice 45d; recruiter_response_rate 0.81; certifications 2."
...
```

> The `reasoning` text above is assembled **only** from fields that exist in each candidate's
> record. If a candidate has no certifications, the certifications clause is absent — never set
> to "0" implications or invented.

---

## 2. `reasoning` Composition Rules (output-side)

The AST engine (`TechSpec.md` §7, implemented in `engine/phase3_reasoning.py`) emits the string;
this section pins the surface form. **No LLM is used** — the text is assembled from a small AST of
template nodes whose leaves bind directly to the candidate's own JSON fields, so hallucination is
structurally impossible (`Rules.md` §R2).

- **One sentence-group, ≤ 240 chars, single line.**
- **Rank-tiered tone** (the Stage-4 rubric rewards tone that tracks rank):
  - **Ranks 1–20** — highly positive ("Exceptional fit …", "Top-tier match …").
  - **Ranks 21–80** — balanced ("Solid … background matching JD requirements …").
  - **Ranks 81–100** — explicit filler ("Adjacent skills only — likely below cutoff but included
    as final filler …").
  - 3–4 phrasings per tier, chosen **deterministically per `candidate_id`** (R7) for variation;
    a phrasing that would reference a missing field prunes and the next phrasing is used.
- **Grounded facts only** (a clause renders only when its backing field is present, non-null):
  experience years, current title, ≤3 **matched** skills (strictly from the candidate's own list,
  filtered to those present in the JD), and `github_contribution_score`.
- **Honest-concern clauses** (red flags are surfaced, not hidden — the rubric penalises missing
  risk). Appended after the main clause:
  - `notice_period_days > 30` → "; however, note the extended notice period of `<N>` days".
  - job-hopper penalty fired (avg tenure < 1.5y) → "; candidate shows frequent job transitions".
- **Never** include: skills not in the candidate's list; signal names with no value present;
  vague filler ("great candidate", "highly motivated"); the words "AI"/"LLM".
- **Fail-closed grounding check:** the output is rejected (and a minimal grounded fallback used) if
  it contains any unresolved `{}` placeholder or any number not traceable to the candidate's record.
- Numbers are rendered exactly as derived; no rounding that changes meaning beyond display.

> **Decision note (Phase 3):** an earlier draft forbade surfacing any "penalty internals" in the
> prose. That is reversed here: penalties still only affect `score`, but the *underlying red flags*
> (extended notice, frequent transitions) are stated as honest concerns because the Stage-4 manual
> review explicitly rewards disclosed risk. Tier-based tone replaces the fixed clause order of the
> earlier draft.

---

## 3. Terminal Logging / Debug Interface

A single structured, human-readable log stream to `stderr` (so `stdout`/CSV stays clean). Every
line is prefixed with an elapsed wall-clock timer to make the 5-minute budget visible at a
glance. Verbosity controlled by `--log-level {INFO,DEBUG}`.

### 3.1 Standard run (INFO)

```
[  0.00s] INFO  redrob-rank start | jd="Senior Backend Engineer (Distributed Systems)"
[  0.01s] INFO  loading artifacts: faiss.index, id_map.npy, offsets.idx
[ 12.84s] INFO  artifacts loaded | N=100000 dim=384 index=IndexFlatIP ram~210MB
[ 12.90s] INFO  JD embedded | dim=384
[ STAGE B] -------------------------------------------------------------
[ 20.31s] INFO  PASS1 faiss search done | K=1000 top_sim=0.8612 min_sim=0.5123
[ STAGE C] -------------------------------------------------------------
[ 41.07s] INFO  PASS2 lazy-loaded 1000 records | parse_errors=0
[ 42.55s] INFO  honeypot elimination | flagged=37 dropped=37
[ 43.10s] INFO  hard filters | dropped=58 (missing_required_skill=41 notice_ceiling=17)
[ STAGE D] -------------------------------------------------------------
[ 47.66s] INFO  scoring complete | survivors=905 kept_top=100
[ STAGE E] -------------------------------------------------------------
[ 49.02s] INFO  reasoning generated | rows=100 avg_len=176 max_len=233
[ STAGE F] -------------------------------------------------------------
[ 49.40s] INFO  wrote team_xxx.csv | rows=100
[ 49.41s] INFO  DONE | total=49.41s peak_ram~3.8GB within_budget=YES (limit 300s/16GB)
```

### 3.2 Per-candidate trace (DEBUG only)

```
[ DEBUG] cand C0098431 | sem=0.8601 base=0.860 behav=0.742 bonus=+0.031 penalty=-0.000 final=0.913742
[ DEBUG] cand C0031778 | HONEYPOT trip=perfect_signal_vector,keyword_density=0.71 → DROP
[ DEBUG] cand C0052213 | HARDFILTER missing_required_skill=[kubernetes] → DROP
[ DEBUG] cand C0007654 | PENALTY job_hopper(avg_tenure=9mo,changes=5)=-0.18 consulting_only(ratio=0.97)=-0.12
```

### 3.3 Logging requirements

- **Never** print full candidate records or PII-like blobs — only IDs, scores, and trip reasons.
- Every dropped candidate (honeypot or hard filter) is logged with a machine-readable reason.
- The final line MUST report total wall-clock and a `within_budget=YES/NO` verdict.
- If `within_budget=NO`, exit non-zero so the harness/CI catches a budget breach.
- Logging must add negligible overhead (buffered writes; DEBUG off by default).

See `Schema.md` for the honeypot trip-reason vocabulary referenced in the logs.
