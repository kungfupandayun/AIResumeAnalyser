import math
from functools import lru_cache
from typing import Dict, List, Optional, Set

import yaml
from rapidfuzz import fuzz

from core.config import settings
from models.analysis import DimensionScore, Gap
from models.job import JobDescription
from models.resume import Resume
from services.scorers.base import DimensionResult


@lru_cache(maxsize=1)
def load_synonyms() -> Dict[str, List[str]]:
    """Load the synonym dictionary from disk once.

    Hard-fails at first call if the YAML is missing or malformed —
    we want loud failure at startup, not silent skill-matching degradation.
    """
    path = settings.SYNONYMS_PATH
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Synonyms YAML at {path} must be a mapping, got {type(raw).__name__}")
    out: Dict[str, List[str]] = {}
    for canonical, aliases in raw.items():
        if not isinstance(aliases, list):
            raise ValueError(f"Synonyms for '{canonical}' must be a list, got {type(aliases).__name__}")
        out[str(canonical).lower()] = [str(a).lower() for a in aliases]
    return out


def expand_with_synonyms(term: str, syns: Dict[str, List[str]]) -> Set[str]:
    """Return the lowercased term plus all of its synonyms (canonical + aliases)."""
    lowered = term.lower()
    out: Set[str] = {lowered}
    for canonical, aliases in syns.items():
        if lowered == canonical or lowered in aliases:
            out.add(canonical)
            out.update(aliases)
    return out


_FUZZY_THRESHOLD = 85
_EMBED_COSINE_THRESHOLD = 0.80


def _normalize(skill: str) -> str:
    return skill.strip().lower()


def _matches_keyword(jd_skill: str, resume_skills: Set[str], syns: dict) -> bool:
    jd_norm = _normalize(jd_skill)
    jd_expanded = expand_with_synonyms(jd_norm, syns)

    for r in resume_skills:
        r_expanded = expand_with_synonyms(r, syns)
        if jd_expanded & r_expanded:
            return True
        # Fuzzy fallback for typos / spacing differences.
        if fuzz.partial_ratio(jd_norm, r) >= _FUZZY_THRESHOLD:
            return True
    return False


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


class SkillsScorer:
    name = "skills"
    default_weight = 0.35

    def applies(self, jd: JobDescription) -> bool:
        return True

    def score(self, resume: Resume, jd: JobDescription, ai: Optional[object]) -> DimensionResult:
        syns = load_synonyms()
        resume_skills = {_normalize(s) for s in resume.skills}
        required = [s for s in (jd.required_skills or []) if s.strip()]

        if not required:
            # No required skills -> nothing to gap on, perfect score.
            return DimensionResult(
                score=DimensionScore(
                    name=self.name,
                    score=100.0,
                    weight=self.default_weight,
                    rationale="JD lists no required skills",
                ),
                gaps=[],
            )

        unmatched: List[str] = []
        for req in required:
            if _matches_keyword(req, resume_skills, syns):
                continue
            unmatched.append(req)

        # AI path: try to rescue remaining unmatched via embedding similarity.
        ai_fallback = False
        if unmatched and ai is not None:
            try:
                texts = unmatched + list(resume_skills)
                vectors = ai.embed(texts)  # type: ignore[attr-defined]
                jd_vecs = vectors[: len(unmatched)]
                rs_vecs = vectors[len(unmatched):]
                still_unmatched: List[str] = []
                for jd_skill, jvec in zip(unmatched, jd_vecs):
                    if any(_cosine(jvec, rv) >= _EMBED_COSINE_THRESHOLD for rv in rs_vecs):
                        continue
                    still_unmatched.append(jd_skill)
                unmatched = still_unmatched
            except Exception:
                ai_fallback = True  # noqa: F841 — recorded in rationale below

        matched_count = len(required) - len(unmatched)
        score_pct = (matched_count / len(required)) * 100.0
        gaps = [
            Gap(category="skills", item=u, severity="high")
            for u in unmatched
        ]
        rationale = f"{matched_count}/{len(required)} required skills matched"
        if ai_fallback:
            rationale = "[fallback] " + rationale

        return DimensionResult(
            score=DimensionScore(
                name=self.name,
                score=score_pct,
                weight=self.default_weight,
                rationale=rationale,
            ),
            gaps=gaps,
        )
