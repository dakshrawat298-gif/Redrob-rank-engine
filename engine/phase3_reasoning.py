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

# Trap / non-technical skill keywords that must NEVER be surfaced as positive
# matches, even when the JD text literally contains them (this JD mentions
# "marketing" and "HR-tech"). Surfacing a candidate's "Marketing"/"HR" skill for
# an AI-engineering role is exactly the keyword trap the dataset warns about, so
# we deny-list them at the source (R2 spirit). JD-archetype-specific by design.
SKILL_DENY_LIST = {
    "marketing", "sales", "hr", "human resources", "recruiting",
    "recruitment", "accounting", "finance",
}


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
# Real-schema accessors (single source of truth for nested field paths, so the
# renderer and the grounding validator can never disagree, Design.md s2 / R2)
# ---------------------------------------------------------------------------

def profile_of(record: dict) -> dict:
    p = record.get("profile")
    return p if isinstance(p, dict) else {}


def signals_of(record: dict) -> dict:
    s = record.get("redrob_signals")
    return s if isinstance(s, dict) else {}


def skill_names(record: dict) -> List[str]:
    """The candidate's declared skill names (real schema: ``skills[].name``)."""
    names: List[str] = []
    for s in record.get("skills") or []:
        name = s.get("name") if isinstance(s, dict) else s
        if name is not None and str(name).strip():
            names.append(str(name).strip())
    return names


def current_title(record: dict):
    return profile_of(record).get("current_title")


def github_score(record: dict) -> Optional[float]:
    """``redrob_signals.github_activity_score`` if it is a *real* score.

    The dataset uses a negative value (e.g. ``-1``) as a "no GitHub data"
    sentinel; we return ``None`` for those so the reasoning never surfaces a
    nonsensical / misleading metric (R2).

    NOTE: the real dataset field is ``github_activity_score``. An external audit
    suggested renaming it to ``github_contribution_score``; that field exists in
    0/2000 sampled records, so the rename is REJECTED -- applying it would null
    out this signal for every candidate.
    """
    v = signals_of(record).get("github_activity_score")
    return float(v) if isinstance(v, (int, float)) and v >= 0 else None


def _total_tenure_months(record: dict) -> Optional[int]:
    hist = record.get("career_history")
    if not isinstance(hist, list):
        return None
    total = 0
    seen = False
    for h in hist:
        dm = h.get("duration_months") if isinstance(h, dict) else None
        if isinstance(dm, (int, float)) and dm >= 0:
            total += int(dm)
            seen = True
    return total if seen else None


def experience_years(record: dict) -> Optional[float]:
    """Total professional experience in years.

    Prefers the candidate's stated ``profile.years_of_experience`` (an explicit,
    grounded field); falls back to summing ``career_history[].duration_months``.
    Used by BOTH the renderer and the digit-grounding validator so the displayed
    number is always traceable to the record (no hallucination, R2).
    """
    yoe = profile_of(record).get("years_of_experience")
    if isinstance(yoe, (int, float)) and yoe >= 0:
        return float(yoe)
    months = _total_tenure_months(record)
    return (months / 12.0) if months is not None else None


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
    return Field(lambda ctx: experience_years(ctx["record"]),
                 lambda v: f"{prefix}{_fmt_years(v)}{suffix}")


def _title(prefix: str = "", suffix: str = "") -> Field:
    return Field(lambda ctx: current_title(ctx["record"]),
                 lambda v: f"{prefix}{str(v).strip()}{suffix}")


def _github(prefix: str = ", GitHub activity ") -> Field:
    return Field(lambda ctx: github_score(ctx["record"]),
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


def _jd_contains_word(skill_lc: str, jd_lc: str) -> bool:
    """True iff ``skill_lc`` appears in the JD as a whole token (not a substring).

    Substring matching is a real bug: skills like "Go" or "Rust" match inside
    unrelated words ("cateGOry", "roBUST"), surfacing skills the JD never actually
    mentions. We require non-alphanumeric boundaries on both sides so only genuine
    whole-word skill mentions count.
    """
    if not skill_lc:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(skill_lc) + r"(?![a-z0-9])"
    return re.search(pattern, jd_lc) is not None


def match_skills(record: dict, jd_text: str) -> List[str]:
    """Return the candidate's OWN skills that also appear in the JD as words.

    Grounded by construction: the result is always a subset of the candidate's
    declared skills (never invented). Two guards keep it honest: (1) whole-word
    matching (no substring false positives like "Go"/"Rust"), and (2) a deny-list
    of trap / non-technical keywords that are dropped even when present in the JD,
    so the reasoning can never cite e.g. "Marketing" as a positive match (R2).
    """
    jd_lower = (jd_text or "").lower()
    out: List[str] = []
    for s_str in skill_names(record):
        s_lc = s_str.lower()
        if s_lc in SKILL_DENY_LIST:
            continue
        if _jd_contains_word(s_lc, jd_lower):
            out.append(s_str)
    return out


def _allowed_digit_tokens(record: dict) -> set:
    """Digit tokens that may legitimately appear in the reasoning."""
    tokens: set = set()
    exp = experience_years(record)
    if isinstance(exp, (int, float)):
        tokens.update(re.findall(r"\d+", _fmt_years(exp)))
    notice = record.get("notice_period_days")
    if notice is None:
        notice = signals_of(record).get("notice_period_days")
    if isinstance(notice, (int, float)):
        tokens.update(re.findall(r"\d+", _fmt_notice(notice)))
    gh = github_score(record)
    if isinstance(gh, (int, float)):
        tokens.update(re.findall(r"\d+", _fmt_github(gh)))
    # Digits inside grounded text the engine may emit verbatim (e.g. a title like
    # "SDE-2" or a skill like "C++20") are legitimate and must not trip the check.
    title = current_title(record)
    if isinstance(title, str):
        tokens.update(re.findall(r"\d+", title))
    for s in skill_names(record):
        tokens.update(re.findall(r"\d+", s))
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
    own = {s.lower() for s in skill_names(record)}
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
