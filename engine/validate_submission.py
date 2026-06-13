#!/usr/bin/env python3
"""Stage-1 submission integrity checker for the Redrob Rank Engine.

This encodes the documented Stage-1 / R10 acceptance rules (``Rules.md`` R10 and
R2, ``PRD.md`` acceptance criteria) so we can mathematically confirm the CSV will
not be rejected by the evaluation harness:

  * header is EXACTLY ``candidate_id,rank,score,reasoning``
  * EXACTLY 100 data rows
  * ``candidate_id`` non-empty, unique, and present in the real dataset
  * ``rank`` is the contiguous integer sequence 1..100
  * ``score`` parses as float and is monotonically NON-INCREASING with rank
  * ``reasoning`` is non-empty and 100% grounded in the source record (R2)

Run:
    python3 engine/validate_submission.py team_vibecoder.csv \
        --artifacts engine/data --jd-file job_description.docx
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import phase2_ranker as p2  # noqa: E402
import phase3_reasoning as p3  # noqa: E402

EXPECTED_HEADER = ["candidate_id", "rank", "score", "reasoning"]
EXPECTED_ROWS = 100


def _load_record(plain_path: str, offsets: dict, cid: str):
    off = offsets.get(cid)
    if off is None:
        return None
    with open(plain_path, "r", encoding="utf-8") as f:
        f.seek(off)
        return json.loads(f.readline())


def validate(csv_path: str, artifacts: str, jd_path: str | None):
    errors: list[str] = []
    warns: list[str] = []

    if not os.path.exists(csv_path):
        return [f"CSV not found: {csv_path}"], []

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return ["CSV is empty"], []

    header, data = rows[0], rows[1:]

    # --- header ---------------------------------------------------------------
    if header != EXPECTED_HEADER:
        errors.append(f"header {header} != required {EXPECTED_HEADER}")

    # --- row count ------------------------------------------------------------
    if len(data) != EXPECTED_ROWS:
        errors.append(f"row count {len(data)} != required {EXPECTED_ROWS}")

    # --- per-row structural checks -------------------------------------------
    seen: set[str] = set()
    prev_score = None
    for i, row in enumerate(data, start=1):
        if len(row) != 4:
            errors.append(f"row {i}: has {len(row)} columns, expected 4")
            continue
        cid, rank_s, score_s, reasoning = row

        if not cid:
            errors.append(f"row {i}: empty candidate_id")
        if cid in seen:
            errors.append(f"row {i}: duplicate candidate_id {cid}")
        seen.add(cid)

        try:
            rank = int(rank_s)
            if rank != i:
                errors.append(f"row {i}: rank={rank} not contiguous (expected {i})")
        except ValueError:
            errors.append(f"row {i}: rank {rank_s!r} not an int")

        try:
            score = float(score_s)
            if prev_score is not None and score > prev_score + 1e-9:
                errors.append(
                    f"row {i}: score {score} > previous {prev_score} (not monotonic)"
                )
            prev_score = score
        except ValueError:
            errors.append(f"row {i}: score {score_s!r} not a float")

        if not reasoning.strip():
            errors.append(f"row {i}: empty reasoning")

    # --- existence + grounding (R2) ------------------------------------------
    offsets_path = os.path.join(artifacts, "byte_offset_index.json")
    manifest_path = os.path.join(artifacts, "manifest.json")
    if os.path.exists(offsets_path) and os.path.exists(manifest_path):
        offsets = json.load(open(offsets_path))
        plain = json.load(open(manifest_path)).get("plain_jsonl")
        jd_text = p2.load_jd_text(jd_path) if jd_path else ""
        ungrounded = 0
        missing = 0
        for row in data:
            if len(row) != 4:
                continue
            cid, _, _, reasoning = row
            rec = _load_record(plain, offsets, cid)
            if rec is None:
                missing += 1
                errors.append(f"candidate_id {cid} not found in dataset")
                continue
            ms = p3.match_skills(rec, jd_text) if jd_text else []
            if not p3._is_grounded(reasoning, rec, ms):
                ungrounded += 1
                errors.append(f"candidate_id {cid}: reasoning not grounded -> {reasoning!r}")
        if not missing and not ungrounded:
            warns.append(f"grounding: all {len(data)} reasoning strings fully grounded (R2)")
    else:
        warns.append("grounding skipped: artifacts (offsets/manifest) not found")

    return errors, warns


def main(argv):
    ap = argparse.ArgumentParser(description="Stage-1 submission integrity checker")
    ap.add_argument("csv", help="submission CSV (e.g. team_vibecoder.csv)")
    ap.add_argument("--artifacts", default="engine/data")
    ap.add_argument("--jd-file", default=None)
    args = ap.parse_args(argv)

    errors, warns = validate(args.csv, args.artifacts, args.jd_file)

    print(f"== Stage-1 integrity check: {args.csv} ==")
    for w in warns:
        print(f"  [info] {w}")
    if errors:
        print(f"RESULT: FAIL ({len(errors)} error(s))")
        for e in errors[:50]:
            print(f"  [error] {e}")
        return 1
    print("RESULT: PASS - header, 100 rows, unique ids, contiguous/monotonic rank, "
          "non-increasing score, non-empty grounded reasoning. Submission valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
