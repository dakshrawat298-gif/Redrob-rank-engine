#!/usr/bin/env python3
"""Phase 3 - Dynamic AST templating engine for grounded reasoning.

Generates the ``reasoning`` column for each Top-N candidate WITHOUT any LLM
(hard CPU/RAM/5-min budget, Rules.md R5/R6). Justifications are assembled from a
small Abstract Syntax Tree of template nodes whose leaves bind *directly* to the
candidate's own JSON fields. This makes hallucination structurally impossible
(Rules.md R2): a fact is emitted only if the backing field exists in the record,
and free-text is limited to controlled, tier-appropriate scaffolding.

Design (see Design.md s2):
  * Leaf nodes (``Field`` / ``Skills``) render ONLY from present, non-null fields
    and prune (return ``None``) otherwise.
  * ``Choice`` picks one of several phrasings deterministically per candidate
    (seeded by ``candidate_id``, R7) for natural variation, falling back to the
    next phrasing if the picked one fully prunes.
  * Tone is rank-tiered: ranks 1-20 "exceptional", 21-80 "balanced",
    81-100 explicit "filler".
  * Honest-concern clauses surface red flags (extended notice, job-hopping) so
    the Stage-4 manual rubric is not penalised for hidden risk.
  * A fail-closed grounding validator rejects any output containing a number not
    traceable to the record; on failure a minimal grounded fallback is used.

Surface form: single line, <= 240 chars, no invented skills/values, CSV-quoted
by the writer (Design.md s1.1).
"""

from __future__ import annotations

import random
import re
from typing import Callable, Dict, List, Optional

MAX_CHARS = 240
SKILLS_IN_REASONING = 3          # at most N matched skills named
NOTICE_CONCERN_THRESHOLD = 30    # days; mirrors Phase 2 notice decay


# ---------------------------------------------------------------------------
# Field formatters (single source of truth - render AND validator agree)
# ---------------------------------------------------------------------------

def _fmt_years(v) -> str:
    return f"{int(v)}"


def _fmt_notice(v) -> str:
    return f"{int(v)}"


def _fmt_github(v) -> str:
    return f"{float(v):.2f}"


def _get_path(record: dict, *keys):
    """Nested getter; returns None if any level is missing/non-dict."""
    cur = record
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


# ---------------------------------------------------------------------------
# AST node types
# ---------------------------------------------------------------------------

class Node:
    def render(self, ctx: dict) -> Optional[str]:  # pragma: no cover - interface
        raise NotImplementedError


class Lit(Node):
    """Controlled literal scaffolding (no candidate data)."""

    def __init__(self, text: str):
        self.text = text

    def render(self, ctx: dict) -> Optional[str]:
        return self.text


class Field(Node):
    """Leaf bound to a candidate field. Prunes when the value is absent/empty."""

    def __init__(self, getter: Callable[[dict], object], fmt: Callable[[object], str]):
        self.getter = getter
        self.fmt = fmt

    def render(self, ctx: dict) -> Optional[str]:
        value = self.getter(ctx)
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        try:
            return self.fmt(value)
        except (TypeError, ValueError):
            return None  # never fabricate on a malformed value


class Skills(Node):
    """Named matched skills - strictly a subset of the candidate's own list."""

    def __init__(self, prefix: str = " incl. ", n: int = SKILLS_IN_REASONING):
        self.prefix = prefix
        self.n = n

    def render(self, ctx: dict) -> Optional[str]:
        matched = ctx.get("matched_skills") or []
        chosen = matched[: self.n]
        if not chosen:
            return None
        return self.prefix + ", ".join(chosen)


class Seq(Node):
    """Concatenate children, dropping pruned (None) ones."""

    def __init__(self, children: List[Node], sep: str = ""):
        self.children = children
        self.sep = sep

    def render(self, ctx: dict) -> Optional[str]:
        parts = [c.render(ctx) for c in self.children]
        parts = [p for p in parts if p]
        if not parts:
            return None
        return self.sep.join(parts)


