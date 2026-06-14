#!/usr/bin/env python3
"""Shared, structured logging configuration for the Redrob Rank Engine.

Every engine module emits its diagnostics through a single namespaced logger
(``redrob``) so progress and timing lines are consistent and, critically, go to
``stderr`` only. ``stdout`` stays reserved for machine-consumable contracts: the
ranked CSV and the validator's ``RESULT: PASS/FAIL`` line. Mixing the two would
corrupt a piped CSV, so the separation is a guardrail, not a style choice.

Usage
-----
    from logging_util import get_logger
    _LOGGER = get_logger("phase2")
    _LOGGER.info("loaded artifacts")

The factory is idempotent: repeated calls never attach duplicate handlers, so
importing several engine modules in one process (e.g. ``run_ranker`` pulling in
both phases) still yields exactly one line per event.
"""
from __future__ import annotations

import logging
import sys

_ROOT_NAME = "redrob"
_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATEFMT = "%H:%M:%S"
_configured = False


def get_logger(name: str = "") -> logging.Logger:
    """Return the shared ``redrob`` logger (or a named child of it).

    On first call this attaches a single ``stderr`` ``StreamHandler`` with a
    consistent format and disables propagation to the root logger (so the host
    application's logging config can never double-print our lines). Subsequent
    calls reuse that handler.

    Args:
        name: Optional sub-component name (e.g. ``"phase2"``). When empty, the
            root ``redrob`` logger itself is returned.

    Returns:
        A ``logging.Logger`` ready to emit to ``stderr`` at ``INFO`` and above.
    """
    global _configured
    root = logging.getLogger(_ROOT_NAME)
    if not _configured:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        root.propagate = False
        _configured = True
    return root.getChild(name) if name else root
