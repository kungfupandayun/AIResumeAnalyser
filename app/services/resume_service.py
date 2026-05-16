# Resume analysis business logic

from models.analysis import AnalysisResponse
from models.job import JobDescription
from models.resume import Resume
from services.analyzer import analyze
from utils.parser import extract_email, extract_name, extract_skills


def parse_resume(text: str):
    # Unchanged behavior; bugs in this function are tracked as separate tickets
    # (see spec section 1 non-goals).
    return {
        "name": extract_name(text),
        "email": extract_email(text),
        "skills": extract_skills(text),
    }


def analyze_resume_logic(resume: Resume, job: JobDescription) -> AnalysisResponse:
    return analyze(resume, job)
