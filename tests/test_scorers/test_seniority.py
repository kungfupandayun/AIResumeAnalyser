from datetime import date

import pytest

from app.models.job import JobDescription
from app.models.resume import Resume, ContactInfo, Experience
from app.services.scorers.seniority import (
    SeniorityScorer,
    extract_required_years,
    sum_resume_years,
)


def _resume_with_experience(experiences):
    return Resume(
        name="T",
        contact=ContactInfo(email="t@x.com", phone="5", location="X"),
        skills=["Python"],
        experience=experiences,
        education=[],
        projects=[],
    )


def _exp(title, start, end):
    return Experience(title=title, company="C", start_date=start, end_date=end, descriptions=["x"])


class TestExtractRequiredYears:
    @pytest.mark.parametrize("text, expected", [
        ("We need 5+ years of Python", 5),
        ("5 years of experience required", 5),
        ("at least 3 years in backend", 3),
        ("3 to 5 years in industry", 5),
        ("10+ yrs of leadership", 10),
        ("5-7 years experience", 7),
    ])
    def test_extracts(self, text, expected):
        assert extract_required_years(text) == expected

    def test_returns_none_when_no_match(self):
        assert extract_required_years("strong communicator with passion") is None

    def test_takes_largest_when_multiple_matches(self):
        assert extract_required_years("3+ years backend, 5+ years cloud") == 5


class TestSumResumeYears:
    def test_simple_three_years(self):
        years = sum_resume_years([_exp("E", date(2020, 1, 1), date(2023, 1, 1))])
        assert 2.9 <= years <= 3.1

    def test_overlapping_intervals_merged(self):
        # Two overlapping 2-year intervals should sum to ~3 years, not 4.
        e1 = _exp("E1", date(2020, 1, 1), date(2022, 1, 1))
        e2 = _exp("E2", date(2021, 1, 1), date(2023, 1, 1))
        years = sum_resume_years([e1, e2])
        assert 2.9 <= years <= 3.1

    def test_current_job_uses_today(self):
        # 2 years ago to now → ~2 years.
        two_yrs_ago = date(date.today().year - 2, date.today().month, date.today().day)
        years = sum_resume_years([_exp("E", two_yrs_ago, None)])
        assert 1.9 <= years <= 2.1

    def test_empty_returns_zero(self):
        assert sum_resume_years([]) == 0.0


class TestSeniorityScorerApplies:
    def test_applies_false_when_no_years_in_jd(self):
        scorer = SeniorityScorer()
        jd = JobDescription(title="E", description="Great team", required_skills=[])
        assert scorer.applies(jd) is False

    def test_applies_true_when_years_in_jd(self):
        scorer = SeniorityScorer()
        jd = JobDescription(title="E", description="5+ years of Python", required_skills=[])
        assert scorer.applies(jd) is True


class TestSeniorityScorerScore:
    def test_meets_requirement_full_score(self):
        scorer = SeniorityScorer()
        resume = _resume_with_experience([
            _exp("E", date(2018, 1, 1), date(2025, 1, 1)),  # 7 years
        ])
        jd = JobDescription(title="E", description="5+ years required", required_skills=[])
        result = scorer.score(resume, jd, ai=None)
        assert result.score.score == 100.0
        assert result.gaps == []

    def test_shortfall_proportional_score(self):
        scorer = SeniorityScorer()
        resume = _resume_with_experience([
            _exp("E", date(2022, 1, 1), date(2025, 1, 1)),  # 3 years
        ])
        jd = JobDescription(title="E", description="5+ years required", required_skills=[])
        result = scorer.score(resume, jd, ai=None)
        # 3/5 = 60.
        assert 55 <= result.score.score <= 65
        assert len(result.gaps) == 1
        assert result.gaps[0].category == "seniority"

    def test_large_shortfall_high_severity(self):
        scorer = SeniorityScorer()
        resume = _resume_with_experience([
            _exp("E", date(2024, 1, 1), date(2025, 1, 1)),  # 1 year
        ])
        jd = JobDescription(title="E", description="10+ years required", required_skills=[])
        result = scorer.score(resume, jd, ai=None)
        assert result.gaps[0].severity == "high"
