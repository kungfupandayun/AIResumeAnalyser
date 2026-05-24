# Resume analysis business logic

from models.analysis import AnalysisResponse
from models.job import JobDescription
from models.resume import Resume
from services.analyzer import analyze
from utils.parser import extract_skills


def parse_resume(text: str):
    # PII (name, email) intentionally not returned — see design spec §3.1.
    # The PDF/parser pipeline gets its own sub-project; that work will re-decide
    # what shape to return without re-introducing PII.
    return {
        "skills": extract_skills(text),
    }


def analyze_resume_logic(resume: Resume, job: JobDescription) -> AnalysisResponse:
    return analyze(resume, job)
