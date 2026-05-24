import json
import logging
from typing import List, Optional

from models.analysis import Gap, Suggestion
from models.job import JobDescription
from models.resume import Resume
from services.scorers.base import DimensionResult

logger = logging.getLogger(__name__)


_REWRITE_PROMPT_SYSTEM = (
    "You are a senior resume coach. You will be given a job description's emphasis "
    "and three of the candidate's existing experience bullets. Suggest one improved "
    "version of each bullet that better aligns with the JD. "
    "CRITICAL RULE: Do not invent facts. Only rephrase or quantify what the user has "
    "already stated. If you cannot rewrite a bullet without invention, set 'suggested' to null. "
    "Output strictly a JSON array of objects, no surrounding prose. Each object has keys: "
    "target_section (string), original (string), suggested (string or null), reason (string)."
)

_PHASE1_TEMPLATES = {
    "skills": {
        "high": "Add '{item}' to your skills section — it's a required skill for this role.",
        "medium": "Consider adding '{item}' to your skills — it appears in the JD's description.",
        "low": "Consider mentioning '{item}' if you have any exposure to it.",
    },
    "experience": {
        "high": "The JD emphasizes '{item}'. None of your experience bullets address this — consider adding or rewriting one to cover it.",
        "medium": "The JD emphasizes '{item}'. Consider rewriting a bullet to highlight relevant work.",
        "low": "The JD mentions '{item}'. Consider whether any of your bullets could be tightened to call it out.",
    },
    "seniority": {
        "high": "{item}. Highlight any contracting, freelance, internship, or pre-degree work that could close the gap.",
        "medium": "{item}. Highlight any contracting or side projects that could close the gap.",
        "low": "{item}. Consider lightly emphasizing relevant early-career work.",
    },
    "education": {
        "high": "{item}. Consider listing relevant graduate coursework, certifications, or equivalent experience.",
        "medium": "{item}. Consider listing relevant coursework or certifications.",
        "low": "{item}. A line of relevant certification could help.",
    },
    "summary_alignment": {
        "high": "Rewrite your summary to lead with the role's key themes.",
        "medium": "Rewrite your summary to lead with the role's key themes.",
        "low": "Lightly adjust your summary to mention one or two of the role's key themes.",
    },
}


def _phase1(gaps: List[Gap]) -> List[Suggestion]:
    out: List[Suggestion] = []
    for g in gaps:
        template = _PHASE1_TEMPLATES.get(g.category, {}).get(g.severity)
        if not template:
            continue
        out.append(Suggestion(
            text=template.format(item=g.item),
            category="gap",
            priority=g.severity,
        ))
    return out


_GAP_SIMILARITY_THRESHOLD = 0.5  # Mirrors ExperienceScorer._GAP_THRESHOLD.


def _select_rewrite_candidates(
    dimension_results: List[DimensionResult],
    limit: int = 3,
) -> List[dict]:
    """From ExperienceScorer metadata, pick the (best-existing-bullet, gap-sentence)
    pairs that are *both* gap-flagged (similarity < threshold) and have the lowest
    similarity. These are the natural rewrite candidates per spec §7 phase 2.
    """
    matches: List[dict] = []
    for r in dimension_results:
        if r.score.name != "experience":
            continue
        sm = r.metadata.get("jd_sentence_matches", [])
        if not sm:
            continue
        weak = [m for m in sm if m.get("similarity", 0.0) < _GAP_SIMILARITY_THRESHOLD]
        weak_sorted = sorted(weak, key=lambda m: m.get("similarity", 0.0))
        matches.extend(weak_sorted)
    return matches[:limit]


def _phase2_rewrites(
    candidates: List[dict],
    jd: JobDescription,
    ai: object,
) -> List[Suggestion]:
    if not candidates:
        return []

    payload_lines = ["JD emphasis:", (jd.description or "")[:1500], "", "Existing bullets:"]
    for c in candidates:
        payload_lines.append(
            f"- target: {c['best_bullet_index']}\n  text: {c['best_bullet_text']}"
        )
    user_payload = "\n".join(payload_lines)

    try:
        raw = ai.complete(  # type: ignore[attr-defined]
            system=_REWRITE_PROMPT_SYSTEM,
            user=user_payload,
            max_tokens=600,
        )
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            return []
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Phase-2 suggestions skipped: %s", e)
        return []

    out: List[Suggestion] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        suggested = item.get("suggested")
        target = item.get("target_section")
        reason = item.get("reason", "")
        if not suggested or not isinstance(suggested, str):
            continue
        text = suggested if not reason else f"{suggested}  (Why: {reason})"
        out.append(Suggestion(
            text=text,
            category="rewrite",
            priority="medium",
            target_section=target if isinstance(target, str) else None,
        ))
    return out


def build_suggestions(
    resume: Resume,
    jd: JobDescription,
    gaps: List[Gap],
    dimension_results: List[DimensionResult],
    ai: Optional[object],
) -> List[Suggestion]:
    """Combine phase-1 templated suggestions with optional phase-2 LLM rewrites."""
    suggestions = _phase1(gaps)

    if ai is not None:
        candidates = _select_rewrite_candidates(dimension_results, limit=3)
        suggestions.extend(_phase2_rewrites(candidates, jd, ai))

    return suggestions
