import sys
import importlib

import pytest
import hashlib
import json
import math
from typing import List, Optional
from fastapi.testclient import TestClient
from datetime import date


def _seed_app_module_aliases():
    """Pre-seed sys.modules so 'app.X' and 'X' resolve to the same objects.

    pytest.ini sets pythonpath = app, so bare imports ('models.analysis')
    and app-prefixed imports ('app.models.analysis') would create two
    separate module objects with incompatible Pydantic v2 class identities.

    Strategy: import bare modules first, then register them under the
    'app.' namespace in sys.modules before any test-module import can
    create a divergent 'app.' copy.
    """
    bare_prefixes = [
        "models",
        "models.analysis",
        "models.job",
        "models.resume",
        "models.resumeInRawText",
        "services",
        "services.scorers",
        "services.scorers.base",
        "services.scorers.skills",
        "services.scorers.experience",
        "services.scorers.seniority",
        "services.scorers.education",
        "services.scorers.summary",
        "services.ai_client",
        "services.resume_service",
        "core",
        "core.config",
        "utils",
        "data",
    ]
    for bare in bare_prefixes:
        try:
            mod = importlib.import_module(bare)
        except ModuleNotFoundError:
            continue
        app_key = f"app.{bare}"
        sys.modules.setdefault(app_key, mod)


_seed_app_module_aliases()

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


class FakeAIClient:
    """Drop-in replacement for AIClient in tests.

    `embed`: deterministic, hash-based 16-dim unit vectors. Two identical
        strings always get the same vector; different strings get
        different-but-stable vectors. Cosine similarity is well-defined
        and not random, so threshold assertions are stable.
    `complete`: returns a canned response. Tests that need a specific
        response set `canned_completion` on the instance.
    """

    DIM = 16

    def __init__(self):
        self.canned_completion: Optional[str] = None
        self.embed_calls: List[List[str]] = []
        self.complete_calls: List[tuple] = []

    @classmethod
    def _vec(cls, text: str) -> List[float]:
        # SHA256 hash -> DIM floats in [-1, 1], then L2-normalized.
        h = hashlib.sha256(text.lower().encode("utf-8")).digest()
        raw = [(b / 127.5) - 1.0 for b in h[: cls.DIM]]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]

    def embed(self, texts: List[str]) -> List[List[float]]:
        self.embed_calls.append(list(texts))
        return [self._vec(t) for t in texts]

    def complete(self, system: str, user: str, *, max_tokens: int) -> str:
        self.complete_calls.append((system, user, max_tokens))
        if self.canned_completion is not None:
            return self.canned_completion
        # Default canned response is an empty JSON array — safe for
        # the suggestions module's phase-2 parser.
        return json.dumps([])


@pytest.fixture
def fake_ai_client():
    """A fresh FakeAIClient per test (no state leaks across tests)."""
    return FakeAIClient()


@pytest.fixture
def fake_ai_with_completion():
    """Factory: returns a FakeAIClient pre-loaded with a canned completion."""
    def _make(completion: str) -> FakeAIClient:
        c = FakeAIClient()
        c.canned_completion = completion
        return c
    return _make
