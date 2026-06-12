---
name: Embedding backend choice (fastembed vs sentence-transformers)
description: Why the Redrob Rank Engine embeds with fastembed (ONNX/CPU) instead of sentence-transformers.
---

# Embedding backend

The Phase 1 precompute embeds candidate text with **fastembed** (ONNX runtime, CPU,
no PyTorch) using `sentence-transformers/all-MiniLM-L6-v2` (384-dim).

**Why:** the repo's root `pyproject.toml` (Replit-managed) pins `sentence-transformers`
(and most torch-ecosystem packages) to the explicit `pytorch-cpu` index
(`download.pytorch.org/whl/cpu`), which does NOT host `sentence-transformers`. So
`uv add sentence-transformers` fails with "No solution found / no versions of
sentence-transformers". `numpy`, `faiss-cpu`, and `fastembed` are NOT pinned and install
cleanly. fastembed is also lighter/faster (no torch) which better fits the hackathon's
CPU-only / <=16GB / <=5min constraints.

**How to apply:** if you must use the literal `sentence-transformers` package, remove its
line from `[tool.uv.sources]` in `pyproject.toml` first (torch can stay pinned to
pytorch-cpu). Otherwise prefer fastembed. fastembed downloads the ONNX model from HF Hub on
first use (fine at offline precompute time; not allowed during the no-network ranking stage).

**Runtime footprint / parallelism:** a single fastembed/onnxruntime embedder plateaus at
~3GB RSS within ~18s and stays there regardless of shard size (the ONNX CPU mem-arena, not
our data, dominates — shrinking `batch_size` barely helps). So embedding scale-out is bounded
by RAM, not CPU: at >1 concurrent embedder you exceed the ~8GB sandbox cgroup and get OOM.
The precompute driver is a bounded, resumable shard pool (per-shard `.npy`/`.json` + a `.ok`
sidecar marker that records range+model for stale-artifact detection) with retry-on-OOM;
default workers=1 here. The merge is deterministic (shards merged in index order) and was
validated byte-identical to single-process. See [sandbox-long-jobs](sandbox-long-jobs.md) for
the cgroup limits and why this must run as a workflow, not a `nohup &` background job.