class Choice(Node):
    """Deterministically pick one phrasing per candidate; fall back if pruned."""

    def __init__(self, children: List[Node]):
        self.children = children

    def render(self, ctx: dict) -> Optional[str]:
        n = len(self.children)
        if n == 0:
            return None
        start = ctx["seed"].randrange(n)
        for off in range(n):
            rendered = self.children[(start + off) % n].render(ctx)
            if rendered:
                return rendered
        return None


# ---------------------------------------------------------------------------
# Leaf builders bound to specific candidate fields
# ---------------------------------------------------------------------------

def _years(prefix: str = "", suffix: str = "") -> Field:
    return Field(lambda ctx: ctx["record"].get("total_experience_years"),
                 lambda v: f"{prefix}{_fmt_years(v)}{suffix}")


def _title(prefix: str = "", suffix: str = "") -> Field:
    return Field(lambda ctx: ctx["record"].get("current_title"),
                 lambda v: f"{prefix}{str(v).strip()}{suffix}")


def _github(prefix: str = ", GitHub contribution ") -> Field:
    return Field(lambda ctx: _get_path(ctx["record"], "redrob_signals",
                                       "github_contribution_score"),
                 lambda v: f"{prefix}{_fmt_github(v)}")


# ---------------------------------------------------------------------------
# Tier templates (3-4 phrasings each; last is a field-free safe fallback)
# ---------------------------------------------------------------------------

def _tier_variants() -> Dict[str, Choice]:
    top = Choice([
        Seq([Lit("Exceptional fit: "), _years(suffix="y"), _title(prefix=" as a "),
             Lit(" with strong engagement signals"), Skills(prefix=", incl. ")]),
        Seq([Lit("Top-tier match — "), _years(suffix="y "), _title(),
             Lit(" background; standout engagement"), Skills(prefix=", proven in ")]),
        Seq([Lit("Outstanding candidate: deep "), _title(),
             _years(prefix=" experience (", suffix="y)"),
             Lit(" directly matching the JD"), Skills(prefix=", incl. ")]),
        Seq([Lit("Exceptional fit for this role with strong engagement signals")]),
    ])
    mid = Choice([
        Seq([Lit("Solid "), _title(), Lit(" background matching JD requirements"),
             _years(prefix=", supported by ", suffix="y of experience"),
             Skills(prefix=", incl. ")]),
        Seq([Lit("Good match: "), _years(suffix="y"), _title(prefix=" as a "),
             Skills(prefix=", with relevant skills in ")]),
        Seq([Lit("Relevant "), _title(), _years(prefix=" profile (", suffix="y)"),
             Lit(" aligning with core JD needs"), Skills(prefix=", incl. ")]),
        Seq([Lit("Solid background matching the JD requirements")]),
    ])
    filler = Choice([
        Seq([Lit("Adjacent skills only — likely below cutoff but included as "
                 "final filler given "), _years(suffix="y of experience")]),
        Seq([Lit("Borderline profile: partial overlap with the JD, retained as "
                 "filler ("), _years(suffix="y"), _title(prefix=" as a "), Lit(")")]),
        Seq([Lit("Peripheral match — included to complete the shortlist; "
                 "limited direct JD alignment")]),
        Seq([Lit("Adjacent skills only — likely below cutoff, included as final filler")]),
    ])
    return {"top": top, "mid": mid, "filler": filler}


def _tier_facts() -> Dict[str, Node]:
    """Optional 'specific fact' suffixes per tier (GitHub proof-of-work)."""
    return {"top": _github(), "mid": _github(), "filler": Lit("")}


SAFE_FALLBACK = {
    "top": "Strong overall fit for this role",
    "mid": "Relevant background matching the JD requirements",
    "filler": "Adjacent skills only — likely below cutoff, included as final filler",
}

_VARIANTS = _tier_variants()
_FACTS = _tier_facts()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def tier_of(rank: int) -> str:
    if rank <= 20:
        return "top"
    if rank <= 80:
        return "mid"
    return "filler"


def match_skills(record: dict, jd_text: str) -> List[str]:
    """Return the candidate's OWN skills that also appear in the JD text.

    Grounded by construction: the result is always a subset of the candidate's
    declared skills (never invented), filtered by case-insensitive presence in
    the JD so the reasoning only cites *relevant* matches.
    """
    jd_lower = (jd_text or "").lower()
    out: List[str] = []
    for s in record.get("skills") or []:
        s_str = str(s).strip()
        if s_str and s_str.lower() in jd_lower:
            out.append(s_str)
    return out


