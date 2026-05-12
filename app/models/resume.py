from pydantic import BaseModel, EmailStr, HttpUrl, Field
from typing import List, Optional, Annotated
from datetime import date

class ContactInfo(BaseModel):
    email: Annotated[EmailStr, Field(description="Valid email address")]
    phone: Annotated[str, Field(description="Phone number", pattern=r"^[0-9\-\+\(\)\s]+$")]
    location: Annotated[str, Field(description="City, State or Country")]
    linkedin: Annotated[Optional[HttpUrl], Field(default=None, description="LinkedIn profile URL")]
    github: Annotated[Optional[HttpUrl], Field(default=None, description="GitHub profile URL")]
    portfolio: Annotated[Optional[HttpUrl], Field(default=None, description="Portfolio website URL")]

class Experience(BaseModel):
    title: Annotated[str, Field(description="Job title", min_length=1)]
    company: Annotated[str, Field(description="Company name", min_length=1)]
    location: Annotated[Optional[str], Field(default=None, description="Work location")]
    start_date: Annotated[date, Field(description="Start date of employment")]
    end_date: Annotated[Optional[date], Field(default=None, description="End date or current position")]
    descriptions: Annotated[List[str], Field(description="List of job responsibilities and achievements", min_length=1)]

class Education(BaseModel):
    degree: Annotated[str, Field(description="Degree name (e.g., Bachelor, Master)", min_length=1)]
    institution: Annotated[str, Field(description="University or institution name", min_length=1)]
    graduation_year: Annotated[Optional[int], Field(default=None, description="Graduation year", ge=1900, le=2100)]
    gpa: Annotated[Optional[float], Field(default=None, description="GPA if applicable", ge=0, le=4)]

class Project(BaseModel):
    name: Annotated[str, Field(description="Project name", min_length=1)]
    tech_stack: Annotated[List[str], Field(description="Technologies used", min_length=1)]
    description: Annotated[str, Field(description="Project description", min_length=1)]
    contributions: Annotated[List[str], Field(description="Your specific contributions", min_length=1)]
    link: Annotated[Optional[HttpUrl], Field(default=None, description="Project repository or demo URL")]


class Resume(BaseModel):
    name: Annotated[str, Field(description="Full name", min_length=1)]
    contact: Annotated[ContactInfo, Field(description="Contact information")]
    summary: Annotated[Optional[str], Field(default=None, description="Professional summary or objective")]
    skills: Annotated[List[str], Field(description="List of technical and soft skills", min_length=1)]
    experience: Annotated[List[Experience], Field(description="Work experience history")]
    education: Annotated[List[Education], Field(description="Educational background")]
    projects: Annotated[Optional[List[Project]], Field(default=[], description="Notable projects")]
