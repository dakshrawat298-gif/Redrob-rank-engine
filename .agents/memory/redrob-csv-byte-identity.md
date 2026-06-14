---
name: Redrob CSV byte-identity gate
description: How to safely make non-behavioral changes to the Redrob Rank Engine without altering the submission CSV.
---

The submission `team_vibecoder.csv` is a hard deliverable that must stay
byte-identical across any non-behavioral pass (type hints, docstrings, logging,
UI polish).

**Why:** It is the graded Track-1 artifact and R7 demands byte-reproducible reruns.

**How to apply:**
- Type hints/docstrings are safe: every engine module has
  `from __future__ import annotations`, so annotations never run; docstrings only
  set `__doc__`.
- Logging is safe only if it goes to **stderr**. The CSV is a file; the
  machine-readable stdout contracts must stay on stdout: `validate_submission`'s
  `RESULT:` line, and `run_ranker`'s RESOURCE PROFILE / rule banners / CSV preview.
- Prove it every time: regen via
  `python engine/phase2_ranker.py --artifacts engine/data --jd-file job_description.docx --out <tmp>`,
  compare sha256 to baseline, run twice and diff for determinism, then
  `engine/validate_submission.py` must return PASS with 100% grounding.
