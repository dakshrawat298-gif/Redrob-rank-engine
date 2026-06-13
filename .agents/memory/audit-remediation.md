---
name: Audit remediation verdicts (Redrob Rank Engine)
description: How external audit findings were vetted against real data; which were false; the trap-keyword skill-match rule.
---

# Auditing the audit

An external (NotebookLM) architectural audit flagged 7 "critical" findings. Two were
**wrong** and would have regressed working features if applied verbatim. Always verify
a finding against the real dataset + actual code before changing anything.

**Rule:** treat audit findings as hypotheses, not facts. Grep the real data first.

- **github field rename = REJECTED.** Audit said rename `github_activity_score` →
  `github_contribution_score`. Real data: `github_activity_score` in 2000/2000 sampled,
  `github_contribution_score` in 0. Renaming would null the signal for every candidate.
- **Job-hopper "flag never surfaces" = MISDIAGNOSED.** `hopper_fired` is computed
  independently of the 0.5× score multiplier and passed straight to reasoning, so the
  honest concern already appears for any surviving hopper. The penalty only affects who
  makes the cut — exactly what R3 wants. No bug.

## Trap-keyword skill matching (real defect, highest value)
`match_skills` had two bugs, both fixed:
1. **Substring matching** (`skill.lower() in jd_lower`) falsely matched "Go"/"Rust"
   inside "category"/"robust". Fix: whole-word regex
   `(?<![a-z0-9])<skill>(?![a-z0-9])` (handles "C++" etc. via re.escape).
2. **Trap keywords**: the JD literally contains "marketing" and "hr-tech", and the JD
   text explicitly calls keyword-matching a built-in trap. A candidate's own
   "Marketing"/"HR" skill must never surface as a positive match for an AI-eng role.
   Fix: a `SKILL_DENY_LIST` constant filtered out before reasoning.

**Why:** R2 (no misleading/hallucinated reasoning). Surfacing a trap keyword as a
"match" is the exact failure mode the dataset was built to punish. The deny-list is
JD-archetype-specific by design.

## Score [0,1] normalization
Raw final score = cosine × multiplier (engagement ∈ [1,2]) can exceed 1.0 (saw
1.169932). R9 only requires non-increasing, but as a precaution scores are rescaled
`max(raw,0)/max_raw` AFTER the deterministic sort — order-preserving, rank-1 = 1.0.
Prefer this over `min(raw,1.0)` clamp (which collapses the top tier into 1.0 ties).
The submission validator also fail-closes on any score outside [0,1].
