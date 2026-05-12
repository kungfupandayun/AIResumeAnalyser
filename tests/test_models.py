import pytest
from app.models.resume import Resume, ContactInfo, Experience, Education, Project
from datetime import date

class TestResumeModels:
    """Test Pydantic models for data validation"""
    
    def test_contact_info_valid(self):
        """Test ContactInfo model with valid data"""
        contact = ContactInfo(
            email="test@example.com",
            phone="+1-555-1234",
            location="NYC"
        )
        assert contact.email == "test@example.com"
    
    def test_contact_info_invalid_email(self):
        """Test ContactInfo rejects invalid email"""
        with pytest.raises(ValueError):
            ContactInfo(
                email="not-an-email",
                phone="+1-555-1234",
                location="NYC"
            )
    
    def test_experience_model_valid(self):
        """Test Experience model with valid data"""
        exp = Experience(
            title="Engineer",
            company="Tech Co",
            start_date=date(2020, 1, 1),
            descriptions=["Did stuff"]
        )
        assert exp.title == "Engineer"
    
    def test_resume_full_model(self, mock_resume):
        """Test full Resume model"""
        resume = Resume(**mock_resume)
        assert resume.name == "John Doe"
        assert len(resume.skills) > 0
