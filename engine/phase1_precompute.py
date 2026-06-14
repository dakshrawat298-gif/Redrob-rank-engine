#!/usr/bin/env python3
"""Phase 1 - Pre-computation of Embeddings for the Redrob Rank Engine (Track 1).

This script turns the raw candidate dataset (``candidates.jsonl`` or
``candidates.jsonl.gz``) into the compact, query-ready disk artifacts that the
ranking runtime consumes. It is the *offline* stage described in ``TechSpec.md``
section 2 and ``ImplementationPlan.md`` Phase 1, and is NOT counted against the
5-minute ranking budget.

Embedding backend
-----------------
Embeddings are produced by the ``all-MiniLM-L6-v2`` model (384-dim) via
``fastembed`` - an ONNX-runtime backend that runs on CPU with no PyTorch
dependency. This is deliberately lighter and faster than the PyTorch-based
``sentence-transformers`` package (which could not be resolved in this
environment because it is pinned to the CPU-only PyTorch wheel index), while
producing the same model's embeddings. The model name is configurable.

It produces:

  * ``candidate_embeddings.faiss`` - a normalized ``IndexFlatIP`` FAISS index
    (inner product over unit vectors == cosine similarity).
  * ``byte_offset_index.json`` - ``{candidate_id: byte_offset}`` into the plain
    JSONL, enabling O(1) lazy ``seek`` reads in Pass 2 (``Rules.md`` R1).
  * ``id_map.json`` - integer FAISS row index -> ``candidate_id``.
  * ``manifest.json`` - run metadata (model, dim, count, normalized, paths).

Guardrails honored (see ``Rules.md``):
  * R1  - the JSONL is streamed line-by-line; it is never fully loaded into RAM.
          Embedding text is encoded in bounded batches; only one batch of text
          lives in memory at a time.
  * R7  - deterministic: no randomness in the embedding/index path.

Usage
-----
Generate mock data and run end-to-end (great for testing before the real file):

    python engine/phase1_precompute.py --mock 100 --outdir engine/data

Run against the real dataset (plain or gzipped):

    python engine/phase1_precompute.py --input candidates.jsonl.gz --outdir engine/data
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

try:  # works whether run as a script (engine/) or imported as engine.phase1_precompute
    from logging_util import get_logger
except ImportError:  # pragma: no cover
    from engine.logging_util import get_logger

_LOGGER = get_logger("phase1")

# ---------------------------------------------------------------------------
# Configuration constants (single source of truth for this stage)
# ---------------------------------------------------------------------------

# Lightweight, CPU-optimized sentence embedding model (384-dim). See TechSpec.md.
# Served via fastembed (ONNX runtime, CPU, no PyTorch).
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Field names used to build the embedding text. Reconciled against the REAL
# dataset schema (nested ``profile`` + ``skills``/``career_history``/``education``
# lists). The ID is a top-level ``candidate_id`` (e.g. "CAND_0000001").
ID_FIELD = "candidate_id"
# Real dataset schema: the semantically-rich fields are nested under ``profile``
# plus the ``skills`` / ``career_history`` / ``education`` lists. These names are
# documentary (the actual extraction happens in ``build_text``); they are recorded
# in the manifest so a reader knows exactly what was embedded.
TEXT_FIELDS = ("profile.headline", "profile.current_title", "profile.current_company",
               "profile.current_industry", "skills[].name", "profile.summary",
               "career_history[].title", "career_history[].description",
               "education[].field_of_study")
# MiniLM truncates to ~256 tokens, so embedding text longer than this only wastes
# tokenization CPU without changing the vector. Cap the composed string.
EMBED_MAX_CHARS = 2000

# Output artifact filenames.
FAISS_FILENAME = "candidate_embeddings.faiss"
OFFSETS_FILENAME = "byte_offset_index.json"
IDMAP_FILENAME = "id_map.json"
MANIFEST_FILENAME = "manifest.json"
PLAIN_JSONL_FILENAME = "candidates.jsonl"  # canonical seekable file for Pass 2

# Encoding batch size - bounds peak memory of the embedding step (R1).
DEFAULT_BATCH_SIZE = 512

_START = time.monotonic()


def log(msg: str) -> None:
    """Emit a diagnostic line via the shared ``redrob`` logger (stderr).

    ``ERROR``/``WARN``-prefixed messages are routed to the matching log level so
    the standard logging machinery (levels, formatting, filtering) applies while
    existing call sites stay unchanged. Stdout is left clean for artifacts.
    """
    if msg.startswith("ERROR"):
        _LOGGER.error(msg)
    elif msg.startswith("WARN"):
        _LOGGER.warning(msg)
    else:
        _LOGGER.info(msg)


# ---------------------------------------------------------------------------
# Mock data generator
# ---------------------------------------------------------------------------

_MOCK_TITLES = [
    "Senior Backend Engineer", "Staff Software Engineer", "Distributed Systems Engineer",
    "Platform Engineer", "Site Reliability Engineer", "Data Engineer",
    "Machine Learning Engineer", "Full Stack Developer", "DevOps Engineer",
    "Principal Engineer", "Cloud Architect", "Backend Developer",
]
_MOCK_SKILLS = [
    "go", "rust", "python", "java", "kafka", "postgresql", "redis", "grpc",
    "kubernetes", "docker", "aws", "gcp", "terraform", "spark", "airflow",
    "tensorflow", "pytorch", "react", "typescript", "graphql", "microservices",
]
# AI-engineering skills used to seed the "title mismatch" honeypot in Phase 2.
_MOCK_AI_SKILLS = ["RAG", "Pinecone", "LangChain", "vector databases", "LLM fine-tuning"]
_MOCK_SUMMARY_BITS = [
    "Built and scaled fault-tolerant services handling millions of requests per day.",
    "Led the migration from a monolith to event-driven microservices.",
    "Designed a low-latency payments ledger with strong consistency guarantees.",
    "Owned the observability stack and cut p99 latency by 40 percent.",
    "Shipped a real-time data pipeline ingesting terabytes per day.",
    "Mentored engineers and drove the platform's reliability roadmap.",
    "Implemented CI/CD and infrastructure-as-code across the org.",
]
# Company pools used by the consulting-lifer penalty and honeypot logic (Phase 2).
_MOCK_CONSULTING = ["TCS", "Infosys", "Wipro", "Accenture", "Cognizant", "Capgemini"]
_MOCK_PRODUCT = ["Google", "Microsoft", "Amazon", "Stripe", "Razorpay", "Flipkart",
                 "Zomato", "Atlassian", "Databricks", "Uber"]


def _mock_employment(rng: random.Random, companies: List[str]) -> List[dict]:
    """Build an employment_history list with per-company tenure (years)."""
    return [{"company": c, "tenure_years": rng.choice([1, 2, 3, 4, 5])}
            for c in companies]


# Longer narrative fragments used only when ``rich=True`` to pad each record's
# ``raw_resume_text`` so the synthetic dataset reaches the real ~465MB scale at
# n=100k (~4.6KB/record). This field is intentionally NOT in TEXT_FIELDS, so it
# bloats the file (stressing streaming + byte-offset seek I/O at true scale)
# without enlarging the embedded text (keeping embedding throughput realistic).
_MOCK_RESUME_BITS = [
    "Led the design and rollout of a fault-tolerant microservices platform serving millions of daily requests.",
    "Owned the end-to-end CI/CD pipeline, cutting mean deployment time from hours to minutes.",
    "Mentored a squad of engineers and ran weekly architecture reviews and brown-bag sessions.",
    "Drove a database sharding migration that reduced p99 read latency by over forty percent.",
    "Built observability tooling (metrics, tracing, structured logs) adopted across the org.",
    "Partnered with product and design to ship a complete checkout redesign ahead of schedule.",
    "Hardened authentication and authorization flows and led the SOC2 readiness effort.",
    "Optimized a hot batch job with vectorized processing, saving substantial monthly compute spend.",
    "Introduced contract tests and a staging gate that sharply reduced production regressions.",
    "Authored the internal RFC process and championed pragmatic, incremental delivery.",
    "Scaled the event-streaming backbone and tuned consumer back-pressure under peak load.",
    "Refactored a legacy monolith into bounded contexts with clear ownership and SLAs.",
]


def generate_mock_data(path: str, n: int = 100, seed: int = 42,
                       rich: bool = False) -> None:
    """Write ``n`` fake JSONL candidate lines to ``path`` for local testing.

    Records use the same field names the real dataset is expected to use so the
    whole pipeline can be exercised before the real file arrives. In addition to
    the embedding fields (``current_title``, ``skills``, ``experience_summary``),
    each record carries the metadata Phase 2 scores on: ``employment_history``,
    ``total_experience_years``, ``current_company_age_years``,
    ``skill_assessment_scores``, ``notice_period_days``, and engagement rates.

    A deterministic mix of *archetypes* is generated (seeded, R7) so every Phase 2
    honeypot and penalty branch is exercised: normal, consulting-lifer, job-hopper,
    long-notice, and the three honeypots (timeline overlap, fake expert, title
    mismatch).
    """
    rng = random.Random(seed)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    # Repeating archetype cycle guarantees several of each within n=100.
    archetypes = (["normal"] * 5 + ["consulting_lifer", "job_hopper", "long_notice",
                  "honeypot_overlap", "honeypot_fake_expert", "honeypot_title_mismatch"])
    with open(path, "w", encoding="utf-8") as f:
        for i in range(n):
            archetype = archetypes[i % len(archetypes)]
            title = rng.choice(_MOCK_TITLES)
            skills = rng.sample(_MOCK_SKILLS, k=rng.randint(3, 8))
            summary = " ".join(rng.sample(_MOCK_SUMMARY_BITS, k=rng.randint(1, 3)))
            n_companies = rng.randint(1, 4)
            companies = rng.sample(_MOCK_PRODUCT, k=min(n_companies, len(_MOCK_PRODUCT)))
            notice = rng.choice([0, 15, 30])
            skill_levels = {s: rng.choice(["beginner", "intermediate", "advanced"])
                            for s in rng.sample(skills, k=min(2, len(skills)))}

            if archetype == "consulting_lifer":
                companies = rng.sample(_MOCK_CONSULTING, k=rng.randint(2, 4))
            elif archetype == "job_hopper":
                companies = rng.sample(_MOCK_PRODUCT, k=4)  # many short stints
            elif archetype == "long_notice":
                notice = rng.choice([60, 90, 120, 150])
            elif archetype == "honeypot_title_mismatch":
                title = rng.choice(["Marketing Manager", "Sales Lead", "HR Partner"])
                skills = skills + rng.sample(_MOCK_AI_SKILLS, k=2)

            employment = _mock_employment(rng, companies)
            if archetype == "job_hopper":
                for e in employment:
                    e["tenure_years"] = 1  # <1.5 avg tenure
            total_exp = sum(e["tenure_years"] for e in employment)

            current_company_age = total_exp + rng.randint(1, 20)  # plausible: age >= tenure
            if archetype == "honeypot_overlap":
                total_exp = current_company_age + rng.randint(2, 8)  # impossible overlap
            elif archetype == "honeypot_fake_expert":
                total_exp = 0  # zero real experience...
                skill_levels[skills[0]] = "expert"  # ...yet claims expert level

            record = {
                ID_FIELD: f"C{i:07d}",
                "current_title": title,
                "skills": skills,
                "experience_summary": summary,
                "total_experience_years": total_exp,
                "current_company_age_years": current_company_age,
                "employment_history": employment,
                "skill_assessment_scores": skill_levels,
                "notice_period_days": notice,
                "redrob_signals": {
                    "recruiter_response_rate": round(rng.uniform(0.2, 1.0), 2),
                    "interview_completion_rate": round(rng.uniform(0.2, 1.0), 2),
                    "github_contribution_score": round(rng.uniform(0.0, 1.0), 2),
                },
            }
            if rich:
                # ~4KB of realistic prose -> pushes each line to the real-dataset
                # scale (~4.6KB) without touching the embedded text fields.
                record["raw_resume_text"] = " ".join(
                    rng.choices(_MOCK_RESUME_BITS, k=40)
                )
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    log(f"mock data written | path={path} records={n}")


# ---------------------------------------------------------------------------
# Input handling: ensure a plain (seekable) JSONL for byte-offset lookups
# ---------------------------------------------------------------------------

def ensure_plain_jsonl(input_path: str, outdir: str) -> str:
    """Return a path to a plain, seekable ``.jsonl``.

    Byte offsets are only meaningful against an uncompressed file, because Pass 2
    needs random ``seek`` access. If the input is gzipped, it is streamed and
    decompressed (never fully loaded) into ``<outdir>/candidates.jsonl`` and that
    path is returned. If the input is already plain JSONL, it is used as-is.
    """
    if input_path.endswith(".gz"):
        plain_path = os.path.join(outdir, PLAIN_JSONL_FILENAME)
        log(f"decompressing gzip -> {plain_path} (streamed)")
        os.makedirs(outdir, exist_ok=True)
        with gzip.open(input_path, "rb") as src, open(plain_path, "wb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)  # 1MB chunks
        return plain_path
    return input_path


# ---------------------------------------------------------------------------
# Core: stream records, build offsets + embedding text
# ---------------------------------------------------------------------------

def _join_nonempty(values: Iterable[object], sep: str = ", ") -> str:
    """Join only the non-empty stringified values (drops None/blank)."""
    out = [str(v).strip() for v in values if v is not None and str(v).strip()]
    return sep.join(out)


def _as_clean_str(value: object) -> str:
    """Stringify a *scalar* field safely.

    Returns "" for ``None`` or container types (dict/list/tuple/set) so a
    malformed value can never crash ``.strip()`` and abort the build.
    """
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return ""
    return str(value).strip()


def build_text(record: dict) -> str:
    """Combine the candidate's semantic fields into one dense string for embedding.

    Reads the REAL nested schema: ``profile.{headline,current_title,current_company,
    current_industry,summary}``, ``skills[].name``, ``career_history[].{title,
    description}`` and ``education[].field_of_study``. Missing fields are skipped so
    we never fabricate content (zero-hallucination ethos, Rules.md R2). The most
    salient fields come first and the result is capped at ``EMBED_MAX_CHARS`` (the
    model truncates to ~256 tokens, so longer input only wastes tokenization CPU).
    """
    profile = record.get("profile")
    if not isinstance(profile, dict):
        profile = {}
    parts: List[str] = []

    headline = _as_clean_str(profile.get("headline"))
    if headline:
        parts.append(headline)

    title = _as_clean_str(profile.get("current_title"))
    company = _as_clean_str(profile.get("current_company"))
    if title or company:
        parts.append(f"{title} at {company}".strip() if company else title)

    industry = _as_clean_str(profile.get("current_industry"))
    if industry:
        parts.append(industry)

    skills = record.get("skills")
    if isinstance(skills, list) and skills:
        names = _join_nonempty(
            s.get("name") if isinstance(s, dict) else s for s in skills)
        if names:
            parts.append("Skills: " + names)

    summary = _as_clean_str(profile.get("summary"))
    if summary:
        parts.append(summary)

    history = record.get("career_history")
    if isinstance(history, list) and history:
        titles = _join_nonempty(
            h.get("title") for h in history if isinstance(h, dict))
        if titles:
            parts.append("Experience: " + titles)
        descs = _join_nonempty(
            (h.get("description") for h in history if isinstance(h, dict)), sep=" ")
        if descs:
            parts.append(descs)

    education = record.get("education")
    if isinstance(education, list) and education:
        fields = _join_nonempty(
            (e.get("field_of_study") or e.get("degree")) for e in education
            if isinstance(e, dict))
        if fields:
            parts.append("Education: " + fields)

    return " | ".join(parts)[:EMBED_MAX_CHARS]


def iter_records_with_offsets(plain_path: str) -> Iterator[Tuple[int, str, str]]:
    """Yield ``(byte_offset, candidate_id, embedding_text)`` per line.

    The file is opened in *binary* mode and iterated line-by-line so the byte
    offset is exact and valid for ``seek`` (text-mode newline translation would
    corrupt offsets). Only one line is held in memory at a time (R1).
    """
    offset = 0
    with open(plain_path, "rb") as f:
        for raw in f:  # streaming iteration - never loads the whole file
            line_len = len(raw)
            stripped = raw.strip()
            if not stripped:
                offset += line_len
                continue
            try:
                record = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                log(f"WARN skipping malformed line at offset={offset}: {exc}")
                offset += line_len
                continue
            try:
                if not isinstance(record, dict):
                    raise TypeError(f"record is {type(record).__name__}, not object")
                cid = record.get(ID_FIELD)
                if cid is None:
                    log(f"WARN skipping line missing '{ID_FIELD}' at offset={offset}")
                    offset += line_len
                    continue
                text = build_text(record)
            except Exception as exc:  # one bad record must never kill the shard
                log(f"WARN skipping unprocessable record at offset={offset}: {exc}")
                offset += line_len
                continue
            yield offset, str(cid), text
            offset += line_len


# ---------------------------------------------------------------------------
# Pre-computation driver
# ---------------------------------------------------------------------------

def precompute(plain_path: str, outdir: str, model_name: str,
               batch_size: int, threads: Optional[int] = None) -> dict:
    """Stream the dataset, embed in batches, and write all Phase 1 artifacts."""
    # Heavy imports are done lazily so --help / mock generation work without them.
    import numpy as np
    import faiss
    from fastembed import TextEmbedding

    os.makedirs(outdir, exist_ok=True)

    # ONNX defaults to a single intra-op thread, which makes large-scale
    # embedding CPU-bound on one core. Use all available cores (R-perf): on this
    # 4-core box this is the difference between ~20min and a few minutes at 100k.
    if threads is None or threads <= 0:
        threads = os.cpu_count() or 1
    log(f"loading model | {model_name} (fastembed / onnx / cpu, threads={threads})")
    model = TextEmbedding(model_name=model_name, threads=threads)

    # The FAISS index is created lazily on the first batch, once the embedding
    # dimension is known directly from the model output.
    index = {"idx": None, "dim": None}
    byte_offsets: Dict[str, int] = {}
    id_map: List[str] = []  # FAISS row order -> candidate_id

    batch_texts: List[str] = []
    total = 0

    def flush_batch() -> None:
        """Encode the buffered texts, normalize, and add to the FAISS index."""
        nonlocal batch_texts
        if not batch_texts:
            return
        # fastembed yields one float32 vector per input document, in order.
        emb = np.asarray(
            list(model.embed(batch_texts, batch_size=batch_size)),
            dtype=np.float32,
        )
        if index["idx"] is None:
            index["dim"] = int(emb.shape[1])
            if index["dim"] != EMBEDDING_DIM:
                log(f"WARN model dim {index['dim']} != expected {EMBEDDING_DIM}")
            index["idx"] = faiss.IndexFlatIP(index["dim"])  # cosine via IP
        faiss.normalize_L2(emb)  # unit vectors -> IndexFlatIP == cosine sim
        index["idx"].add(emb)
        batch_texts = []  # free the batch's text from memory (R1)

    log(f"streaming + embedding | batch_size={batch_size}")
    for offset, cid, text in iter_records_with_offsets(plain_path):
        if cid in byte_offsets:
            log(f"WARN duplicate candidate_id '{cid}' - keeping first occurrence")
            continue
        byte_offsets[cid] = offset
        id_map.append(cid)
        batch_texts.append(text)
        total += 1
        if len(batch_texts) >= batch_size:
            flush_batch()
            if total % (batch_size * 20) == 0:
                ntotal = index["idx"].ntotal if index["idx"] else 0
                log(f"  ...embedded {total} candidates (index.ntotal={ntotal})")
    flush_batch()

    if index["idx"] is None:
        log("ERROR no valid candidates were embedded; nothing to write")
        raise SystemExit(3)  # fail loud, never write empty artifacts (R10)

    faiss_index = index["idx"]
    dim = index["dim"]
    assert faiss_index.ntotal == len(id_map) == len(byte_offsets), (
        f"count mismatch: index={faiss_index.ntotal} id_map={len(id_map)} "
        f"offsets={len(byte_offsets)}"
    )

    # --- Persist artifacts ---
    faiss_path = os.path.join(outdir, FAISS_FILENAME)
    offsets_path = os.path.join(outdir, OFFSETS_FILENAME)
    idmap_path = os.path.join(outdir, IDMAP_FILENAME)
    manifest_path = os.path.join(outdir, MANIFEST_FILENAME)

    faiss.write_index(faiss_index, faiss_path)
    with open(offsets_path, "w", encoding="utf-8") as f:
        json.dump(byte_offsets, f)
    with open(idmap_path, "w", encoding="utf-8") as f:
        json.dump(id_map, f)

    manifest = {
        "model_name": model_name,
        "embedding_backend": "fastembed-onnx-cpu",
        "embedding_dim": dim,
        "count": faiss_index.ntotal,
        "normalized": True,
        "index_type": "IndexFlatIP",
        "text_fields": list(TEXT_FIELDS),
        "id_field": ID_FIELD,
        "plain_jsonl": os.path.abspath(plain_path),
        "artifacts": {
            "faiss": os.path.abspath(faiss_path),
            "byte_offset_index": os.path.abspath(offsets_path),
            "id_map": os.path.abspath(idmap_path),
        },
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    log(f"wrote {faiss_path} | vectors={faiss_index.ntotal} dim={dim}")
    log(f"wrote {offsets_path} | entries={len(byte_offsets)}")
    log(f"wrote {idmap_path} | entries={len(id_map)}")
    log(f"wrote {manifest_path}")
    return manifest


# ---------------------------------------------------------------------------
# Parallel pre-computation (multi-core via subprocess shards)
# ---------------------------------------------------------------------------
# fastembed/onnxruntime is effectively single-core for our short texts (the
# tokenizer dominates), so one process leaves 3 of 4 cores idle. We shard the
# plain file into contiguous byte ranges and embed each in its own OS process
# (true parallelism, no GIL, no fork+onnx issues), then merge in shard order so
# the global FAISS row order / id_map stays deterministic (R7).

def _shard_boundaries(plain_path: str, nshards: int) -> List[Tuple[int, int]]:
    """Split the file into ``nshards`` contiguous [start, end) byte ranges, each
    aligned to a line boundary so no record is split across shards."""
    size = os.path.getsize(plain_path)
    if nshards <= 1 or size == 0:
        return [(0, size)]
    cuts = [0]
    with open(plain_path, "rb") as f:
        for i in range(1, nshards):
            f.seek(size * i // nshards)
            f.readline()  # advance to the start of the next whole line
            pos = f.tell()
            if pos > cuts[-1] and pos < size:
                cuts.append(pos)
    cuts.append(size)
    return [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)]


def precompute_shard(plain_path: str, start: int, end: int, out_prefix: str,
                     model_name: str, batch_size: int,
                     threads: Optional[int]) -> int:
    """Embed records in byte range [start, end) and write ``<out_prefix>.npy``
    (normalized float32 vectors) + ``<out_prefix>.json`` ([abs_offset, id] list,
    in file order). Absolute offsets stay valid against the original plain file."""
    import numpy as np
    import faiss
    from fastembed import TextEmbedding

    if threads is None or threads <= 0:
        threads = 1
    model = TextEmbedding(model_name=model_name, threads=threads)

    meta: List[Tuple[int, str]] = []
    vectors: List["np.ndarray"] = []
    batch_texts: List[str] = []

    def flush() -> None:
        """Embed the buffered batch, L2-normalize it, and append to ``vectors``."""
        nonlocal batch_texts
        if not batch_texts:
            return
        emb = np.asarray(list(model.embed(batch_texts, batch_size=batch_size)),
                         dtype=np.float32)
        faiss.normalize_L2(emb)
        vectors.append(emb)
        batch_texts = []

    with open(plain_path, "rb") as f:
        f.seek(start)
        offset = start
        while offset < end:
            raw = f.readline()
            if not raw:
                break
            line_len = len(raw)
            stripped = raw.strip()
            if stripped:
                try:
                    record = json.loads(raw.decode("utf-8"))
                    cid = record.get(ID_FIELD)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    cid = None
                if cid is not None:
                    meta.append((offset, str(cid)))
                    batch_texts.append(build_text(record))
                    if len(batch_texts) >= batch_size:
                        flush()
            offset += line_len
    flush()

    arr = (np.vstack(vectors) if vectors
           else np.zeros((0, EMBEDDING_DIM), dtype=np.float32))
    np.save(out_prefix + ".npy", arr)
    with open(out_prefix + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f)
    # Completion marker written LAST (after .npy/.json are durable). The resumable
    # driver validates this against the CURRENT byte range + model before reusing a
    # shard, so a stale/partial artifact from an earlier run with different
    # boundaries or a different model is never silently merged.
    with open(out_prefix + ".ok", "w", encoding="utf-8") as f:
        json.dump({"start": start, "end": end, "model": model_name,
                   "count": len(meta)}, f)
    log(f"shard done | range=[{start},{end}) records={len(meta)} -> {out_prefix}.npy")
    return len(meta)


# Bytes per shard. Keeping shards small (≈50 MB) means each subprocess finishes
# in 1-2 min and persists its .npy/.json, so a killed/interrupted run resumes
# instead of restarting from zero. Concurrency (not shard size) drives peak RAM.
SHARD_TARGET_BYTES = 50 * 1024 * 1024

# A shard that exits non-zero (typically -9 / OOM from a transient neighbour
# spike) is re-spawned up to this many times before the run gives up.
MAX_SHARD_TRIES = 4
SHARD_RETRY_COOLDOWN_S = 8.0


def precompute_parallel(plain_path: str, outdir: str, model_name: str,
                        batch_size: int, threads: Optional[int],
                        workers: int, nshards: Optional[int] = None) -> dict:
    """Multi-core driver: fan out byte-range shards to a *bounded pool* of at most
    ``workers`` subprocesses, then merge them (in shard order) into the same
    artifacts ``precompute`` would write.

    Concurrency is capped at ``workers`` because each fastembed/onnxruntime
    subprocess allocates a ~1.4 GB memory arena; 4 at once OOMs a 7.7 GB box
    (SIGKILL/-9). With ``workers=2`` peak RAM stays ≈3 GB (under the 4 GB target).

    Shards already on disk (both ``.npy`` and ``.json`` present) are skipped, so a
    run that was killed mid-way resumes from where it stopped. Merge is always in
    shard index order, so the global FAISS row order / id_map stays deterministic
    (R7) regardless of completion order or resumes.
    """
    import numpy as np
    import faiss

    os.makedirs(outdir, exist_ok=True)
    if nshards is None:
        size = os.path.getsize(plain_path)
        nshards = max(workers, math.ceil(size / SHARD_TARGET_BYTES) if size else 1)
    boundaries = _shard_boundaries(plain_path, nshards)
    nshards = len(boundaries)
    workers = max(1, min(workers, nshards))
    log(f"parallel precompute | workers={workers} shards={nshards}")

    shard_dir = os.path.join(outdir, "_shards")
    os.makedirs(shard_dir, exist_ok=True)
    prefixes = [os.path.join(shard_dir, f"shard_{i}") for i in range(nshards)]

    def _done(i: int) -> bool:
        """True iff shard ``i`` is already on disk AND its ``.ok`` marker matches
        this run's byte range + model (stale/partial shards are redone)."""
        prefix = prefixes[i]
        if not (os.path.exists(prefix + ".npy") and os.path.exists(prefix + ".json")
                and os.path.exists(prefix + ".ok")):
            return False
        # Reuse only if the sidecar marker matches THIS run's range + model; a
        # mismatch (or unreadable marker) means the shard is stale -> redo it.
        try:
            with open(prefix + ".ok", "r", encoding="utf-8") as f:
                ok = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False
        start, end = boundaries[i]
        return (ok.get("start") == start and ok.get("end") == end
                and ok.get("model") == model_name)

    def _spawn(i: int) -> subprocess.Popen:
        """Launch a worker-mode subprocess to embed shard ``i``'s byte range."""
        start, end = boundaries[i]
        argv = [sys.executable, os.path.abspath(__file__),
                "--input", os.path.abspath(plain_path),
                "--shard-start", str(start), "--shard-end", str(end),
                "--shard-out", prefixes[i], "--model", model_name,
                "--batch-size", str(batch_size), "--threads", "1"]
        log(f"  shard {i}/{nshards} -> spawn (bytes {start}-{end})")
        return subprocess.Popen(argv)

    # Bounded pool: keep at most `workers` subprocesses alive at any time.
    pending = [i for i in range(nshards) if not _done(i)]
    skipped = nshards - len(pending)
    if skipped:
        log(f"  resuming: {skipped} shard(s) already on disk, {len(pending)} to do")
    running: Dict[int, subprocess.Popen] = {}
    attempts: Dict[int, int] = {}
    pending.reverse()  # pop() yields ascending shard order
    while pending or running:
        while pending and len(running) < workers:
            i = pending.pop()
            attempts[i] = attempts.get(i, 0) + 1
            running[i] = _spawn(i)
        # Wait for any running shard to finish (poll loop keeps RAM observable).
        done_idx = None
        while done_idx is None:
            for i, p in list(running.items()):
                if p.poll() is not None:
                    done_idx = i
                    break
            if done_idx is None:
                time.sleep(0.5)
        p = running.pop(done_idx)
        rc = p.returncode
        if rc != 0 or not _done(done_idx):
            # Transient OOM (-9) is common when an always-on neighbour process
            # spikes and our ~3GB embedder tips the 8GB cgroup over. Completed
            # shards already persisted, so just retry this one after a short
            # cool-down to let memory recover. Only give up after MAX_SHARD_TRIES.
            if attempts[done_idx] < MAX_SHARD_TRIES:
                log(f"  shard {done_idx} failed (rc={rc}), retry "
                    f"{attempts[done_idx]}/{MAX_SHARD_TRIES} after cool-down")
                time.sleep(SHARD_RETRY_COOLDOWN_S)
                pending.append(done_idx)  # re-spawn when a slot frees
                continue
            for q in running.values():
                q.terminate()
            raise SystemExit(
                f"shard {done_idx} failed with exit code {rc} after "
                f"{attempts[done_idx]} tries (-9 = OOM: lower --workers or free "
                f"RAM). Completed shards are kept for resume."
            )
        log(f"  shard {done_idx} done")

    # Merge in shard order -> deterministic global row order (R7).
    faiss_index = faiss.IndexFlatIP(EMBEDDING_DIM)
    byte_offsets: Dict[str, int] = {}
    id_map: List[str] = []
    for i, prefix in enumerate(prefixes):
        emb = np.load(prefix + ".npy")
        if emb.shape[0]:
            faiss_index.add(emb.astype(np.float32))
        with open(prefix + ".json", "r", encoding="utf-8") as f:
            for offset, cid in json.load(f):
                if cid in byte_offsets:
                    log(f"WARN duplicate candidate_id '{cid}' - keeping first")
                    continue
                byte_offsets[cid] = offset
                id_map.append(cid)

    if faiss_index.ntotal == 0:
        log("ERROR no valid candidates were embedded; nothing to write")
        raise SystemExit(3)
    assert faiss_index.ntotal == len(id_map) == len(byte_offsets), (
        f"count mismatch: index={faiss_index.ntotal} id_map={len(id_map)} "
        f"offsets={len(byte_offsets)}"
    )

    faiss_path = os.path.join(outdir, FAISS_FILENAME)
    offsets_path = os.path.join(outdir, OFFSETS_FILENAME)
    idmap_path = os.path.join(outdir, IDMAP_FILENAME)
    manifest_path = os.path.join(outdir, MANIFEST_FILENAME)

    faiss.write_index(faiss_index, faiss_path)
    with open(offsets_path, "w", encoding="utf-8") as f:
        json.dump(byte_offsets, f)
    with open(idmap_path, "w", encoding="utf-8") as f:
        json.dump(id_map, f)

    manifest = {
        "model_name": model_name,
        "embedding_backend": "fastembed-onnx-cpu",
        "embedding_dim": EMBEDDING_DIM,
        "count": faiss_index.ntotal,
        "normalized": True,
        "index_type": "IndexFlatIP",
        "text_fields": list(TEXT_FIELDS),
        "id_field": ID_FIELD,
        "plain_jsonl": os.path.abspath(plain_path),
        "workers": workers,
        "artifacts": {
            "faiss": os.path.abspath(faiss_path),
            "byte_offset_index": os.path.abspath(offsets_path),
            "id_map": os.path.abspath(idmap_path),
        },
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    shutil.rmtree(shard_dir, ignore_errors=True)
    log(f"wrote {faiss_path} | vectors={faiss_index.ntotal} dim={EMBEDDING_DIM}")
    log(f"wrote {offsets_path} | entries={len(byte_offsets)}")
    log(f"wrote {idmap_path} | entries={len(id_map)}")
    log(f"wrote {manifest_path}")
    return manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: List[str]) -> argparse.Namespace:
    """Parse Phase-1 CLI arguments (input/mock source, model, sharding flags)."""
    p = argparse.ArgumentParser(
        description="Phase 1 - pre-compute embeddings + byte-offset index.",
    )
    p.add_argument("--input", default=None,
                   help="Path to candidates.jsonl or candidates.jsonl.gz")
    p.add_argument("--outdir", default="engine/data",
                   help="Directory for output artifacts (default: engine/data)")
    p.add_argument("--mock", type=int, default=0, metavar="N",
                   help="Generate N mock JSONL records and use them as input")
    p.add_argument("--model", default=DEFAULT_MODEL_NAME,
                   help="fastembed model name (384-dim all-MiniLM-L6-v2 default)")
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                   help="Embedding batch size (bounds peak memory)")
    p.add_argument("--threads", type=int, default=0,
                   help="ONNX intra-op threads (0 = all CPU cores)")
    p.add_argument("--rich", action="store_true",
                   help="pad mock records to real ~4.6KB/record scale (~465MB at 100k)")
    p.add_argument("--workers", type=int, default=1,
                   help="parallel embedding processes (>1 shards across CPU cores)")
    # Internal worker-mode flags (used by precompute_parallel; not for direct use).
    p.add_argument("--shard-start", type=int, default=None, help=argparse.SUPPRESS)
    p.add_argument("--shard-end", type=int, default=None, help=argparse.SUPPRESS)
    p.add_argument("--shard-out", default=None, help=argparse.SUPPRESS)
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    """Phase-1 CLI entrypoint: build artifacts, or embed one shard in worker mode.

    Returns a process exit code (0 on success; non-zero on a fail-loud error
    such as a missing input file, per R10).
    """
    args = parse_args(argv)

    # --- Worker mode: embed one byte-range shard and exit (no artifacts) ---
    if args.shard_out is not None:
        if not args.input or args.shard_start is None or args.shard_end is None:
            log("ERROR shard mode requires --input, --shard-start, --shard-end")
            return 2
        precompute_shard(args.input, args.shard_start, args.shard_end,
                         args.shard_out, args.model, args.batch_size, args.threads)
        return 0

    os.makedirs(args.outdir, exist_ok=True)

    if args.mock > 0:
        mock_path = os.path.join(args.outdir, PLAIN_JSONL_FILENAME)
        generate_mock_data(mock_path, n=args.mock, rich=args.rich)
        input_path = mock_path
    elif args.input:
        if not os.path.exists(args.input):
            log(f"ERROR input not found: {args.input}")
            return 2
        input_path = args.input
    else:
        log("ERROR provide --input <file> or --mock <N>. See --help.")
        return 2

    plain_path = ensure_plain_jsonl(input_path, args.outdir)
    log(f"start precompute | input={input_path} plain={plain_path} outdir={args.outdir}")
    if args.workers and args.workers >= 1:
        precompute_parallel(plain_path, args.outdir, args.model, args.batch_size,
                            threads=args.threads, workers=args.workers)
    else:
        precompute(plain_path, args.outdir, args.model, args.batch_size,
                   threads=args.threads)
    log(f"DONE | total={time.monotonic() - _START:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
