---
name: Reproducible-output determinism (R7)
description: How to keep the ranker's per-candidate selection byte-reproducible across runs.
---

# Determinism for byte-identical reruns (Rules.md R7)

**Rule:** any per-candidate *selection* logic (picking a fallback phrasing, a
bucket, an index) must use a stable digest, never Python's builtin `hash()`.

**Why:** builtin `hash()` of `str`/`bytes` is salted by `PYTHONHASHSEED`, so it
returns different values across processes — using it for selection makes the
output CSV differ run-to-run and silently violates R7. Confirmed empirically
(builtin hash gave 5 vs 3 buckets across two runs; `hashlib` gave 6/6 stable).

**How to apply:**
- Use `int.from_bytes(hashlib.sha256(s.encode()).digest()[:8], "big")` for index
  selection (see `_stable_hash`/`_fallback_for` in `engine/phase3_reasoning.py`).
- `random.Random(seed)` (Mersenne Twister) IS deterministic for a fixed seed and
  is fine for seeded variation (existing `Choice` node seeds on `candidate_id`).
- Cross-row dedup must walk a deterministic order (final rank order) so it is
  reproducible; never iterate a `set` for logic, only membership-test it.
- Verify by running the ranker twice and `diff`/`md5sum` the two CSVs.
