import math
from typing import List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from models.analysis import DimensionScore, Gap
from models.job import JobDescription
from models.resume import Resume
from services.scorers.base import DimensionResult


_GAP_THRESHOLD = 60.0


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


class SummaryAlignmentScorer:
    name = "summary_alignment"
    default_weight = 0.10

    def applies(self, jd: JobDescription) -> bool:
        # applies() can't see the resume; the orchestrator additionally checks
        # `resume.summary is not None` before including this scorer's result
        # in dimension_scores. See Task 15.
        return bool(jd.description and jd.description.strip())

    def score(self, resume: Resume, jd: JobDescription, ai: Optional[object]) -> DimensionResult:
        summary = resume.summary or ""
        jd_desc = (jd.description or "").strip()

        if not summary.strip() or not jd_desc:
            return DimensionResult(
                score=DimensionScore(
                    name=self.name,
                    score=100.0,
                    weight=self.default_weight,
                    rationale="No summary or no JD description (no-op)",
                ),
                gaps=[],
            )

        ai_fallback = False
        score_pct: float = 0.0
        if ai is not None:
            try:
                vecs = ai.embed([summary, jd_desc])  # type: ignore[attr-defined]
                score_pct = max(0.0, min(100.0, _cosine(vecs[0], vecs[1]) * 100.0))
            except Exception:
                ai_fallback = True

        if ai is None or ai_fallback:
            vec = TfidfVectorizer().fit([summary, jd_desc])
            tfidf = vec.transform([summary, jd_desc])
            sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
            score_pct = max(0.0, min(100.0, float(sim) * 100.0))

        gaps: List[Gap] = []
        if score_pct < _GAP_THRESHOLD:
            gaps.append(Gap(
                category="summary_alignment",
                item="Resume summary doesn't strongly align with the role's emphasis",
                severity="low",
            ))

        rationale = f"summary/JD cosine = {score_pct:.0f}"
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