def _allowed_digit_tokens(record: dict) -> set:
    """Digit tokens that may legitimately appear in the reasoning."""
    tokens: set = set()
    exp = record.get("total_experience_years")
    if isinstance(exp, (int, float)):
        tokens.update(re.findall(r"\d+", _fmt_years(exp)))
    notice = record.get("notice_period_days")
    if notice is None:
        notice = _get_path(record, "redrob_signals", "notice_period_days")
    if isinstance(notice, (int, float)):
        tokens.update(re.findall(r"\d+", _fmt_notice(notice)))
    gh = _get_path(record, "redrob_signals", "github_contribution_score")
    if isinstance(gh, (int, float)):
        tokens.update(re.findall(r"\d+", _fmt_github(gh)))
    # Digits inside grounded text the engine may emit verbatim (e.g. a title like
    # "SDE-2" or a skill like "C++20") are legitimate and must not trip the check.
    title = record.get("current_title")
    if isinstance(title, str):
        tokens.update(re.findall(r"\d+", title))
    for s in record.get("skills") or []:
        tokens.update(re.findall(r"\d+", str(s)))
    return tokens


def _is_grounded(text: str, record: dict, matched_skills: List[str]) -> bool:
    """Fail-closed traceability check (Design.md s2 / R2).

    Rejects unresolved placeholders and any number not derivable from the record.
    Skills are grounded by construction (``match_skills`` returns a subset).
    """
    if "{" in text or "}" in text:
        return False
    allowed = _allowed_digit_tokens(record)
    for num in re.findall(r"\d+", text):
        if num not in allowed:
            return False
    own = {str(s).strip().lower() for s in (record.get("skills") or [])}
    for s in matched_skills:
        if s.strip().lower() not in own:
            return False
    return True


def _tidy(text: str) -> str:
    """Clean up spacing artifacts left when a mid-sentence leaf prunes."""
    text = re.sub(r"\s+", " ", text)            # collapse runs of whitespace
    text = re.sub(r"\s+([,;.)])", r"\1", text)   # no space before , ; . )
    text = re.sub(r"\(\s+", "(", text)           # no space after (
    text = re.sub(r"(?:,\s*)+([;.)])", r"\1", text)  # drop dangling commas
    return text.strip()


def _concerns(notice_days, hopper_fired: bool) -> str:
    """Honest red-flag clauses appended to the justification."""
    out = ""
    if isinstance(notice_days, (int, float)) and notice_days > NOTICE_CONCERN_THRESHOLD:
        out += f"; however, note the extended notice period of {_fmt_notice(notice_days)} days"
    if hopper_fired:
        out += "; candidate shows frequent job transitions"
    return out


def build_reasoning(record: dict, rank: int, matched_skills: List[str],
                    hopper_fired: bool, notice_days) -> str:
    """Assemble the grounded, tier-appropriate, <=240-char reasoning string."""
    tier = tier_of(rank)
    ctx = {
        "record": record,
        "rank": rank,
        "matched_skills": matched_skills,
        "seed": random.Random(str(record.get("candidate_id", rank))),
    }
    concern = _concerns(notice_days, hopper_fired)

    # Build candidates in priority order (richest -> safest) and pick the first
    # that is both grounded and within the length budget.
    rich = Seq([_VARIANTS[tier], _FACTS[tier]], sep="").render(ctx)
    lean = _VARIANTS[tier].render(ctx)
    candidates = [c for c in (rich, lean) if c]
    candidates.append(SAFE_FALLBACK[tier])

    for base in candidates:
        text = _tidy(base + concern + ".")
        if len(text) <= MAX_CHARS and _is_grounded(text, record, matched_skills):
            return text

    # Last resort: keep the (mandatory) concerns, trim the lead to fit.
    minimal = _tidy(SAFE_FALLBACK[tier] + concern + ".")
    if len(minimal) > MAX_CHARS:
        minimal = minimal[: MAX_CHARS - 1].rstrip() + "."
    return minimal
