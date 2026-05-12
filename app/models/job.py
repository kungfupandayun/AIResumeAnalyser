from pydantic import BaseModel, Field
from typing import List, Annotated,Optional

# Future job description model definitions
class JobDescription(BaseModel):
    title: Annotated[str, Field(description="Job title", min_length=1)]
    description: Annotated[Optional[str], Field(description="Job description")]
    required_skills: Annotated[Optional[List[str]], Field(description="List of required technical and soft skills")]
