# Rules.md — Unbreakable System Guardrails

**Project:** Redrob Rank Engine — Track 1
**Companion docs:** `PRD.md`, `TechSpec.md`, `AppFlow.md`, `Design.md`, `Schema.md`

These are **invariants**. Any code change that violates one is a defect, regardless of metric
impact. Each rule is stated, justified, and made testable.

---

## R1 — Never load the entire JSONL into memory at once

- **Rule:** the engine MUST NOT read all 100,000 records (≈465MB) into memory simultaneously.
  Offline precompute streams the file **line-by-line**; runtime accesses records via byte-offset
  **lazy seeks** for the ~1,000 Pass-2 candidates only (`TechSpec.md` §5, `Schema.md` §1).
- **Why:** the 16GB ceiling and the need to keep the pipeline fast; parsed Python objects for
  100k rich records would balloon well past the raw 465MB.
- **Test:** peak RSS during a full run stays far below 16GB (target ≤4GB); a code grep shows no
  `f.read()`/`json.load(f)` over the whole file and no list comprehension that materializes all
  lines.

## R2 — Never hallucinate skills or facts in the `reasoning` column

- **Rule:** every clause/token in `reasoning` MUST be backed by a present, non-null field of that
  candidate's record. Skill mentions come only from the candidate's own `skills`/matched skills.
  No invented skills, employers, numbers, or generic filler. Built via the AST engine whose
  leaves prune on missing data (`TechSpec.md` §7, `Design.md` §2).
- **Why:** Stage 4 is a manual truthfulness review; a single fabricated fact discredits the whole
  output and the team.
- **Test:** the reasoning traceability validator (Phase 3) asserts every output token maps to a
  source field; it fails-closed (no CSV emitted) on any ungrounded token.

## R3 — Aggressively penalize job hoppers and strictly consulting-only profiles

- **Rule:** scoring MUST apply mandatory penalties for (a) **job hoppers** — low
  `avg_tenure_months` and/or high `job_changes_last_3y`; and (b) **consulting-only** profiles —
  high `consulting_ratio` with no permanent/product roles, per the JD biases (`TechSpec.md` §6,
  `Schema.md` §3,§5).
- **Why:** the JD explicitly disfavors these patterns; ignoring them tanks NDCG@10 against the
  intended relevance judgments.
- **Test:** with all else equal, a high-hop / consulting-only candidate scores strictly lower
  than an equivalent stable / product candidate; penalties are logged in DEBUG (`Design.md` §3.2).

## R4 — Honeypot profiles MUST be detected and dropped

- **Rule:** any candidate tripping a honeypot heuristic (`Schema.md` §4) is removed in Stage C
  and can never appear in the output CSV. Each drop is logged with a reason token.
- **Why:** the dataset is adversarially seeded; admitting traps poisons NDCG@10/MAP.
- **Test:** no output `candidate_id` is honeypot-flagged; seeded/labeled traps in tests are all
  dropped; drop count + reasons appear in the log.

## R5 — No external network or API calls during ranking

- **Rule:** the ranking runtime MUST make **zero** network calls (no OpenAI/Claude/HTTP/DNS).
  All model inference (embeddings) is offline (`TechSpec.md` §2). Model weights and artifacts are
  read from local disk only.
- **Why:** hard hackathon constraint; also guarantees the 5-minute budget isn't blown by I/O.
- **Test:** a run with networking disabled produces identical output; no network client libs are
  imported in the runtime path.

## R6 — Stay within the 5-minute / 16GB budget

- **Rule:** end-to-end wall-clock ≤ 300 s and peak RAM ≤ 16 GB on CPU. The final log line MUST
  report totals and a `within_budget=YES/NO` verdict; a breach exits non-zero (`Design.md` §3.3).
- **Why:** out-of-budget submissions are invalid.
- **Test:** Phase-4 benchmark records both numbers under the caps; CI fails on `within_budget=NO`.

## R7 — Deterministic, reproducible output

- **Rule:** no randomness anywhere in ranking. Same inputs (artifacts + JD) ⇒ byte-identical
  `team_xxx.csv`. Ties broken by `sem_score` desc, then ascending `candidate_id`
  (`TechSpec.md` §6, `Design.md` §1.2).
- **Why:** reproducibility for evaluation and debugging; avoids flaky scores.
- **Test:** two consecutive runs produce identical CSVs (diff is empty).

## R8 — Respect the two-pass funnel boundaries

- **Rule:** Pass 1 touches **only** vectors + integer IDs (never JSON/metadata). Expensive
  per-record work (parse, signals, honeypot, reasoning) happens **only** in Pass 2 on the
  ~K=1000 recall set. K is a single documented constant (`TechSpec.md` §3).
- **Why:** this boundary is what keeps the engine inside the time/memory budget while maximizing
  semantic recall before precision re-ranking.
- **Test:** Pass-1 code imports no JSON/record loader; per-record parsing count ≈ K, not N.

## R9 — Output contract is exact

- **Rule:** `team_xxx.csv` MUST have header `candidate_id,rank,score,reasoning`, exactly 100
  unique rows, contiguous ranks 1–100, `score` non-increasing with rank, valid CSV quoting
  (`Design.md` §1).
- **Why:** the evaluation harness parses this format; any deviation can zero the submission.
- **Test:** the Phase-4 integrity checker validates schema, counts, uniqueness, and monotonicity.

## R10 — Fail loud, never fake

- **Rule:** on unrecoverable error (missing artifacts, <100 valid candidates after documented
  fallback, validator failure) the engine logs a clear error and exits non-zero. It MUST NOT emit
  placeholder rows, padded fake candidates, or silent fallbacks.
- **Why:** silent fabrication violates R2 and produces an untrustworthy, likely-disqualified file.
- **Test:** corrupting an artifact yields a non-zero exit + explanatory log, not a partial CSV.

---

**Precedence:** if any other document or future request conflicts with these guardrails, these
rules win. Changing a rule requires updating this file and the affected companion docs together.
