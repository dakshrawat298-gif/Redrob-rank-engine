---
name: Air-gap offline lock for fastembed
description: Why the ranking offline lock must be conditional on the caller's air-gap, not forced.
---

# Air-gap offline lock (R5)

The ranking stage must make zero network calls (R5). fastembed's `TextEmbedding(...)`
can ping the HF Hub on init even when the model is cached.

**Rule:** in the embedding entrypoint, set `HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE`/
`HF_DATASETS_OFFLINE` **only when the caller already engaged the air-gap**
(detected via `os.environ.get("HF_HUB_OFFLINE") == "1"`, which `run_ranker.py`'s
`network_air_gap` sets before ranking). Always disable telemetry. Under the air-gap,
a missing model fails loud (R10). When NOT air-gapped, do NOT force offline.

**Why:** forcing `HF_HUB_OFFLINE=1` unconditionally makes fastembed pass
`local_files_only=True`, so a first run with an empty cache can never download the
model and aborts. The fastembed cache lives at `/tmp/fastembed_cache`, which is
ephemeral — it gets wiped between sessions, so "the model was cached once" is not a
safe assumption for standalone `phase2_ranker.py` runs.

**How to apply:** the real submission path is `run_ranker.py` = Phase 1 (online,
populates the cache) → ranking (air-gapped, offline + socket guard + isolation
probe). Standalone `phase2_ranker.py` runs online and will re-download/cache the
model if `/tmp` was cleared. Verified: with the model cached, `HF_HUB_OFFLINE=1
python3 engine/phase2_ranker.py ...` loads from cache and produces byte-identical
output to a normal run (satisfies R5's "identical output offline" test).
