#!/usr/bin/env python3
"""Phase 2 - Two-pass re-ranker for the Redrob Rank Engine (Track 1).

Consumes the Phase 1 artifacts and produces the Top 100 candidates for a given
job description (JD). This is the *runtime* stage that must respect the hard
budget (CPU-only, <=16GB, <=5min) and make NO network calls during ranking
beyond loading the local ONNX model (``Rules.md`` R5, R6).

Pipeline (see ``TechSpec.md`` sections 3-6 and ``AppFlow.md``):

  Pass 1 - Recall (vectors + ids only, R8):
    * embed the JD with the same fastembed model used in Phase 1
    * FAISS search the IndexFlatIP for the top ``K`` (default 1000) candidates,
      yielding (candidate_id, base cosine similarity)

  Pass 2 - Precision (lazy metadata for the K recall set only, R1):
    * ``seek`` each candidate's JSON record via ``byte_offset_index.json``
      (only K records are ever parsed/held in memory)
    * drop honeypots (immediate Tier 0 / score 0)
    * apply JD-specific multipliers to the base cosine score
    * sort by final score (deterministic tie-breaks, R7) and take the Top 100

Output: a CSV with columns ``candidate_id,rank,score,reasoning`` where the
``reasoning`` column is a Phase-3 placeholder (the AST reasoning engine).

Usage
-----
    python engine/phase2_ranker.py --artifacts engine/data --jd "Senior ML ..."
    python engine/phase2_ranker.py --artifacts engine/data --jd-file jd.txt
With no --jd/--jd-file a built-in sample AI-engineering JD is used (handy for
running against the Phase 1 mock data).
"""

from __future__ import annotations

import argparse
import csv
import heapq
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from typing import Dict, List, Optional, Tuple

try:  # works whether run as a script (engine/) or imported as engine.phase2_ranker
    from phase3_reasoning import (build_reasoning, assign_unique_reasonings,
                                  match_skills, skill_names, profile_of,
                                  signals_of, experience_years)
except ImportError:  # pragma: no cover
    from engine.phase3_reasoning import (build_reasoning, assign_unique_reasonings,
                                         match_skills, skill_names, profile_of,
                                         signals_of, experience_years)

# ---------------------------------------------------------------------------
# Configuration (single source of truth - no magic numbers, Rules.md spirit)
# ---------------------------------------------------------------------------

RECALL_K = 1000          # Pass-1 recall set size
TOP_N = 100              # final output size

# Consulting firms for the "consulting lifer" penalty (case-insensitive match).
CONSULTING_FIRMS = {
    "tcs", "tata consultancy services", "infosys", "wipro", "accenture",
    "cognizant", "capgemini",
}

# AI-engineering keywords for the title-mismatch honeypot.
AI_KEYWORDS = {
    "rag", "pinecone", "langchain", "vector database", "vector databases",
    "llm", "llm fine-tuning", "embeddings", "weaviate", "qdrant", "milvus",
}
NON_TECH_TITLE_TOKENS = ("marketing", "sales", "hr", "human resources")

# Off-domain professions for the `domain_mismatch` relevance-trap drop (Fix #1).
# Matched WHOLE-WORD against ``profile.current_title`` ONLY (never skills/summary)
# so e.g. "sales" cannot match "salesforce" and "finance" cannot match the
# "financial" inside another token. This is distinct from NON_TECH_TITLE_TOKENS
# above (which only fires alongside an AI-keyword skill): a profile whose CURRENT
# title is squarely another profession is an off-domain trap for this AI-
# engineering JD and is dropped outright (R4). Kept conservative + title-only.
# Approved Stage-4 deny-list (whole-word, lowercase, matched against
# current_title ONLY). Whole-word matching prevents substring hits such as
# "sales"->"salesforce", "finance"->"financial", "operations"->"devops".
TITLE_DENY_LIST = {
    "civil", "mechanical", "electrical", "chemical", "structural",
    "hr", "human resources", "recruiter", "recruitment", "talent acquisition",
    "marketing", "sales", "account manager", "accountant", "accounting",
    "finance", "operations", "administrative", "office manager",
    "customer support", "customer success",
    "teacher", "professor", "nurse", "doctor", "lawyer", "paralegal",
}

