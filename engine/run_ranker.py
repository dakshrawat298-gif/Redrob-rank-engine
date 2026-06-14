#!/usr/bin/env python3
"""Redrob Rank Engine - final CLI entrypoint (Phase 4).

Runs the full pipeline end to end in a SINGLE process so a single peak-RAM
number covers everything:

    Stage 0  (optional)  generate a mock dataset
    Stage 1  PRECOMPUTE  Phase 1 - stream JSONL -> embeddings + FAISS + offsets
    Stage 2  RANK        Phase 2/3 - two-pass recall + behavioral re-rank + reasoning

The ranking stage is the part that must obey the hackathon sandbox constraints
(CPU-only, <=16GB RAM, <=5min, NO network - Rules.md R1/R3/R8). To prove the
air-gap, ``--network-off`` (or ``NETWORK_OFF=1``) installs a process-wide block
on all outbound socket connections for the duration of ranking; the model is
loaded from the local fastembed cache that Stage 1 populated while online.

Profiling uses only the stdlib ``resource`` module (no extra dependency):
peak RSS via ``ru_maxrss`` (process-lifetime peak) and user+system CPU seconds,
plus wall-clock per stage via ``time.monotonic``.

Examples
--------
    # 100k stress test, offline ranking, rich ~465MB dataset:
    python3 engine/run_ranker.py --mock 100000 --rich-mock --network-off \
        --out engine/data/team_xxx.csv

    # Real dataset:
    python3 engine/run_ranker.py --input candidates.jsonl.gz \
        --jd-file jd.txt --network-off --out team_xxx.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import resource
import socket
import sys
import time
from contextlib import contextmanager
from typing import Iterator, List, Optional, Tuple

# Make the sibling phase modules importable whether run as a script
# (`python3 engine/run_ranker.py`) or as a module.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import phase1_precompute as p1  # noqa: E402
import phase2_ranker as p2      # noqa: E402
from logging_util import get_logger  # noqa: E402

_LOGGER = get_logger("run_ranker")


# ---------------------------------------------------------------------------
# Logging / formatting helpers
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    """Emit an orchestration progress line via the shared logger (stderr).

    ``ERROR``/``WARN``-prefixed messages map to the matching level. The
    human-facing resource report (``_rule`` banners + the RESOURCE PROFILE table)
    intentionally stays on stdout — it is the deliverable benchmark output.
    """
    if msg.startswith("ERROR"):
        _LOGGER.error(msg)
    elif msg.startswith("WARN"):
        _LOGGER.warning(msg)
    else:
        _LOGGER.info(msg)


def _rule(title: str) -> None:
    """Print a titled separator banner to stdout (part of the human report)."""
    print("\n" + "=" * 72, flush=True)
    print(f"  {title}", flush=True)
    print("=" * 72, flush=True)


def _rusage_peak_mb() -> Tuple[float, float]:
    """Peak RSS (MB) for this process and for its reaped children, separately.

    ``ru_maxrss`` is kilobytes on Linux (bytes on macOS); we assume Linux. Stage 1
    embedding now runs in SUBPROCESSES, so the true peak lives in RUSAGE_CHILDREN
    (which reports the max maxrss across all reaped children, not the parent). We
    must read both or we under-report peak RAM and emit a misleading verdict.
    """
    self_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    child_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024.0
    return self_mb, child_mb


def _peak_rss_mb() -> float:
    """Overall peak RSS (MB): the larger of this process and any child."""
    self_mb, child_mb = _rusage_peak_mb()
    return max(self_mb, child_mb)


def _cpu_seconds() -> float:
    """User+system CPU seconds, including reaped embedding subprocesses."""
    s = resource.getrusage(resource.RUSAGE_SELF)
    c = resource.getrusage(resource.RUSAGE_CHILDREN)
    return s.ru_utime + s.ru_stime + c.ru_utime + c.ru_stime


# ---------------------------------------------------------------------------
# Strict network isolation (Stage 3 air-gap simulation, Rules.md R3/R8)
# ---------------------------------------------------------------------------

class NetworkBlocked(OSError):
    """Raised when code attempts an outbound connection while the air-gap is on."""


_LOOPBACK = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}


@contextmanager
def network_air_gap(enabled: bool) -> Iterator[None]:
    """Block ALL non-loopback outbound socket connections while active.

    Implemented by monkeypatching ``socket.socket.connect`` and
    ``socket.create_connection``. Loopback is allowed so any in-process local
    IPC keeps working; everything else raises ``NetworkBlocked``. We also flip
    the HuggingFace/Transformers offline switches so the embedding backend reads
    purely from its local cache instead of phoning home (which would otherwise
    hit the block and abort the model load).
    """
    if not enabled:
        yield
        return

    real_connect = socket.socket.connect
    real_create = socket.create_connection
    prev_env = {k: os.environ.get(k) for k in
                ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE")}

    def _host_of(address: object) -> Optional[str]:
        """Extract the host string from a socket address tuple, else None."""
        if isinstance(address, tuple) and address:
            return str(address[0])
        return None

    def guarded_connect(self: socket.socket, address: object) -> object:
        """``socket.connect`` replacement: allow loopback, block everything else."""
        host = _host_of(address)
        if host is None or host in _LOOPBACK:
            return real_connect(self, address)
        raise NetworkBlocked(f"outbound network blocked (air-gap): {address}")

    def guarded_create(address: object, *args: object, **kwargs: object) -> object:
        """``create_connection`` replacement: block any non-loopback target."""
        host = _host_of(address)
        if host is not None and host not in _LOOPBACK:
            raise NetworkBlocked(f"outbound network blocked (air-gap): {address}")
        return real_create(address, *args, **kwargs)

    socket.socket.connect = guarded_connect          # type: ignore[assignment]
    socket.create_connection = guarded_create        # type: ignore[assignment]
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    log("NETWORK AIR-GAP ENGAGED - all non-loopback outbound connections blocked")
    try:
        yield
    finally:
        socket.socket.connect = real_connect          # type: ignore[assignment]
        socket.create_connection = real_create        # type: ignore[assignment]
        for k, v in prev_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        log("network air-gap lifted")


def prove_isolation() -> bool:
    """Best-effort proof the air-gap is real: try to reach a public host and
    confirm the attempt is refused. Returns True if outbound was blocked."""
    import urllib.request
    try:
        urllib.request.urlopen("http://example.com", timeout=4)  # noqa: S310
        log("ISOLATION CHECK: FAILED - an outbound request unexpectedly succeeded")
        return False
    except NetworkBlocked as exc:
        log(f"ISOLATION CHECK: PASSED - outbound blocked at socket layer ({exc})")
        return True
    except Exception as exc:  # noqa: BLE001 - any failure means no connection made
        log(f"ISOLATION CHECK: PASSED - no outbound connection ({type(exc).__name__})")
        return True


# ---------------------------------------------------------------------------
# CSV preview
# ---------------------------------------------------------------------------

def preview_csv(path: str, n: int = 5) -> None:
    """Print the top and bottom ``n`` rows of a ranked CSV to stdout (a report)."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        log(f"WARN no rows in {path}")
        return
    score_col = "final_score" if "final_score" in rows[0] else "score"

    def show(label: str, subset: List[dict]) -> None:
        """Print one labelled block of preview rows under a rule banner."""
        _rule(label)
        for r in subset:
            rank = r.get("rank", "?")
            cid = r.get("candidate_id", "?")
            score = r.get(score_col, "?")
            reason = (r.get("reasoning") or "")
            print(f"  #{rank:<4} {cid:<12} score={score}", flush=True)
            print(f"        {reason}", flush=True)

    show(f"TOP {n}", rows[:n])
    show(f"BOTTOM {n}", rows[-n:])
    print(flush=True)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> int:
    """Run the full pipeline (optional mock → precompute → rank) with profiling.

    Returns a process exit code: 0 on success, or non-zero on a fail-loud error
    (missing input, failed isolation probe, or a non-zero ranking stage, per R10).
    """
    t_start = time.monotonic()
    os.makedirs(args.artifacts, exist_ok=True)

    # --- Stage 0: optional mock generation ---
    if args.mock > 0:
        mock_path = os.path.join(args.artifacts, p1.PLAIN_JSONL_FILENAME)
        _rule(f"STAGE 0 - generate mock data (n={args.mock}, rich={args.rich_mock})")
        t0 = time.monotonic()
        p1.generate_mock_data(mock_path, n=args.mock, rich=args.rich_mock)
        size_mb = os.path.getsize(mock_path) / (1024 * 1024)
        log(f"mock dataset: {size_mb:.1f} MB at {mock_path} "
            f"({time.monotonic() - t0:.2f}s)")
        input_path = mock_path
    elif args.input:
        if not os.path.exists(args.input):
            log(f"ERROR input not found: {args.input}")
            return 2
        input_path = args.input
    else:
        log("ERROR provide --input <file> or --mock <N>. See --help.")
        return 2

    # --- Stage 1: precompute (network ALLOWED: may download model on first use) ---
    _rule("STAGE 1 - PRECOMPUTE (embeddings + FAISS + byte-offset index)")
    t_pre = time.monotonic()
    plain_path = p1.ensure_plain_jsonl(input_path, args.artifacts)
    if args.workers and args.workers >= 1:
        log(f"embedding via resumable shard pool | workers={args.workers}")
        p1.precompute_parallel(plain_path, args.artifacts, args.model,
                               args.batch_size, threads=args.threads,
                               workers=args.workers)
    else:
        p1.precompute(plain_path, args.artifacts, args.model, args.batch_size,
                      threads=args.threads)
    precompute_s = time.monotonic() - t_pre
    log(f"precompute wall-clock: {precompute_s:.2f}s")

    # --- Stage 2/3: ranking + reasoning (network OFF if requested) ---
    _rule("STAGE 2/3 - RANK + REASONING"
          + (" [AIR-GAPPED]" if args.network_off else ""))
    t_rank = time.monotonic()
    rank_argv = ["--artifacts", args.artifacts, "--out", args.out,
                 "--k", str(args.k), "--top-n", str(args.top_n)]
    if args.jd_file:
        rank_argv += ["--jd-file", args.jd_file]
    elif args.jd:
        rank_argv += ["--jd", args.jd]

    with network_air_gap(args.network_off):
        if args.network_off and not prove_isolation():
            log("ERROR air-gap requested but isolation probe FAILED - an outbound "
                "request unexpectedly succeeded; aborting before ranking (fail-closed)")
            return 4
        rc = p2.main(rank_argv)
    rank_s = time.monotonic() - t_rank
    log(f"ranking wall-clock: {rank_s:.2f}s")
    if rc != 0:
        log(f"ERROR ranking stage returned {rc}")
        return rc

    # --- Verification: CSV preview + resource report ---
    preview_csv(args.out, n=5)

    total_s = time.monotonic() - t_start
    self_peak_mb, child_peak_mb = _rusage_peak_mb()
    peak_mb = max(self_peak_mb, child_peak_mb)
    cpu_s = _cpu_seconds()

    _rule("RESOURCE PROFILE")
    print(f"  dataset records     : {args.mock if args.mock else '(file)'}", flush=True)
    print(f"  output CSV          : {args.out}", flush=True)
    print(f"  network air-gap     : {'ON' if args.network_off else 'off'}", flush=True)
    print("  " + "-" * 50, flush=True)
    print(f"  Stage 1 precompute  : {precompute_s:8.2f} s  (wall)", flush=True)
    print(f"  Stage 2/3 ranking   : {rank_s:8.2f} s  (wall)   <- 5-min budget", flush=True)
    print(f"  TOTAL wall-clock    : {total_s:8.2f} s", flush=True)
    print(f"  TOTAL CPU time      : {cpu_s:8.2f} s  (user+sys, incl. children)", flush=True)
    print(f"  PEAK RAM ranking    : {self_peak_mb:8.1f} MB  (parent process)", flush=True)
    print(f"  PEAK RAM embedder   : {child_peak_mb:8.1f} MB  (Stage 1 subprocess)", flush=True)
    print(f"  PEAK RAM overall    : {peak_mb:8.1f} MB  ({peak_mb / 1024:.2f} GB)"
          f"   <- 16GB budget", flush=True)
    print("=" * 72, flush=True)

    # --- Verdict against the stated targets ---
    ram_ok = peak_mb < 4096          # user target: < 4 GB
    rank_budget_ok = rank_s < 300    # hard constraint: ranking < 5 min
    total_ok = total_s < 120         # user stretch target: full pipeline < 2 min
    log(f"VERDICT: ranking<5min={'YES' if rank_budget_ok else 'NO'} | "
        f"RAM<4GB={'YES' if ram_ok else 'NO'} | "
        f"total<2min={'YES' if total_ok else 'NO'}")
    return 0


