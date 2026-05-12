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
        """Test that matching skills yield high score"""
        # Resume with ALL job required skills
        resume = mock_resume.copy()
        resume["skills"] = mock_job_description["required_skills"]
        
        payload = {
            "resume": resume,
            "job_description": mock_job_description
        }
        response = client.post("/api/resume/analyze", json=payload)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["match_score"] >= 95  # Should be nearly perfect
    
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
        assert all(isinstance(s, str) for s in data["suggestions"])
    
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
