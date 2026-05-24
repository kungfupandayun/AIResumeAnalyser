import re
from datetime import date
from typing import List, Optional, Tuple

from models.analysis import DimensionScore, Gap
from models.job import JobDescription
from models.resume import Experience, Resume
from services.scorers.base import DimensionResult


# Order matters: ranges first so "3 to 5 years" parses as 5, not 3.
_PATTERNS = [
    re.compile(r"(\d+)\s*(?:-|to)\s*(\d+)\s*(?:\+)?\s*(?:years?|yrs?)", re.IGNORECASE),
    re.compile(r"at\s+least\s+(\d+)\s+(?:years?|yrs?)", re.IGNORECASE),
    re.compile(r"(\d+)\s*\+\s*(?:years?|yrs?)", re.IGNORECASE),
    re.compile(r"(\d+)\s+(?:years?|yrs?)", re.IGNORECASE),
]


def extract_required_years(text: str) -> Optional[int]:
    """Return the largest year value mentioned in the JD text, or None."""
    if not text:
        return None
    values: List[int] = []
    for pat in _PATTERNS:
        for m in pat.finditer(text):
            groups = [g for g in m.groups() if g is not None]
            values.extend(int(g) for g in groups if g.isdigit())
    return max(values) if values else None


def _merge_intervals(intervals: List[Tuple[date, date]]) -> List[Tuple[date, date]]:
    if not intervals:
        return []
    sorted_iv = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_iv[0]]
    for start, end in sorted_iv[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def sum_resume_years(experiences: List[Experience]) -> float:
    intervals: List[Tuple[date, date]] = []
    today = date.today()
    for exp in experiences:
        end = exp.end_date or today
        if end < exp.start_date:
            continue
        intervals.append((exp.start_date, end))
    merged = _merge_intervals(intervals)
    days = sum((e - s).days for s, e in merged)
    return round(days / 365.25, 1)


class SeniorityScorer:
    name = "seniority"
    default_weight = 0.15

    def applies(self, jd: JobDescription) -> bool:
        return extract_required_years(jd.description or "") is not None

    def score(self, resume: Resume, jd: JobDescription, ai: Optional[object]) -> DimensionResult:
        required = extract_required_years(jd.description or "")
        # applies() should have prevented this, but be defensive.
        if required is None:
            return DimensionResult(
                score=DimensionScore(
                    name=self.name,
                    score=100.0,
                    weight=self.default_weight,
                    rationale="No years requirement in JD",
                ),
                gaps=[],
            )

        resume_years = sum_resume_years(resume.experience)
        ratio = min(resume_years / required, 1.0) if required > 0 else 1.0
        score_pct = ratio * 100.0

        gaps: List[Gap] = []
        shortfall = max(0.0, required - resume_years)
        if shortfall >= 1.0:
            if shortfall >= 3.0:
                sev = "high"
            elif shortfall >= 1.5:
                sev = "medium"
            else:
                sev = "low"
            gaps.append(Gap(
                category="seniority",
                item=f"Role asks for {required}+ yrs; resume shows {resume_years} yrs",
                severity=sev,
            ))

        return DimensionResult(
            score=DimensionScore(
                name=self.name,
                score=score_pct,
                weight=self.default_weight,
                rationale=f"{resume_years} yrs vs required {required}",
            ),
            gaps=gaps,
        )
