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
