# Resume analysis business logic

from models.resume import Resume
from models.job import JobDescription
from models.analysis import AnalysisResponse
from utils.parser  import extract_email,extract_name,extract_skills


def parse_resume(text: str):
    return {
        "name": extract_name(text),
        "email": extract_email(text),
        "skills": extract_skills(text)
    }

def analyze_resume_logic(resume: Resume, job: JobDescription) -> AnalysisResponse:
    resume_skills = set(s.lower() for s in resume.skills)
    required_skills = set(s.lower() for s in job.required_skills)
    
    # Calculate match score
    if not required_skills:
        match_score = 0.0
    else:
        matched = len(resume_skills & required_skills)
        match_score = (matched / len(required_skills)) * 100
    
    # Find missing keywords
    missing = list(required_skills - resume_skills)
    
    # Generate suggestions (placeholder)
    suggestions = []
    if missing:
        suggestions.append(f"Add these skills to your resume: {', '.join(list(missing)[:3])}")
    
    suggestions.append("Highlight your relevant experience in the description")
    suggestions.append("Quantify your achievements with metrics")
    
    return AnalysisResponse(
        match_score=match_score,
        missing_keywords=missing,
        suggestions=suggestions
    )
