import pytest
from fastapi.testclient import TestClient
from datetime import date

@pytest.fixture
def mock_resume():
    """Mock resume data for testing"""
    return {
        "name": "John Doe",
        "contact": {
            "email": "john.doe@example.com",
            "phone": "+1-555-123-4567",
            "location": "San Francisco, CA",
            "linkedin": "https://linkedin.com/in/johndoe",
            "github": "https://github.com/johndoe",
            "portfolio": "https://johndoe.dev"
        },
        "summary": "Senior Software Engineer with 8+ years of experience in Python, FastAPI, and cloud technologies",
        "skills": [
            "Python", "FastAPI", "AWS", "Docker", "Kubernetes", "PostgreSQL",
            "JavaScript", "React", "Git", "CI/CD", "Microservices", "REST APIs"
        ],
        "experience": [
            {
                "title": "Senior Backend Engineer",
                "company": "Tech Corp",
                "location": "San Francisco, CA",
                "start_date": "2022-01-15",
                "end_date": None,
                "descriptions": [
                    "Led development of scalable microservices using FastAPI",
                    "Managed AWS infrastructure and deployment pipelines",
                    "Mentored junior developers on best practices"
                ]
            },
            {
                "title": "Backend Engineer",
                "company": "StartUp Inc",
                "location": "Remote",
                "start_date": "2019-06-01",
                "end_date": "2021-12-31",
                "descriptions": [
                    "Developed REST APIs using FastAPI and Flask",
                    "Implemented Docker containerization for microservices",
                    "Set up CI/CD pipelines using GitHub Actions"
                ]
            }
        ],
        "education": [
            {
                "degree": "Bachelor of Science",
                "institution": "University of California",
                "graduation_year": 2019,
                "gpa": 3.8
            }
        ],
        "projects": [
            {
                "name": "AI Resume Analyzer",
                "tech_stack": ["Python", "FastAPI", "spaCy", "OpenAI"],
                "description": "Tool that analyzes resumes against job descriptions",
                "contributions": [
                    "Designed architecture for text processing pipeline",
                    "Implemented keyword matching algorithm",
                    "Integrated OpenAI API for suggestion generation"
                ],
                "link": "https://github.com/johndoe/ai-resume-analyzer"
            }
        ]
    }

@pytest.fixture
def mock_job_description():
    """Mock job description for testing"""
    return {
        "title": "Senior Python Developer",
        "description": "We are looking for a Senior Python Developer with 5+ years of experience in FastAPI and AWS. You will be responsible for building scalable backend systems, leading architectural decisions, and mentoring junior developers.",
        "required_skills": [
            "Python",
            "FastAPI",
            "AWS",
            "Docker",
            "PostgreSQL",
            "Kubernetes",
            "REST APIs",
            "Microservices",
            "CI/CD"
        ]
    }

@pytest.fixture
def client():
    """Create a test client"""
    from app.main import app
    return TestClient(app)
