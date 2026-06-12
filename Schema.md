# Schema.md — Input Data & `redrob_signals` Catalog

**Project:** Redrob Rank Engine — Track 1
**Companion docs:** `TechSpec.md`, `AppFlow.md`, `Design.md`, `Rules.md`

This document defines the **input candidate record**, the **23 `redrob_signals`**, and the
**Honeypot detection criteria**. It is the source of truth for field names used across all docs.

---

## 1. Input File

- **Path:** `candidates.jsonl` (single JSON object per line, newline-delimited).
- **Size:** ~465MB uncompressed, **100,000 records**.
- **Access policy:** **NEVER** `json.load` the whole file. Stream it once to build the
  byte-offset index, then lazy-seek individual records in Pass 2 (`TechSpec.md` §5, `Rules.md` §R1).

---

## 2. Candidate Record Structure

Each line is a JSON object. Field names below are the canonical names used everywhere. Exact
field presence in the provided dataset will be confirmed in Phase 1; unknown/missing fields are
treated as null and handled per `AppFlow.md` §4 (neutral normalization, omitted from reasoning).

```jsonc
{
  "candidate_id": "C0098431",            // unique id; appears in output CSV
  "name": "…",                           // not used for scoring (avoid bias); not output
  "headline": "Senior Backend Engineer", // short title
  "summary": "…",                        // narrative — used for embedding (Pillar 1)
  "skills": ["go", "kafka", "postgresql", "grpc"],  // normalized skill tokens
  "years_experience": 9,                  // total professional years
  "experience": [                         // role history — used for embedding + tenure math
    {
      "title": "Staff Engineer",
      "company": "…",
      "employment_type": "full_time",     // full_time | contract | consulting | intern
      "start": "2019-06",
      "end": "2024-01",                   // null/"present" if current
      "description": "…"                  // narrative — used for embedding
    }
  ],
  "projects": [ { "name": "…", "description": "…" } ],  // narrative — used for embedding
  "education": [ { "degree": "…", "field": "…", "year": 2015 } ],
  "location": "Bengaluru, IN",
  "redrob_signals": {                     // 23 behavioral signals — see §3
    "recruiter_response_rate": 0.94,
    "notice_period_days": 15
    // … 21 more …
  }
}
```

**Embedding text (Pillar 1)** is built from: `headline + summary + experience[].title +
experience[].description + projects[].description + skills`. See `TechSpec.md` §2.

---

## 3. The 23 `redrob_signals`

Each signal has a **type**, a **direction** (does higher help or hurt?), a **normalization** to
`[0,1]`, and a **role** in scoring. `norm(x)` denotes the value after mapping to `[0,1]` in the
helpful direction (so 1.0 is always "best"). Exact min/max bounds and any clipping are finalized
in Phase 2 config; defaults are indicative.

