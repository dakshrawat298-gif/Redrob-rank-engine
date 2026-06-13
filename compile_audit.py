#!/usr/bin/env python3
"""Compile the project's text-based sources into a single NotebookLM audit file.

Excludes the FAISS index, candidates.jsonl/.gz, and byte_offset_index.json
(per the audit spec) to keep the master file lean. team_vibecoder.csv is
appended last so the auditor sees the exact ranked output.
"""
from __future__ import annotations

import os

OUT = "NotebookLM_Master_Codebase.txt"
SEP = "\n\n================ [FILE: {name}] ================\n\n"

# Order: architecture docs -> engine code -> deps -> metadata.
DOCS = [
    "PRD.md", "TechSpec.md", "Rules.md", "AppFlow.md",
    "Design.md", "Schema.md", "ImplementationPlan.md", "Tracker.md",
]
ENGINE = [
    "engine/phase1_precompute.py",
    "engine/phase2_ranker.py",
    "engine/phase3_reasoning.py",
    "engine/run_ranker.py",
    "engine/validate_submission.py",
]
DEPS = ["pyproject.toml", "engine/requirements.txt"]
METADATA = ["engine/data/manifest.json"]

INCLUDE = DOCS + ENGINE + DEPS + METADATA
APPEND_LAST = "team_vibecoder.csv"


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def main() -> None:
    included, skipped = [], []
    with open(OUT, "w", encoding="utf-8") as out:
        out.write(f"NotebookLM Master Codebase — Redrob Rank Engine\n")
        out.write(f"Files included: see headers below. Excluded: *.faiss, "
                  f"candidates.jsonl/.gz, byte_offset_index.json.\n")
        for path in INCLUDE:
            if not os.path.exists(path):
                skipped.append(path)
                continue
            out.write(SEP.format(name=path))
            out.write(read_text(path))
            included.append(path)
        # The exact ranked output goes at the very end.
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
