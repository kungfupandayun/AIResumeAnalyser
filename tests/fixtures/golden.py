from datetime import date

from app.models.job import JobDescription
from app.models.resume import (
    ContactInfo,
    Education,
    Experience,
    Project,
    Resume,
)


def _contact():
    return ContactInfo(email="t@x.com", phone="555-0000", location="SF, CA")


def strong_match():
    """Senior Python engineer applying to a senior Python role — should score high."""
    resume = Resume(
        name="Sam Senior",
        contact=_contact(),
        summary="Senior backend engineer with 8 years building FastAPI services on AWS",
        skills=["Python", "FastAPI", "AWS", "Docker", "PostgreSQL", "Kubernetes"],
        experience=[
            Experience(
                title="Senior Backend Engineer",
                company="BigCo",
                start_date=date(2018, 1, 1),
                end_date=None,
                descriptions=[
                    "Led design of FastAPI microservices serving 10k req/s on AWS",
                    "Managed Docker and Kubernetes deployments for the backend platform",
                    "Mentored junior engineers on backend best practices",
                ],
            ),
        ],
        education=[Education(degree="Bachelor of Science", institution="UC Berkeley")],
        projects=[],
    )
    jd = JobDescription(
        title="Senior Python Engineer",
        description=(
            "We need a senior Python engineer with 5+ years of FastAPI on AWS. "
            "You will build scalable microservices and mentor juniors. "
            "Bachelor's degree required."
        ),
        required_skills=["Python", "FastAPI", "AWS", "Docker", "Kubernetes"],
    )
    return resume, jd


def weak_match():
    """Junior frontend dev applying for a senior backend role — should score low."""
    resume = Resume(
        name="Jamie Junior",
        contact=_contact(),
        summary="Frontend developer who enjoys React and CSS",
        skills=["JavaScript", "React", "CSS"],
        experience=[
            Experience(
                title="Junior Frontend Dev",
                company="SmallCo",
                start_date=date(2024, 1, 1),
                end_date=None,
                descriptions=["Built marketing site components in React"],
            ),
        ],
        education=[Education(degree="Bachelor of Arts", institution="State U")],
        projects=[],
    )
    jd = JobDescription(
        title="Senior Backend Engineer",
        description="5+ years of Python and AWS required. Master's preferred.",
        required_skills=["Python", "AWS", "PostgreSQL"],
    )
    return resume, jd


def no_summary():
    """Resume has no summary field — SummaryAlignmentScorer should produce a no-op."""
    resume, jd = strong_match()
    resume = resume.model_copy(update={"summary": None})
    return resume, jd


def no_years_in_jd():
    """JD doesn't mention years — SeniorityScorer.applies() returns False; weight redistributes."""
    resume, _ = strong_match()
    jd = JobDescription(
        title="Backend Engineer",
        description="Build FastAPI services. Strong team player.",
        required_skills=["Python", "FastAPI"],
    )
    return resume, jd


def rich_jd():
    """JD has rich free-text description — exercises ExperienceScorer thoroughly."""
    resume = Resume(
        name="Pat Pro",
        contact=_contact(),
        summary="Backend engineer with database expertise",
        skills=["Python", "PostgreSQL"],
        experience=[
            Experience(
                title="Engineer",
                company="DataCo",
                start_date=date(2021, 1, 1),
                end_date=None,
                descriptions=[
                    "Tuned PostgreSQL queries for analytics workloads",
                    "Built ETL pipelines in Python with Airflow",
                ],
            ),
        ],
        education=[],
        projects=[],
    )
    jd = JobDescription(
        title="Data Engineer",
        description=(
            "Tune database queries for analytics. "
            "Build ETL pipelines. "
            "Operate Airflow at scale. "
            "Mentor junior data engineers."
        ),
        required_skills=["Python", "PostgreSQL", "Airflow"],
    )
    return resume, jd


ALL_FIXTURES = {
    "strong_match": strong_match,
    "weak_match": weak_match,
    "no_summary": no_summary,
    "no_years_in_jd": no_years_in_jd,
    "rich_jd": rich_jd,
}
