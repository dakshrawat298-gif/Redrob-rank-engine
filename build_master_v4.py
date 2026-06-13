#!/usr/bin/env python3
"""Compile NotebookLM_Master_Codebase_V4.txt — a single-file audit bundle.

Sections, in order:
  1. Architecture / design docs (all *.md)
  2. Updated Python sources (engine + entrypoints)
  3. The final team_vibecoder.csv (appended at the very end)

Fails loud (R10 spirit) if any expected file is missing.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "NotebookLM_Master_Codebase_V4.txt"

# 1. Architecture docs — explicit order, most-foundational first.
DOC_FILES = [
    "PRD.md",
    "Design.md",
    "TechSpec.md",
    "Schema.md",
    "Rules.md",
    "AppFlow.md",
    "ImplementationPlan.md",
    "Tracker.md",
    "Remediation_Plan.md",
    "Stage4_Hotfix_Plan.md",
    "V4_Hotfix_Plan.md",
    "replit.md",
]

# 2. Python sources requested for the audit.
CODE_FILES = [
    "engine/phase1_precompute.py",
    "engine/phase2_ranker.py",
    "engine/phase3_reasoning.py",
    "engine/validate_submission.py",
    "app.py",
    "main.py",
]

# 3. Final deliverable, appended last.
CSV_FILE = "team_vibecoder.csv"

LANG = {".py": "python", ".md": "markdown", ".csv": "csv"}


def banner(title: str) -> str:
    bar = "=" * 78
    return f"\n{bar}\n=== {title}\n{bar}\n"


def section_banner(title: str) -> str:
    bar = "#" * 78
    return f"\n\n{bar}\n## {title}\n{bar}\n"


def read_required(rel: str) -> str:
    p = ROOT / rel
    if not p.is_file():
        sys.exit(f"ERROR missing required file: {rel} (refusing to write a partial bundle)")
    return p.read_text(encoding="utf-8")


def emit_file(parts: list, rel: str) -> None:
    text = read_required(rel)
    lang = LANG.get(Path(rel).suffix, "")
    parts.append(banner(f"FILE: {rel}  ({len(text.splitlines())} lines)"))
    parts.append(f"```{lang}\n{text.rstrip()}\n```\n")


def main() -> int:
    parts: list = []
    parts.append(
        "NOTEBOOKLM MASTER CODEBASE — V4 (FINAL AUDIT BUNDLE)\n"
        "Project: Redrob Rank Engine (Track 1, CPU-only candidate ranking)\n"
        "Contents: architecture docs, updated Python sources, final submission CSV.\n"
    )

    parts.append(section_banner("PART 1 — ARCHITECTURE & DESIGN DOCS"))
    for rel in DOC_FILES:
        emit_file(parts, rel)

    parts.append(section_banner("PART 2 — PYTHON SOURCES (UPDATED)"))
    for rel in CODE_FILES:
        emit_file(parts, rel)

    parts.append(section_banner("PART 3 — FINAL SUBMISSION: team_vibecoder.csv"))
    emit_file(parts, CSV_FILE)

    OUT.write_text("".join(parts), encoding="utf-8")
    print(f"wrote {OUT.name} | {OUT.stat().st_size:,} bytes | "
          f"{len(OUT.read_text().splitlines()):,} lines")
    print(f"docs={len(DOC_FILES)} code={len(CODE_FILES)} csv=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
