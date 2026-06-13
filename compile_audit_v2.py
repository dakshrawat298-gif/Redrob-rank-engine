#!/usr/bin/env python3
"""Compile the project's text sources into NotebookLM_Master_Codebase_v2.txt.

V2 differences vs compile_audit.py:
  * Includes the Streamlit UI (``app.py``) and ``main.py`` alongside the engine.
  * Includes the post-remediation architecture doc (``Remediation_Plan.md``) and
    project overview (``replit.md``).
  * Appends the NEW, rescaled ``team_vibecoder.csv`` (max score == 1.000000) last.

Still excludes the heavy binary/data artifacts (the FAISS index,
candidates.jsonl/.gz, byte_offset_index.json) to keep the master file lean.
"""
from __future__ import annotations

import os

OUT = "NotebookLM_Master_Codebase_v2.txt"
SEP = "\n\n================ [FILE: {name}] ================\n\n"

# Order: architecture docs -> Python scripts -> deps -> metadata -> output CSV.
DOCS = [
    "PRD.md", "TechSpec.md", "Rules.md", "AppFlow.md", "Design.md",
    "Schema.md", "ImplementationPlan.md", "Remediation_Plan.md",
    "Tracker.md", "replit.md",
]
PYTHON = [
    "app.py",
    "main.py",
    "engine/phase1_precompute.py",
    "engine/phase2_ranker.py",
    "engine/phase3_reasoning.py",
    "engine/run_ranker.py",
    "engine/validate_submission.py",
]
DEPS = ["pyproject.toml", "engine/requirements.txt"]
METADATA = ["engine/data/manifest.json"]

INCLUDE = DOCS + PYTHON + DEPS + METADATA
APPEND_LAST = "team_vibecoder.csv"


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def main() -> None:
    included, skipped = [], []
    with open(OUT, "w", encoding="utf-8") as out:
        out.write("NotebookLM Master Codebase V2 — Redrob Rank Engine\n")
        out.write(
            "Files included: see headers below. Excluded: *.faiss, "
            "candidates.jsonl/.gz, byte_offset_index.json.\n"
        )
        for path in INCLUDE:
            if not os.path.exists(path):
                skipped.append(path)
                continue
            out.write(SEP.format(name=path))
            out.write(read_text(path))
            included.append(path)
        # The exact ranked output (rescaled, top score = 1.0) goes at the very end.
        if os.path.exists(APPEND_LAST):
            out.write(SEP.format(name=APPEND_LAST))
            out.write(read_text(APPEND_LAST))
            included.append(APPEND_LAST)
        else:
            skipped.append(APPEND_LAST)

    size = os.path.getsize(OUT)
    print(f"wrote {OUT} | {size:,} bytes | {len(included)} files")
    for p in included:
        print(f"  + {p}")
    if skipped:
        print("skipped (not found):")
        for p in skipped:
            print(f"  - {p}")


if __name__ == "__main__":
    main()
