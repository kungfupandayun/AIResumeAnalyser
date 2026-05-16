from typing import Any, Dict, List, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from models.analysis import DimensionScore, Gap
from models.job import JobDescription
from models.resume import Resume


class DimensionResult(BaseModel):
    """The output of one scorer.

    `metadata` is intentionally internal — it is NOT included in AnalysisResponse.
    ExperienceScorer uses it to pass the per-JD-sentence similarity matrix to
    the suggestions module without recomputation.
    """

    score: DimensionScore
    gaps: List[Gap]
    metadata: Dict[str, Any] = Field(default_factory=dict)


# We import AIClient lazily inside scorers to avoid a circular import,
# so the Protocol uses `object` for the ai parameter type and each scorer
# narrows it internally.
@runtime_checkable
class Scorer(Protocol):
    name: str  # one of the DimensionName Literals
    default_weight: float

    def applies(self, jd: JobDescription) -> bool:
        """Return False to drop this dimension; weights re-normalize."""
        ...

    def score(self, resume: Resume, jd: JobDescription, ai: object) -> DimensionResult:
        """Compute the dimension. `ai` is `AIClient | None`."""
        ...
