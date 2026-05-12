from pydantic import BaseModel


class ResumeRequest(BaseModel):
    text: str  # raw resume text