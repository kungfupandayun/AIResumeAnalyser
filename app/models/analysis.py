from pydantic import BaseModel, Field
from typing import List

class AnalysisResponse(BaseModel):
    match_score: float = Field(..., description="Percentage match (0-100)")
    missing_keywords: List[str] = Field(..., description="Keywords from job description not found in resume")
    suggestions: List[str] = Field(..., description="AI-generated improvement suggestions")
