"""Workspace entrypoint placeholder.

The Redrob Rank Engine is driven through the modules under ``engine/`` (run the
full pipeline with ``python engine/run_ranker.py`` or rank from existing
artifacts with ``python engine/phase2_ranker.py``). This stub exists only so the
repository root has a conventional, importable entrypoint.
"""
from __future__ import annotations


def main() -> None:
    """Print a short pointer to the real engine entrypoints."""
    print("Redrob Rank Engine — run `python engine/run_ranker.py --help` to start.")


if __name__ == "__main__":
    main()