| # | Signal | Type | Direction | Normalization (→[0,1], 1=best) | Role |
|---|--------|------|-----------|--------------------------------|------|
| 1 | `recruiter_response_rate` | float 0–1 | ↑ better | identity | engagement multiplier |
| 2 | `notice_period_days` | int days | ↓ better | `1 - clip(x/90)` | availability; hard-filter ceiling |
| 3 | `application_completion_rate` | float 0–1 | ↑ better | identity | intent multiplier |
| 4 | `profile_freshness_days` | int days | ↓ better | `1 - clip(x/180)` | freshness bonus |
| 5 | `avg_tenure_months` | float | ↑ better | `clip(x/48)` | **job-hopper** input |
| 6 | `job_changes_last_3y` | int | ↓ better | `1 - clip(x/6)` | **job-hopper** input |
| 7 | `consulting_ratio` | float 0–1 | ↓ better | `1 - x` | **consulting-only** input |
| 8 | `interview_show_up_rate` | float 0–1 | ↑ better | identity | reliability multiplier |
| 9 | `offer_acceptance_rate` | float 0–1 | ↑ better | identity | conversion multiplier |
| 10 | `backout_rate` | float 0–1 | ↓ better | `1 - x` | reliability penalty input |
| 11 | `ghosting_incidents` | int | ↓ better | `1 - clip(x/5)` | reliability penalty input |
| 12 | `response_latency_hours` | float | ↓ better | `1 - clip(x/72)` | engagement multiplier |
| 13 | `message_sentiment_score` | float -1–1 | ↑ better | `(x+1)/2` | soft-signal |
| 14 | `recruiter_rating_avg` | float 1–5 | ↑ better | `(x-1)/4` | quality multiplier |
| 15 | `skill_endorsement_count` | int | ↑ better | `clip(x/50)` | credibility bonus |
| 16 | `peer_endorsement_score` | float 0–1 | ↑ better | identity | credibility bonus |
| 17 | `referral_count` | int | ↑ better | `clip(x/5)` | trust bonus |
| 18 | `certifications_count` | int | ↑ better | `clip(x/5)` | credibility bonus |
| 19 | `github_contribution_score` | float 0–1 | ↑ better | identity | proof-of-work bonus |
| 20 | `open_source_commits` | int | ↑ better | `clip(log1p(x)/log1p(500))` | proof-of-work bonus |
| 21 | `salary_expectation_ratio` | float (exp/market) | ~1 best | `1 - clip(|x-1|)` | fit multiplier |
| 22 | `relocation_willingness` | float 0–1 / bool | ↑ better | identity (bool→0/1) | logistics multiplier |
| 23 | `remote_preference_match` | float 0–1 | ↑ better | identity | logistics multiplier |

`clip(v)` = `min(max(v,0),1)`. Signals 5–7 feed the mandatory JD-bias penalties (`Rules.md` §R3).
Missing signal ⇒ neutral `norm = 0.5` and **omitted** from `reasoning`.

---

## 4. Honeypot (Trap Profile) Detection

The dataset is seeded with **adversarial "Honeypot" profiles** — records engineered to look
perfect to a naive keyword/score system but that a real recruiter would never shortlist.
Detecting and **dropping** them (Stage C, `Rules.md` §R4) protects NDCG@10/MAP from poisoning.

A candidate is flagged if **any** trip fires. Each trip emits a machine-readable reason for the
log (`Design.md` §3.2).

| Trip reason (log token) | Heuristic | Rationale |
|---|---|---|
| `perfect_signal_vector` | All/most of the 23 signals at or near their max simultaneously (statistically implausible). | Real humans have trade-offs; all-perfect is synthetic. |
| `keyword_density` | Skill/keyword stuffing: skills list or summary repeats JD terms at abnormally high density vs. narrative length. | Gaming keyword match. |
| `semantic_outlier` | Embedding is a near-duplicate of many other records, or sits in a degenerate cluster (templated text). | Mass-produced trap text. |
| `timeline_impossible` | Sum of role durations ≫ `years_experience`; overlapping full-time roles; skill predates its real-world existence; `end` < `start`. | Fabricated history. |
| `contradictory_signals` | Logically incompatible pairs, e.g. `consulting_ratio≈1.0` **and** `avg_tenure_months` very high; `offer_acceptance_rate=1.0` **and** `backout_rate=1.0`. | Internally inconsistent synthetic data. |
| `degenerate_text` | Summary/experience nearly empty or boilerplate while signals are maxed. | "All signal, no substance" trap. |
| `dup_identity` | Exact-duplicate narrative across multiple candidate_ids. | Cloned trap records. |

- Thresholds are config constants (Phase 2), tuned in Phase 4 against any labeled traps.
- **Conservative bias:** prefer dropping a true trap over admitting one; but a single soft signal
  alone should not flag a genuine strong candidate — flags require the specific patterns above,
  and borderline cases are logged for review rather than silently kept.

---

## 5. JD-Side Inputs (for filters & penalties)

- **Required (hard) skills** — gate in Stage C2; absence ⇒ drop (`AppFlow.md`).
- **Preferred skills** — contribute to semantic/behavioral score, not a hard gate.
- **Absolute ceilings** — e.g. max acceptable `notice_period_days`.
- **JD biases (mandatory penalties)** — job hoppers (signals 5,6) and consulting-only profiles
  (signal 7), per `PRD.md` Pillar 2 and `Rules.md` §R3.
