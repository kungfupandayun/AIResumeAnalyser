import re
from typing import Optional

from models.analysis import DimensionScore, Gap
from models.job import JobDescription
from models.resume import Resume
from services.scorers.base import DimensionResult


# Degree rank — higher number = higher degree.
_RANK_PATTERNS = [
    (4, re.compile(r"\b(phd|ph\.d|doctorate|doctoral)\b", re.IGNORECASE)),
    (3, re.compile(r"\b(master|m\.?s\.?|m\.?a\.?|mba)\b", re.IGNORECASE)),
    (2, re.compile(r"\b(bachelor|b\.?s\.?|b\.?a\.?|undergrad)\b", re.IGNORECASE)),
    (1, re.compile(r"\b(diploma|associate|high school|ged)\b", re.IGNORECASE)),
]

_RANK_NAMES = {0: "no degree", 1: "Diploma", 2: "Bachelor's", 3: "Master's", 4: "PhD"}


def rank_degree(text: str) -> int:
    if not text:
        return 0
    for rank, pat in _RANK_PATTERNS:
        if pat.search(text):
            return rank
    return 0


def _highest_resume_rank(resume: Resume) -> int:
    return max((rank_degree(e.degree) for e in resume.education), default=0)


def _jd_required_rank(jd: JobDescription) -> int:
    return rank_degree(jd.description or "")


class EducationScorer:
    name = "education"
    default_weight = 0.10

    def applies(self, jd: JobDescription) -> bool:
        return _jd_required_rank(jd) > 0

    def score(self, resume: Resume, jd: JobDescription, ai: Optional[object]) -> DimensionResult:
        required_rank = _jd_required_rank(jd)
        resume_rank = _highest_resume_rank(resume)

        if required_rank == 0:
            return DimensionResult(
                score=DimensionScore(
                    name=self.name,
                    score=100.0,
                    weight=self.default_weight,
                    rationale="No degree requirement in JD",
                ),
                gaps=[],
            )

        if resume_rank >= required_rank:
            return DimensionResult(
                score=DimensionScore(
                    name=self.name,
                    score=100.0,
                    weight=self.default_weight,
                    rationale=f"Resume {_RANK_NAMES[resume_rank]} meets/exceeds required {_RANK_NAMES[required_rank]}",
                ),
                gaps=[],
            )

        score_pct = (resume_rank / required_rank) * 100.0
        gap = Gap(
            category="education",
            item=f"Role expects {_RANK_NAMES[required_rank]}; resume shows {_RANK_NAMES[resume_rank]}",
            severity="medium",
        )
        return DimensionResult(
            score=DimensionScore(
                name=self.name,
                score=score_pct,
                weight=self.default_weight,
                rationale=f"Resume {_RANK_NAMES[resume_rank]} below required {_RANK_NAMES[required_rank]}",
            ),
            gaps=[gap],
        )
