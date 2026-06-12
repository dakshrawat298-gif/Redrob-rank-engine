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
import os
import random
import shutil
import sys
import time
from typing import Dict, Iterator, List, Tuple

# ---------------------------------------------------------------------------
# Configuration constants (single source of truth for this stage)
# ---------------------------------------------------------------------------

# Lightweight, CPU-optimized sentence embedding model (384-dim). See TechSpec.md.
# Served via fastembed (ONNX runtime, CPU, no PyTorch).
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Field names used to build the embedding text. Per the Phase 1 request these are
# `current_title`, `skills`, and `experience_summary`. They are kept here as
# constants so they are trivial to reconcile against the real dataset schema
# (see Schema.md section 2) without touching the logic below.
ID_FIELD = "candidate_id"
TEXT_FIELDS = ("current_title", "skills", "experience_summary")

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
    """Timestamped log line to stderr (keeps stdout clean), per Design.md s3."""
    elapsed = time.monotonic() - _START
    print(f"[{elapsed:7.2f}s] {msg}", file=sys.stderr, flush=True)


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
_MOCK_SUMMARY_BITS = [
    "Built and scaled fault-tolerant services handling millions of requests per day.",
    "Led the migration from a monolith to event-driven microservices.",
    "Designed a low-latency payments ledger with strong consistency guarantees.",
    "Owned the observability stack and cut p99 latency by 40 percent.",
    "Shipped a real-time data pipeline ingesting terabytes per day.",
    "Mentored engineers and drove the platform's reliability roadmap.",
    "Implemented CI/CD and infrastructure-as-code across the org.",
]


def generate_mock_data(path: str, n: int = 100, seed: int = 42) -> None:
    """Write ``n`` fake JSONL candidate lines to ``path`` for local testing.

    The records use the same field names the real dataset is expected to use
    (``candidate_id``, ``current_title``, ``skills``, ``experience_summary``)
    so the rest of the pipeline can be exercised before the real file arrives.
    Deterministic given ``seed`` (R7).
    """
    rng = random.Random(seed)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for i in range(n):
            title = rng.choice(_MOCK_TITLES)
            skills = rng.sample(_MOCK_SKILLS, k=rng.randint(3, 8))
            summary = " ".join(rng.sample(_MOCK_SUMMARY_BITS, k=rng.randint(1, 3)))
            record = {
                ID_FIELD: f"C{i:07d}",
                "current_title": title,
                "skills": skills,
                "experience_summary": summary,
                # A few extra fields the later phases will use (kept realistic).
                "years_experience": rng.randint(1, 18),
                "redrob_signals": {
                    "recruiter_response_rate": round(rng.uniform(0.2, 1.0), 2),
                    "notice_period_days": rng.choice([0, 15, 30, 45, 60, 90]),
                },
            }
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

def build_text(record: dict) -> str:
    """Combine the configured text fields into one dense string per candidate.

    ``current_title`` + ``skills`` + ``experience_summary`` (Phase 1 request).
    Lists (e.g. skills) are joined; missing fields are simply skipped so we never
    fabricate content (consistent with the zero-hallucination ethos, Rules.md R2).
    """
    parts: List[str] = []
    for field in TEXT_FIELDS:
        value = record.get(field)
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            joined = ", ".join(str(v) for v in value if v is not None)
            if joined:
                parts.append(joined)
        else:
            text = str(value).strip()
            if text:
                parts.append(text)
    return " | ".join(parts)


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
            cid = record.get(ID_FIELD)
            if cid is None:
                log(f"WARN skipping line missing '{ID_FIELD}' at offset={offset}")
                offset += line_len
                continue
            yield offset, str(cid), build_text(record)
            offset += line_len


# ---------------------------------------------------------------------------
# Pre-computation driver
# ---------------------------------------------------------------------------

def precompute(plain_path: str, outdir: str, model_name: str,
               batch_size: int) -> dict:
    """Stream the dataset, embed in batches, and write all Phase 1 artifacts."""
    # Heavy imports are done lazily so --help / mock generation work without them.
    import numpy as np
    import faiss
    from fastembed import TextEmbedding

    os.makedirs(outdir, exist_ok=True)

    log(f"loading model | {model_name} (fastembed / onnx / cpu)")
    model = TextEmbedding(model_name=model_name)

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
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: List[str]) -> argparse.Namespace:
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
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    os.makedirs(args.outdir, exist_ok=True)

    if args.mock > 0:
        mock_path = os.path.join(args.outdir, PLAIN_JSONL_FILENAME)
        generate_mock_data(mock_path, n=args.mock)
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
    precompute(plain_path, args.outdir, args.model, args.batch_size)
    log(f"DONE | total={time.monotonic() - _START:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