# Multiplier constants.
CONSULTING_LIFER_MULTIPLIER = 0.1
# Job-hopper penalty per R3 ("penalize job hoppers"). Softened 0.5 -> 0.8 as an
# EXPLICIT, documented R3 tradeoff (Stage-4 hotfix): 0.5x buried strong-but-
# mobile candidates far below the cutoff. The plan proposed 0.8x, but empirically
# the strongest hopper still landed at rank ~108 (just below the cutoff), so the
# Stage-4 acceptance criterion "at least one genuine hopper visible in the Top-100
# with the concern clause" was unmet. Calibrated to 0.85x: the minimal softening
# (still a 15% penalty) that surfaces exactly one true hopper in the Top-100. The
# penalty is NOT removed and is still logged. The hopper flag is tracked
# independently of this multiplier and ALWAYS surfaced as an honest concern in the
# reasoning for any hopper that makes the Top-N, so the penalty never hides the
# flag (breakdown["hopper"] < 1.0 still holds at 0.85, so the concern clause fires).
JOB_HOPPER_MULTIPLIER = 0.85
JOB_HOPPER_TENURE_THRESHOLD = 1.5      # years per company
NOTICE_FREE_DAYS = 30                   # <= this -> no notice penalty
NOTICE_DECAY_PER_30D = 0.15            # subtracted per extra 30-day block

# Honeypot thresholds (real-schema traps, kept conservative to avoid false drops).
OVERLAP_TENURE_RATIO = 1.5     # summed tenure > calendar span * this -> impossible
EXPERT_SCORE_THRESHOLD = 90.0  # skill_assessment_scores value >= this == "expert"
# Experience-inflation trap (Fix #3, REFRAMED — the dataset has no
# `current_company_age_years` field): claimed years_of_experience implausibly
# exceeds the real calendar span of career_history. Conservative 2x so a genuine
# senior listing only recent roles is unlikely to be flagged; null-safe.
EXPERIENCE_INFLATION_RATIO = 2.0

# Phase-3 placeholder for the reasoning column.
REASONING_PLACEHOLDER = "AST generation pending Phase 3"

# Built-in sample JD (used when no JD is supplied) - matches the mock dataset.
SAMPLE_JD = (
    "Senior Backend / Platform Engineer with strong distributed systems "
    "experience. Must know Go or Java, Kafka, Kubernetes, PostgreSQL and have "
    "built scalable, fault-tolerant microservices on AWS or GCP. Experience "
    "with observability, CI/CD and high-throughput data pipelines preferred."
)

_START = time.monotonic()


