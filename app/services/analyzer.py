from typing import Dict, List

from models.analysis import AnalysisResponse, Gap
from models.job import JobDescription
from models.resume import Resume
from services.ai_client import get_ai_client
from services.scorers import REGISTRY
from services.scorers.base import DimensionResult
from services.suggestions import build_suggestions


def _renormalize(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return {k: 0.0 for k in weights}
    return {k: v / total for k, v in weights.items()}


def _scorer_applies_with_resume(scorer, resume: Resume, jd: JobDescription) -> bool:
    """Apply Scorer.applies(jd) plus dimension-specific resume checks.

    SummaryAlignmentScorer.applies takes only the JD, so the orchestrator
    handles the resume.summary-is-None check here to avoid leaking resume
    knowledge into every applies() method.
    """
    if not scorer.applies(jd):
        return False
    if scorer.name == "summary_alignment" and not (resume.summary and resume.summary.strip()):
        return False
    return True


def analyze(resume: Resume, jd: JobDescription) -> AnalysisResponse:
    ai = get_ai_client()
    warnings: List[str] = []

    active = [s for s in REGISTRY if _scorer_applies_with_resume(s, resume, jd)]
    weights = _renormalize({s.name: s.default_weight for s in active})

    results: List[DimensionResult] = []
    any_ai_used = False
    for scorer in active:
        result = scorer.score(resume, jd, ai)
        if ai is not None:
            if result.score.rationale.startswith("[fallback]"):
                warnings.append(f"{scorer.name} fell back to keyword-only")
            else:
                any_ai_used = True
        # Apply re-normalized weight onto the DimensionScore.
        result.score.weight = weights[scorer.name]
        results.append(result)

    if ai is None:
        mode = "keyword-only"
    elif not any_ai_used:
        # Every AI-using scorer fell back; effectively keyword-only.
        mode = "keyword-only"
    else:
        mode = "hybrid"

    overall = sum(r.score.score * r.score.weight for r in results)
    all_gaps: List[Gap] = [g for r in results for g in r.gaps]
    suggestions = build_suggestions(resume, jd, all_gaps, results, ai)

    return AnalysisResponse(
        mode=mode,
        overall_score=round(overall, 2),
        dimension_scores=[r.score for r in results],
        gaps=all_gaps,
        suggestions=suggestions,
        warnings=warnings,
        # Legacy aliases:
        match_score=round(overall, 2),
        missing_keywords=[g.item for g in all_gaps if g.category == "skills"],
    )