def parse_args(argv: List[str]) -> argparse.Namespace:
    """Parse the full-pipeline runner's CLI arguments (input, JD, tuning, sandbox)."""
    p = argparse.ArgumentParser(
        description="Redrob Rank Engine - full pipeline runner with profiling.",
    )
    src = p.add_argument_group("input")
    src.add_argument("--input", default=None,
                     help="candidates.jsonl or .jsonl.gz (real dataset)")
    src.add_argument("--mock", type=int, default=0, metavar="N",
                     help="generate N synthetic candidates instead of --input")
    src.add_argument("--rich-mock", action="store_true",
                     help="pad mock records to real ~4.6KB/record scale (~465MB at 100k)")

    jd = p.add_argument_group("job description")
    jd.add_argument("--jd", default=None, help="JD text inline")
    jd.add_argument("--jd-file", default=None, help="path to a JD text file")

    out = p.add_argument_group("output / tuning")
    out.add_argument("--artifacts", default="engine/data",
                     help="working dir for Phase 1 artifacts (default: engine/data)")
    out.add_argument("--out", default="engine/data/ranked.csv",
                     help="final ranked CSV path")
    out.add_argument("--k", type=int, default=p2.RECALL_K, help="Pass-1 recall size")
    out.add_argument("--top-n", type=int, default=p2.TOP_N, help="final output size")
    out.add_argument("--model", default=p1.DEFAULT_MODEL_NAME,
                     help="fastembed model name")
    out.add_argument("--batch-size", type=int, default=p1.DEFAULT_BATCH_SIZE,
                     help="embedding batch size (bounds peak memory)")
    out.add_argument("--threads", type=int, default=1,
                     help="ONNX intra-op threads per embedding process")
    out.add_argument("--workers", type=int, default=1,
                     help="parallel embedding processes (default: 1, the only safe "
                          "config on a ~8GB cgroup shared with other services). Each "
                          "onnxruntime embedder plateaus ~3GB RAM; >1 risks OOM here. "
                          "Raise on a 16GB+ box with spare headroom.")

    sandbox = p.add_argument_group("sandbox")
    sandbox.add_argument("--network-off", action="store_true",
                         default=os.environ.get("NETWORK_OFF") == "1",
                         help="block all outbound network during ranking "
                              "(or set NETWORK_OFF=1)")
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    """CLI entrypoint: parse args and run the full pipeline; returns an exit code."""
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
