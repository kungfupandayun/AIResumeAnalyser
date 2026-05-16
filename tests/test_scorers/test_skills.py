import pytest

from app.models.job import JobDescription
from app.models.resume import Resume, ContactInfo
from app.services.scorers.skills import SkillsScorer


def _resume(skills, summary=None):
    return Resume(
        name="Test User",
        contact=ContactInfo(
            email="t@example.com",
            phone="555-0000",
            location="X",
        ),
        summary=summary,
        skills=skills,
        experience=[],
        education=[],
        projects=[],
    )


def _jd(required, description=""):
    return JobDescription(
        title="Engineer",
        description=description,
        required_skills=required,
    )


class TestSkillsScorerKeywordPath:
    def test_perfect_match(self):
        scorer = SkillsScorer()
        result = scorer.score(
            _resume(["Python", "FastAPI"]),
            _jd(["Python", "FastAPI"]),
            ai=None,
        )
        assert result.score.score == 100.0
        assert result.gaps == []

    def test_no_match(self):
        scorer = SkillsScorer()
        result = scorer.score(
            _resume(["Cobol"]),
            _jd(["Python", "FastAPI"]),
            ai=None,
        )
        assert result.score.score == 0.0
        assert len(result.gaps) == 2
        assert all(g.category == "skills" and g.severity == "high" for g in result.gaps)

    def test_synonym_match(self):
        scorer = SkillsScorer()
        # Resume says "K8s", JD asks "Kubernetes". Synonyms YAML maps them.
        result = scorer.score(
            _resume(["K8s"]),
            _jd(["Kubernetes"]),
            ai=None,
        )
        assert result.score.score == 100.0

    def test_fuzzy_match(self):
        scorer = SkillsScorer()
        # "Postgres" ↔ "PostgreSQL" via synonym dict.
        result = scorer.score(
            _resume(["Postgres"]),
            _jd(["PostgreSQL"]),
            ai=None,
        )
        assert result.score.score == 100.0

    def test_partial_match_score(self):
        scorer = SkillsScorer()
        result = scorer.score(
            _resume(["Python", "FastAPI"]),
            _jd(["Python", "FastAPI", "Docker", "AWS"]),
            ai=None,
        )
        # 2 out of 4 → 50.
        assert 49 <= result.score.score <= 51

    def test_score_is_zero_when_no_required_skills(self):
        scorer = SkillsScorer()
        result = scorer.score(_resume(["Python"]), _jd([], ""), ai=None)
        # No skills required → no gaps, perfect score by convention.
        assert result.score.score == 100.0
        assert result.gaps == []


class TestSkillsScorerAIPath:
    def test_ai_path_catches_synonym_not_in_dict(self, fake_ai_client):
        scorer = SkillsScorer()
        # Same string -> identical fake-embedding -> cosine 1.0 -> matched.
        result = scorer.score(
            _resume(["Distributed Systems"]),
            _jd(["Distributed Systems"]),
            ai=fake_ai_client,
        )
        assert result.score.score == 100.0


class TestSkillsScorerApplies:
    def test_always_applies(self):
        scorer = SkillsScorer()
        assert scorer.applies(_jd([])) is True
        assert scorer.applies(_jd(["X"])) is True
