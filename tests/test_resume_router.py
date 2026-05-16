import pytest
from fastapi import status

class TestAnalyzeEndpoint:
    """Test suite for resume analysis endpoint"""
    
    def test_analyze_with_valid_resume_and_job(self, client, mock_resume, mock_job_description):
        """Test successful analysis with valid resume and job description"""
        payload = {
            "resume": mock_resume,
            "job_description": mock_job_description
        }
        response = client.post("/api/resume/analyze", json=payload)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "match_score" in data
        assert "missing_keywords" in data
        assert "suggestions" in data
        assert isinstance(data["match_score"], (int, float))
        assert 0 <= data["match_score"] <= 100
        assert isinstance(data["missing_keywords"], list)
        assert isinstance(data["suggestions"], list)
    
    def test_analyze_returns_high_match_score_for_perfect_match(self, client, mock_resume, mock_job_description):
        """When resume.skills == jd.required_skills, the skills dimension scores 100.

        Note: under the holistic analyzer the overall score blends skills with
        experience/seniority/summary/education — so a 'perfect skills match'
        does NOT necessarily yield 95+ overall. We assert skills dimension == 100.
        """
        from fastapi import status
        resume = mock_resume.copy()
        resume["skills"] = mock_job_description["required_skills"]

        payload = {"resume": resume, "job_description": mock_job_description}
        response = client.post("/api/resume/analyze", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        skills_dim = next(
            (d for d in data["dimension_scores"] if d["name"] == "skills"),
            None,
        )
        assert skills_dim is not None
        assert skills_dim["score"] == 100.0
    
    def test_analyze_identifies_missing_keywords(self, client, mock_resume, mock_job_description):
        """Test that missing keywords are correctly identified"""
        payload = {
            "resume": mock_resume,
            "job_description": mock_job_description
        }
        response = client.post("/api/resume/analyze", json=payload)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Check that some keywords are identified as missing or present
        resume_skills_set = set(mock_resume["skills"])
        required_skills_set = set(mock_job_description["required_skills"])
        
        if len(required_skills_set - resume_skills_set) > 0:
            # If there are missing skills, they should be in missing_keywords
            assert len(data["missing_keywords"]) > 0
    
    def test_analyze_provides_suggestions(self, client, mock_resume, mock_job_description):
        """Test that improvement suggestions are generated"""
        payload = {
            "resume": mock_resume,
            "job_description": mock_job_description
        }
        response = client.post("/api/resume/analyze", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["suggestions"]) > 0
        # suggestions are now Suggestion objects with text, category, priority
        assert all(isinstance(s, dict) and "text" in s for s in data["suggestions"])
    
    def test_analyze_with_minimal_resume(self, client, mock_job_description):
        """Test analysis with minimal resume data"""
        minimal_resume = {
            "name": "Jane Smith",
            "contact": {
                "email": "jane@example.com",
                "phone": "555-9999",
                "location": "New York, NY"
            },
            "skills": ["Python"],
            "experience": [],
            "education": []
        }
        
        payload = {
            "resume": minimal_resume,
            "job_description": mock_job_description
        }
        response = client.post("/api/resume/analyze", json=payload)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "match_score" in data
        # Minimal resume should have lower match score
        assert data["match_score"] < 100
    
    def test_analyze_with_empty_job_description(self, client, mock_resume):
        """Test that empty job description is handled"""
        empty_job = {
            "title": "Position",
            "description": "",
            "required_skills": []
        }
        
        payload = {
            "resume": mock_resume,
            "job_description": empty_job
        }
        response = client.post("/api/resume/analyze", json=payload)
        
        # Should either return 400 (invalid input) or 200 with 0 score
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]
    
    def test_analyze_response_schema(self, client, mock_resume, mock_job_description):
        """Test that response follows the expected schema"""
        payload = {
            "resume": mock_resume,
            "job_description": mock_job_description
        }
        response = client.post("/api/resume/analyze", json=payload)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify response structure
        required_fields = ["match_score", "missing_keywords", "suggestions"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify field types
        assert isinstance(data["match_score"], (int, float))
        assert isinstance(data["missing_keywords"], list)
        assert isinstance(data["suggestions"], list)
    
    def test_analyze_with_missing_required_fields(self, client):
        """Test error handling when required fields are missing"""
        # Missing job_description
        payload = {
            "resume": {"name": "Test"}
        }
        response = client.post("/api/resume/analyze", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_analyze_endpoint_exists(self, client):
        """Test that analyze endpoint is accessible"""
        response = client.get("/docs")
        assert response.status_code == status.HTTP_200_OK


class TestResumeValidation:
    """Test resume data validation"""
    
    def test_invalid_email_in_contact(self, client, mock_resume, mock_job_description):
        """Test validation of invalid email"""
        bad_resume = mock_resume.copy()
        bad_resume["contact"]["email"] = "not-an-email"
        
        payload = {
            "resume": bad_resume,
            "job_description": mock_job_description
        }
        response = client.post("/api/resume/analyze", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_missing_required_contact_info(self, client, mock_resume, mock_job_description):
        """Test validation of missing contact info"""
        bad_resume = mock_resume.copy()
        bad_resume["contact"] = {}  # Empty contact
        
        payload = {
            "resume": bad_resume,
            "job_description": mock_job_description
        }
        response = client.post("/api/resume/analyze", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestJobDescriptionValidation:
    """Test job description validation"""
    
    def test_missing_required_job_fields(self, client, mock_resume):
        """Test validation of incomplete job description"""
        incomplete_job = {
            "title": "Position"
            # Missing description and required_skills
        }

        payload = {
            "resume": mock_resume,
            "job_description": incomplete_job
        }
        response = client.post("/api/resume/analyze", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestAnalyzeNewShape:
    """Assertions for the holistic analyzer's new response fields."""

    def test_response_has_mode_field(self, client, mock_resume, mock_job_description):
        from fastapi import status
        payload = {"resume": mock_resume, "job_description": mock_job_description}
        response = client.post("/api/resume/analyze", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["mode"] in ("hybrid", "keyword-only")

    def test_response_has_dimension_scores(self, client, mock_resume, mock_job_description):
        from fastapi import status
        payload = {"resume": mock_resume, "job_description": mock_job_description}
        response = client.post("/api/resume/analyze", json=payload)
        data = response.json()
        assert isinstance(data["dimension_scores"], list)
        assert len(data["dimension_scores"]) >= 1
        for d in data["dimension_scores"]:
            assert d["name"] in (
                "skills", "experience", "education", "seniority", "summary_alignment"
            )
            assert 0 <= d["score"] <= 100
            assert 0 <= d["weight"] <= 1

    def test_dimension_weights_sum_to_one(self, client, mock_resume, mock_job_description):
        from fastapi import status
        payload = {"resume": mock_resume, "job_description": mock_job_description}
        response = client.post("/api/resume/analyze", json=payload)
        data = response.json()
        total = sum(d["weight"] for d in data["dimension_scores"])
        assert abs(total - 1.0) < 1e-3

    def test_gaps_have_required_fields(self, client, mock_resume, mock_job_description):
        from fastapi import status
        # Use a JD with skills the resume lacks to force gaps.
        jd = dict(mock_job_description)
        jd["required_skills"] = mock_job_description["required_skills"] + ["MadeUpSkill"]
        payload = {"resume": mock_resume, "job_description": jd}
        response = client.post("/api/resume/analyze", json=payload)
        data = response.json()
        for g in data["gaps"]:
            assert g["category"] in (
                "skills", "experience", "education", "seniority", "summary_alignment"
            )
            assert g["severity"] in ("high", "medium", "low")
            assert isinstance(g["item"], str) and g["item"]

    def test_legacy_match_score_equals_overall_score(self, client, mock_resume, mock_job_description):
        from fastapi import status
        payload = {"resume": mock_resume, "job_description": mock_job_description}
        response = client.post("/api/resume/analyze", json=payload)
        data = response.json()
        assert data["match_score"] == data["overall_score"]
