# PRD.md — Product Requirements Document

**Project:** Redrob Rank Engine
**Event:** Redrob "India Runs" Hackathon — Track 1: Intelligent Candidate Discovery
**Status:** Architecture foundation (pre-implementation)
**Owner:** Team `xxx`

---

## 1. Core Objective

Build a deterministic, CPU-only candidate ranking engine that ingests **100,000 synthetic
candidate profiles** (JSONL, ~465MB uncompressed), scores each candidate against a single
target Job Description (JD), and emits the **Top 100 candidates** as a ranked CSV
(`team_xxx.csv`) — all within **5 minutes wall-clock** on a machine with **≤16GB RAM** and
**no external network/API calls** during ranking.

The engine optimizes for three things simultaneously:

1. **Relevance** — surface the candidates a human recruiter would actually shortlist.
2. **Robustness** — refuse to be fooled by adversarial "Honeypot" profiles planted in the dataset.
3. **Trust** — every ranked candidate ships with a short, fully data-grounded `reasoning`
   string that a reviewer can verify line-by-line against the source record.

> **Non-goal:** This is not a generative chatbot or an LLM-at-inference system. The 5-minute /
> no-network budget makes runtime LLM calls impossible. All "intelligence" is pre-computed
> (embeddings) or rule-based (scoring + AST templating). See `TechSpec.md`.

---

## 2. Target Metrics

| Metric | Definition | Priority | Target |
|--------|-----------|----------|--------|
| **NDCG@10** | Normalized Discounted Cumulative Gain over the top 10 returned candidates. Rewards putting the most-relevant candidates highest. | **Primary** | Maximize |
| **MAP** | Mean Average Precision across the relevant set. Rewards overall ordering quality, not just the head. | **Secondary** | Maximize |
| **Stage 4 manual review** | Human review of code quality + reasoning-column truthfulness. Hallucinated or generic reasoning is penalized. | **Gate** | Zero hallucinations |

Operational metrics (must pass or the submission is invalid):

| Constraint metric | Budget |
|---|---|
| Wall-clock runtime | ≤ 300 s |
| Peak RAM | ≤ 16 GB (design target ≤ 4 GB) |
| External API calls during ranking | 0 |
| Output rows | exactly 100 |

NDCG@10 is the north star because the evaluation weights the **head** of the ranking most
heavily. Every design decision (FAISS recall → rule-based precision re-rank → behavioral
multipliers) is ordered to maximize the quality of the top 10–100 specifically. See
`TechSpec.md` §"Why two passes".

---

## 3. The Three Core Pillars

### Pillar 1 — Deep Semantic Fit

Move beyond keyword matching. A candidate who writes "shipped a fault-tolerant payments
ledger in Go" should rank for a "distributed systems / backend" JD even without the exact JD
keywords.

- **How:** pre-computed dense embeddings of each candidate's narrative text (summary,
  experience, project descriptions) compared against the JD embedding via cosine similarity.
- **Where:** Pass 1 (FAISS ANN search) produces the semantic recall set; the cosine score is
  also reused as the base term in Pass 2 scoring. See `TechSpec.md` §"Pass 1".
- **Why it wins:** semantic recall lifts genuinely-qualified candidates who use non-standard
  vocabulary into the candidate pool, directly improving NDCG@10/MAP recall before precision
  re-ranking.

### Pillar 2 — Behavioral Signal Multipliers

A great résumé is not a great hire. Redrob ships **23 `redrob_signals`** per candidate
(e.g. `recruiter_response_rate`, `notice_period_days`). These behavioral signals act as
**multipliers / penalties** on the semantic base score, encoding "will this person actually
engage, accept, and stay?"

- **How:** a transparent, bounded scoring function combines the semantic score with normalized
  behavioral signals and JD-bias penalties (job hoppers, consulting-only profiles). See
  `Schema.md` for the full 23-signal catalog and `TechSpec.md` §"Scoring math".
- **Why it wins:** behavioral re-ranking is what separates a paper-good list from a
  recruiter-grade shortlist, which is exactly what NDCG@10 rewards.

### Pillar 3 — Zero-Hallucination Explainability

Every output row carries a `reasoning` string. It must be **100% grounded** in the
candidate's actual data — no invented skills, no generic filler.

- **How:** reasoning is assembled by an **AST (Abstract Syntax Tree) templating engine** whose
  leaf nodes can only bind to fields that are present and non-null in the candidate record.
  If a fact isn't in the data, it cannot appear in the reasoning. See `TechSpec.md`
  §"AST reasoning" and `Rules.md` §R2.
- **Why it wins:** Stage 4 is a manual review. Verifiable, specific reasoning ("8y backend,
  notice 15d, recruiter_response_rate 0.92") beats fluent-but-unverifiable prose every time.

---

## 4. Users & Use Case

- **Primary user:** the hackathon evaluation harness (consumes `team_xxx.csv`).
- **Secondary user:** a human reviewer (Stage 4) reading the `reasoning` column and the code.
- **Tertiary user:** us, the developers, reading the terminal debug log (see `Design.md`).

---

## 5. Scope

**In scope (this engine):** ingestion, vectorization (offline), ANN recall, honeypot
elimination, behavioral scoring, AST reasoning, CSV emission, terminal logging.

**Out of scope:** any runtime LLM/API call; a UI; persistence to a database; multi-JD batch
mode (single JD per run); retraining embedding models at runtime.

---

## 6. Acceptance Criteria

1. `python -m redrob_rank ...` (final CLI) produces `team_xxx.csv` with exactly 100 rows and
   the schema in `Design.md`.
2. End-to-end run completes in ≤ 300 s on CPU with ≤ 16 GB RAM and zero network calls.
3. No candidate flagged as a Honeypot (per `Schema.md` criteria) appears in the output.
4. Every `reasoning` string is reconstructable from the source record (no hallucinated tokens).
5. NDCG@10 and MAP are computed and logged for any run that has ground-truth labels available.

---

## 7. Related Documents

- `TechSpec.md` — two-pass pipeline and scoring math
- `AppFlow.md` — end-to-end data flow
- `Design.md` — output CSV contract + logging interface
- `Schema.md` — input record + 23 signals + honeypot criteria
- `Rules.md` — unbreakable guardrails
