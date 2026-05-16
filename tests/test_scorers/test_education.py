import pytest

from app.models.job import JobDescription
from app.models.resume import Resume, ContactInfo, Education
from app.services.scorers.education import EducationScorer, rank_degree


def _resume(degrees):
    return Resume(
        name="T",
        contact=ContactInfo(email="t@x.com", phone="5", location="X"),
        skills=["Python"],
        experience=[],
        education=[Education(degree=d, institution="Inst") for d in degrees],
        projects=[],
    )


def _jd(desc):
    return JobDescription(title="E", description=desc, required_skills=[])


class TestRankDegree:
    @pytest.mark.parametrize("text, expected", [
        ("PhD in CS", 4),
        ("Doctorate", 4),
        ("Master of Science", 3),
        ("MBA", 3),
        ("M.S. in EE", 3),
        ("Bachelor of Arts", 2),
        ("B.S. in CS", 2),
        ("High School Diploma", 1),
        ("", 0),
    ])
    def test_rank(self, text, expected):
        assert rank_degree(text) == expected


class TestEducationScorerApplies:
    def test_no_degree_keyword(self):
        scorer = EducationScorer()
        assert scorer.applies(_jd("Strong leadership skills")) is False

    def test_with_degree_keyword(self):
        scorer = EducationScorer()
        assert scorer.applies(_jd("Bachelor's in CS required")) is True


class TestEducationScorerScore:
    def test_meets_requirement(self):
        scorer = EducationScorer()
        result = scorer.score(_resume(["Master of Science"]), _jd("Bachelor's required"), ai=None)
        assert result.score.score == 100.0
        assert result.gaps == []

    def test_below_requirement(self):
        scorer = EducationScorer()
        result = scorer.score(_resume(["Bachelor of Arts"]), _jd("Master's required"), ai=None)
        # 2/3 ≈ 66.7
        assert 60 <= result.score.score <= 70
        assert len(result.gaps) == 1

    def test_no_education_listed(self):
        scorer = EducationScorer()
        result = scorer.score(_resume([]), _jd("Bachelor's required"), ai=None)
        assert result.score.score == 0.0
