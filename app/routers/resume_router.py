from fastapi import APIRouter,HTTPException, status, UploadFile, File
from models.resume import Resume
from models.job import JobDescription
from models.analysis import AnalysisResponse
from models.resumeInRawText import ResumeRequest
from services.resume_service import analyze_resume_logic, parse_resume
from utils.pdfparser import extract_text_from_pdf


# routers package
# Import router instances here if needed
router = APIRouter(prefix="/api/resume", tags=["resume"])

@router.post("/analyze", response_model=AnalysisResponse)
def analyze_resume(resume: Resume, job_description: JobDescription):
    """
    Analyze a resume against a job description.
    
    Returns:
    - match_score: Percentage match (0-100)
    - missing_keywords: Keywords from job description not found in resume
    - suggestions: AI-generated improvement suggestions
    """
    try:
        # Basic validation
        if not resume or not job_description:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resume and job description are required"
            )
        
        return analyze_resume_logic(resume, job_description)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
        
@router.post("/parse")
def parseResumeToJSON(request: str):
    """
        Parse from String to JSON Structured output
    """
    try:
        return parse_resume(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
        


@router.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    content = await file.read()
    text = extract_text_from_pdf(content)
    return parse_resume(text)




