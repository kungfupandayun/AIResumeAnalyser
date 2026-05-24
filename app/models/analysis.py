from typing import List, Literal, Optional

from pydantic import BaseModel, Field


DimensionName = Literal[
    "skills",
    "experience",
    "education",
    "seniority",
    "summary_alignment",
]


class DimensionScore(BaseModel):
    name: DimensionName
    score: float = Field(..., ge=0, le=100, description="Dimension score 0-100")
    weight: float = Field(..., ge=0, le=1, description="Contribution to overall, after renormalization")
    rationale: str = Field(..., description="One-line explanation of the score")


class Gap(BaseModel):
    category: DimensionName
    item: str = Field(..., description="What is missing/weak (skill name, JD sentence, etc.)")
    severity: Literal["high", "medium", "low"]


class Suggestion(BaseModel):
    text: str
    category: Literal["gap", "rewrite", "structure", "keyword"]
    priority: Literal["high", "medium", "low"]
    target_section: Optional[str] = Field(
        default=None,
        description="Dotted path into the Resume model, e.g. 'experience[0].descriptions[1]'",
    )


class AnalysisResponse(BaseModel):
    mode: Literal["hybrid", "keyword-only"]
    overall_score: float = Field(..., ge=0, le=100, description="Weighted sum of dimension scores")
    dimension_scores: List[DimensionScore]
    gaps: List[Gap]
    suggestions: List[Suggestion]
    warnings: List[str] = Field(default_factory=list)

    # Legacy aliases — kept for one minor release. Drop in v2.
    match_score: float = Field(..., description="DEPRECATED: equals overall_score")
    missing_keywords: List[str] = Field(
        ..., description="DEPRECATED: equals [g.item for g in gaps if g.category == 'skills']"
    )