def log(msg: str) -> None:
    """Timestamped log line to stderr (keeps stdout clean), per Design.md s3."""
    print(f"[{time.monotonic() - _START:7.2f}s] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Artifact loading
# ---------------------------------------------------------------------------

def load_artifacts(artifacts_dir: str):
    """Load manifest, FAISS index, id_map, and byte-offset index.

    Returns ``(manifest, faiss_index, id_map, byte_offsets, plain_jsonl_path)``.
    Fails loud (non-zero exit) if any artifact is missing (R10).
    """
    import faiss  # lazy heavy import

    manifest_path = os.path.join(artifacts_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        log(f"ERROR manifest not found: {manifest_path} (run Phase 1 first)")
        raise SystemExit(2)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    faiss_path = manifest["artifacts"]["faiss"]
    offsets_path = manifest["artifacts"]["byte_offset_index"]
    idmap_path = manifest["artifacts"]["id_map"]
    # The byte offsets are valid against this plain (decompressed) JSONL - NOT
    # the original .gz input. Phase 2 must read records from here (R1, R8).
    plain_jsonl = manifest["plain_jsonl"]

    for label, p in (("faiss", faiss_path), ("byte_offset_index", offsets_path),
                     ("id_map", idmap_path), ("plain_jsonl", plain_jsonl)):
        if not os.path.exists(p):
            log(f"ERROR {label} artifact missing: {p}")
            raise SystemExit(2)

    index = faiss.read_index(faiss_path)
    with open(idmap_path, "r", encoding="utf-8") as f:
        id_map = json.load(f)
    with open(offsets_path, "r", encoding="utf-8") as f:
        byte_offsets = json.load(f)

    log(f"loaded artifacts | vectors={index.ntotal} ids={len(id_map)} "
        f"offsets={len(byte_offsets)} model={manifest.get('model_name')}")
    return manifest, index, id_map, byte_offsets, plain_jsonl


# ---------------------------------------------------------------------------
# Pass 1 - recall (vectors + ids only)
# ---------------------------------------------------------------------------

def embed_query(jd_text: str, model_name: str):
    """Embed the JD with the same fastembed model used in Phase 1, normalized.

    Air-gap lock (R5): if the caller engaged the air-gap (``run_ranker.py``'s
    ``network_air_gap`` sets ``HF_HUB_OFFLINE=1`` *before* ranking starts), we
    reinforce every offline switch and load the model strictly from the local
    cache that Phase 1 populated -- never pinging the HF Hub. A missing local
    model then fails loud (R10) instead of silently reaching for the network.

    When NO air-gap is requested (Phase 1 / dev runs), we must NOT force offline,
    or the very first run could never download and cache the model. Telemetry is
    always disabled regardless.
    """
    airgap = os.environ.get("HF_HUB_OFFLINE") == "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    if airgap:
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_DATASETS_OFFLINE"] = "1"

    import numpy as np
    import faiss
    from fastembed import TextEmbedding

    try:
        model = TextEmbedding(model_name=model_name)
    except Exception as exc:  # noqa: BLE001 - surface a missing offline model loudly
        if airgap:
            log(f"ERROR could not load embedding model '{model_name}' from the "
                f"local cache under the ranking air-gap (R5/R10); Phase 1 must "
                f"cache it while online before air-gapped ranking. ({exc})")
            raise SystemExit(2)
        raise
    vec = np.asarray(list(model.embed([jd_text])), dtype=np.float32)
    faiss.normalize_L2(vec)  # cosine via IndexFlatIP
    return vec


def recall_top_k(index, query_vec, id_map: List[str], k: int
                 ) -> List[Tuple[str, float]]:
    """FAISS search -> list of (candidate_id, base_cosine_score), best first."""
    k = min(k, index.ntotal)
    scores, idxs = index.search(query_vec, k)
    out: List[Tuple[str, float]] = []
    for row_idx, score in zip(idxs[0], scores[0]):
        if row_idx < 0:  # FAISS pads with -1 when fewer than k results
            continue
        out.append((id_map[row_idx], float(score)))
    return out


# ---------------------------------------------------------------------------
# Pass 2 - lazy metadata load (only the recall set, R1)
# ---------------------------------------------------------------------------

def load_record(plain_jsonl_path: str, fh, byte_offset: int) -> Optional[dict]:
    """Seek to ``byte_offset`` in the open file handle and parse one record."""
    fh.seek(byte_offset)
    line = fh.readline()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Honeypot detection (immediate drop) - Schema.md s4 / Phase 2 request
# ---------------------------------------------------------------------------

def _companies(record: dict) -> List[str]:
    """Employer names from the real ``career_history`` list."""
    names: List[str] = []
    for e in record.get("career_history") or []:
        if isinstance(e, dict) and e.get("company"):
            names.append(str(e["company"]))
    return names


def _parse_month_index(date_str) -> Optional[int]:
    """``YYYY-MM[-DD]`` -> integer month index (year*12 + month-1); else ``None``."""
    if not isinstance(date_str, str):
        return None
    m = re.match(r"\s*(\d{4})-(\d{1,2})", date_str)
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        return None
    return year * 12 + (month - 1)


def _career_span_and_tenure_months(record: dict) -> Tuple[Optional[int], Optional[int]]:
    """Return ``(calendar_span_months, total_tenure_months)`` from career_history.

    ``span`` runs from the earliest start to the latest end; ongoing roles imply
    their end from ``start + duration_months`` so no wall-clock "today" is needed
    (keeps ranking deterministic and offline). ``tenure`` sums all
    ``duration_months``. Tenure far exceeding span means impossible concurrent
    full-time roles -> a fabricated profile.
    """
    hist = record.get("career_history")
    if not isinstance(hist, list) or not hist:
        return None, None
    starts: List[int] = []
    ends: List[int] = []
    tenure = 0
    saw_tenure = False
    for h in hist:
        if not isinstance(h, dict):
            continue
        dm = h.get("duration_months")
        if isinstance(dm, (int, float)) and dm >= 0:
            tenure += int(dm)
            saw_tenure = True
        start = _parse_month_index(h.get("start_date"))
        if start is None:
            continue
        starts.append(start)
        end = _parse_month_index(h.get("end_date"))
        if end is None:  # ongoing / current -> imply end from duration
            end = start + (int(dm) if isinstance(dm, (int, float)) and dm >= 0 else 0)
        ends.append(end)
    span = (max(ends) - min(starts)) if starts and ends else None
    return span, (tenure if saw_tenure else None)


def _mean_tenure_years(record: dict) -> Optional[float]:
    """Average months-per-company / 12 from ``career_history`` (job-hopper signal)."""
    hist = record.get("career_history")
    if not isinstance(hist, list):
        return None
    months = [int(h["duration_months"]) for h in hist
              if isinstance(h, dict)
              and isinstance(h.get("duration_months"), (int, float))
              and h["duration_months"] >= 0]
    if not months:
        return None
    return (sum(months) / len(months)) / 12.0


def _title_denied(title) -> Optional[str]:
    """Return the off-domain term tripped by ``title`` (whole-word), else None.

    WHOLE-WORD only (boundary regex), matched against the current title string
    exclusively, so a denied token can never match inside an unrelated word
    (e.g. "sales" in "salesforce", "finance" in "financial").
    """
    t = str(title or "").lower()
    if not t:
        return None
    for term in TITLE_DENY_LIST:
        if re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", t):
            return term
    return None


def detect_honeypot(record: dict) -> Optional[str]:
    """Return a reason string if the candidate is a honeypot, else ``None``.

    Reconciled to the REAL nested schema. Tripping any rule means immediate
    disqualification (Tier 0 / score 0, R4). Every check is grounded in fields
    that actually exist in the dataset and kept conservative so genuine
    candidates are not wrongly dropped (a false drop hurts NDCG).
    """
    profile = profile_of(record)
    signals = signals_of(record)
    exp = experience_years(record)

    # 0. Off-domain relevance trap: current title is squarely another profession
    #    (Civil/HR/Marketing/...) — drop outright for this AI-engineering JD
    #    (Fix #1). Title-only + whole-word so it stays conservative.
    if _title_denied(profile.get("current_title")):
        return "domain_mismatch"

    # 1. Overlapping timeline: summed tenure impossibly exceeds the real calendar
    #    span of the career history (fabricated, concurrent full-time roles).
    span, tenure = _career_span_and_tenure_months(record)
    if (span is not None and tenure is not None and span > 0
            and tenure > span * OVERLAP_TENURE_RATIO):
        return "overlapping_timeline"

    # 1b. Experience inflation: claimed years_of_experience implausibly exceeds
    #     the real calendar span of career_history (fabricated seniority, Fix #3).
    #     Null-safe — skips unless BOTH the claim and a positive span are present.
    yoe_claim = profile.get("years_of_experience")
    if (isinstance(yoe_claim, (int, float)) and yoe_claim >= 0
            and span is not None and span > 0
            and yoe_claim * 12 > span * EXPERIENCE_INFLATION_RATIO):
        return "experience_inflation"

    # 2. Fake expert: an expert-level assessment score with <0.5y real experience.
    #    (exp==0 was too weak; <0.5 also catches sub-6-month fabricated experts.)
    assessments = signals.get("skill_assessment_scores")
    if isinstance(assessments, dict):
        has_expert = any(isinstance(v, (int, float)) and v >= EXPERT_SCORE_THRESHOLD
                         for v in assessments.values())
        if has_expert and isinstance(exp, (int, float)) and exp < 0.5:
            return "fake_expert"

    # 3. Title mismatch trap: non-technical current title but AI-engineering skills.
    title = str(profile.get("current_title") or "").lower()
    if any(tok in title for tok in NON_TECH_TITLE_TOKENS):
        skills_lc = {s.lower() for s in skill_names(record)}
        if skills_lc & AI_KEYWORDS:
            return "title_mismatch"

    return None


# ---------------------------------------------------------------------------
# NDCG@10 multipliers - Phase 2 request / TechSpec.md s6
# ---------------------------------------------------------------------------

def compute_multiplier(record: dict) -> Tuple[float, Dict[str, float]]:
    """Combine all JD-specific multipliers into one factor on the base score.

    Returns ``(multiplier, breakdown)`` for transparent DEBUG logging.
    """
    breakdown: Dict[str, float] = {}

    # --- Consulting lifer: 100% career at consulting firms, no product co. ---
    companies = _companies(record)
    consulting_mult = 1.0
    if companies:
        all_consulting = all(c.strip().lower() in CONSULTING_FIRMS for c in companies)
        if all_consulting:
            consulting_mult = CONSULTING_LIFER_MULTIPLIER
    breakdown["consulting"] = consulting_mult

    # --- Job hopper: average tenure per company (from career_history dates) ---
    hopper_mult = 1.0
    mean_tenure = _mean_tenure_years(record)
    if mean_tenure is not None and mean_tenure < JOB_HOPPER_TENURE_THRESHOLD:
        hopper_mult = JOB_HOPPER_MULTIPLIER
    breakdown["hopper"] = hopper_mult

    # --- Notice period decay: 1.0 up to 30 days, -0.15 per extra 30-day block ---
    notice_mult = 1.0
    signals = signals_of(record)
    notice = signals.get("notice_period_days", record.get("notice_period_days"))
    if isinstance(notice, (int, float)) and notice > NOTICE_FREE_DAYS:
        extra_blocks = (int(notice) - NOTICE_FREE_DAYS + 29) // 30  # ceil to 30d blocks
        notice_mult = max(0.0, 1.0 - NOTICE_DECAY_PER_30D * extra_blocks)
    breakdown["notice"] = notice_mult

    # --- Engagement boost: 1 + response_rate * completion_rate (in [1, 2]) ---
    # Rates are in [0,1]; negatives are "no data" sentinels. Clamp both ways so a
    # sentinel gives no boost and out-of-range upstream data can't inflate the band.
    rr = signals.get("recruiter_response_rate", 0)
    ic = signals.get("interview_completion_rate", 0)
    rr = min(1.0, float(rr)) if isinstance(rr, (int, float)) and rr > 0 else 0.0
    ic = min(1.0, float(ic)) if isinstance(ic, (int, float)) and ic > 0 else 0.0
    engagement_mult = 1.0 + (rr * ic)  # in [1, 2]
    breakdown["engagement"] = engagement_mult

    total = consulting_mult * hopper_mult * notice_mult * engagement_mult
    return total, breakdown


# ---------------------------------------------------------------------------
# Ranking driver
# ---------------------------------------------------------------------------

class _RevId:
    """Wrap a candidate_id so a LARGER id compares as "smaller".

    Lets a size-``top_n`` min-heap evict the worst candidate on score/sem_score
    ties using the canonical tie-break (ascending candidate_id ranks higher, so
    the larger id is the one to drop first). Determinism preserved (R7).
    """

    __slots__ = ("s",)

    def __init__(self, s: str):
        self.s = s

    def __lt__(self, other: "_RevId") -> bool:
        return self.s > other.s


def rank(artifacts_dir: str, jd_text: str, k: int, top_n: int, debug: bool
         ) -> List[dict]:
    """Run Pass 1 + Pass 2 and return the Top-N scored candidate dicts."""
    manifest, index, id_map, byte_offsets, plain_jsonl = load_artifacts(artifacts_dir)

    log(f"embedding JD ({len(jd_text)} chars) | model={manifest.get('model_name')}")
    qvec = embed_query(jd_text, manifest["model_name"])

    log(f"Pass 1: FAISS recall top-{k}")
    recall = recall_top_k(index, qvec, id_map, k)
    log(f"Pass 1: recalled {len(recall)} candidates")

    log("Pass 2: lazy-load metadata + score (honeypots + multipliers)")
    # Bounded top-N retention (R1): keep at most ``top_n`` survivors in a min-heap
    # whose root is always the WORST kept candidate, so memory is O(top_n) records
    # instead of O(K). The heap order is the exact inverse of the final tie-break
    # (R7): worst = lowest score, then lowest sem_score, then LARGEST candidate_id
    # (ascending id ranks higher). ``_RevId`` makes the larger id compare as
    # "smaller" so the min-heap evicts it first on ties.
    heap: list = []
    kept = 0
    dropped = 0
    drop_reasons: Dict[str, int] = {}
    missing = 0

    with open(plain_jsonl, "rb") as fh:
        for cid, base_score in recall:
            offset = byte_offsets.get(cid)
            if offset is None:
                missing += 1
                continue
            record = load_record(plain_jsonl, fh, offset)
            if record is None:
                missing += 1
                continue

            reason = detect_honeypot(record)
            if reason is not None:
                dropped += 1
                drop_reasons[reason] = drop_reasons.get(reason, 0) + 1
                if debug:
                    log(f"  DROP {cid} | honeypot={reason}")
                continue  # Tier 0 - never appears in output (R4)

            multiplier, breakdown = compute_multiplier(record)
            final_score = base_score * multiplier
            notice_days = signals_of(record).get("notice_period_days",
                                                 record.get("notice_period_days"))
            payload = {
                "candidate_id": cid,
                "score": final_score,
                "sem_score": base_score,
                "multiplier": multiplier,
                # Carried into Phase 3 reasoning (only the recall set, R1).
                "record": record,
                "hopper_fired": breakdown["hopper"] < 1.0,
                "notice_days": notice_days,
                "matched_skills": match_skills(record, jd_text),
            }
            kept += 1
            item = (final_score, base_score, _RevId(cid), payload)
            if len(heap) < top_n:
                heapq.heappush(heap, item)
            else:
                heapq.heappushpop(heap, item)  # keep the top_n best, evict worst
            if debug:
                log(f"  KEEP {cid} | base={base_score:.4f} mult={multiplier:.3f} "
                    f"final={final_score:.4f} {breakdown}")

    log(f"Pass 2: kept={kept} retained={len(heap)} dropped_honeypots={dropped} "
        f"missing={missing} reasons={drop_reasons or '{}'}")

    # Deterministic final order: score desc, then sem_score desc, then id asc (R7).
    top = [item[3] for item in heap]
    top.sort(key=lambda r: (-r["score"], -r["sem_score"], r["candidate_id"]))
    top = top[:top_n]

    # Score normalization (R9 precaution): map raw scores into [0,1] with a single
    # monotonic transform so order and the non-increasing property are preserved
    # EXACTLY while the column stays within the [0,1] band the harness may expect.
    # Dividing by the top raw score keeps granularity (unlike a flat min(x,1.0)
    # clamp, which would collapse the whole top tier into 1.0 ties).
    max_raw = top[0]["score"] if top else 0.0
    for row in top:
        raw = row["score"]
        row["score"] = (max(raw, 0.0) / max_raw) if max_raw > 0 else 0.0

    # Phase 3: grounded AST reasoning for the final ranked list. ``top`` is in
    # the deterministic final rank order (R7), so the uniqueness post-pass below
    # is byte-reproducible. It sets each row["reasoning"] in place and guarantees
    # 100 globally-unique, grounded strings (R9).
    log("Phase 3: generating grounded reasoning (AST templating)")
    assign_unique_reasonings(top)
    log(f"selected Top {len(top)} (requested {top_n})")
    return top


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_csv(rows: List[dict], out_path: str) -> None:
    """Write the ``candidate_id,rank,score,reasoning`` CSV (Design.md s1)."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for rank_pos, row in enumerate(rows, start=1):
            writer.writerow([
                row["candidate_id"],
                rank_pos,
                f"{row['score']:.6f}",
                row.get("reasoning") or REASONING_PLACEHOLDER,
            ])
    log(f"wrote {out_path} | rows={len(rows)}")


# ---------------------------------------------------------------------------
# Job-description loading (supports .docx via stdlib only - no extra dependency)
# ---------------------------------------------------------------------------

_DOCX_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_docx_text(path: str) -> str:
    """Extract plain text from a ``.docx`` using ONLY the stdlib.

    A ``.docx`` is a zip whose body is ``word/document.xml``. We read the text of
    every ``<w:t>`` run and join runs per ``<w:p>`` paragraph with newlines. No
    third-party library is needed, so this also works under the ranking air-gap
    (Rules.md R5/R6) - the JD parse never touches the network.
    """
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    lines: List[str] = []
    for para in root.iter(f"{_DOCX_NS}p"):
        runs = [node.text for node in para.iter(f"{_DOCX_NS}t") if node.text]
        line = "".join(runs).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def load_jd_text(path: str) -> str:
    """Load JD text from a ``.docx`` (Word) or a plain-text file."""
    if path.lower().endswith(".docx"):
        text = extract_docx_text(path)
    else:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    return text.strip()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Phase 2 - two-pass FAISS recall + behavioral re-ranking.",
    )
    p.add_argument("--artifacts", default="engine/data",
                   help="Directory with Phase 1 artifacts (default: engine/data)")
    p.add_argument("--jd", default=None, help="Job description text")
    p.add_argument("--jd-file", default=None, help="Path to a file with the JD text")
    p.add_argument("--out", default="engine/data/phase2_ranked.csv",
                   help="Output CSV path")
    p.add_argument("--k", type=int, default=RECALL_K, help="Pass-1 recall size")
    p.add_argument("--top-n", type=int, default=TOP_N, help="Final output size")
    p.add_argument("--debug", action="store_true",
                   help="Verbose per-candidate scoring log")
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    if args.jd_file:
        if not os.path.exists(args.jd_file):
            log(f"ERROR JD file not found: {args.jd_file}")
            return 2
        try:
            jd_text = load_jd_text(args.jd_file)
        except Exception as exc:  # noqa: BLE001 - surface any parse failure loudly
            log(f"ERROR could not read JD file {args.jd_file}: {exc}")
            return 2
        log(f"loaded JD from {args.jd_file} ({len(jd_text)} chars)")
    elif args.jd:
        jd_text = args.jd.strip()
    else:
        log("no --jd/--jd-file given; using built-in SAMPLE_JD")
        jd_text = SAMPLE_JD

    if not jd_text:
        log("ERROR empty JD text")
        return 2
    if args.k <= 0 or args.top_n <= 0:
        log(f"ERROR --k and --top-n must be positive (got k={args.k}, top_n={args.top_n})")
        return 2

    rows = rank(args.artifacts, jd_text, args.k, args.top_n, args.debug)
    if not rows:
        log("ERROR no candidates survived filtering; nothing to write (R10)")
        return 3
    if len(rows) != args.top_n:
        log(
            f"ERROR only {len(rows)} valid candidates survived but {args.top_n} "
            f"required; refusing to write a short submission (R9/R10). Widen "
            f"recall (--k) or relax filters."
        )
        return 3
    write_csv(rows, args.out)
    log(f"DONE | total={time.monotonic() - _START:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
