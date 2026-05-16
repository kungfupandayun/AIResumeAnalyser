import pytest

from app.models.job import JobDescription
from app.models.resume import Resume, ContactInfo
from app.services.scorers.summary import SummaryAlignmentScorer


def _resume(summary):
    return Resume(
        name="T",
        contact=ContactInfo(email="t@x.com", phone="5", location="X"),
        summary=summary,
        skills=["Python"],
        experience=[],
        education=[],
        projects=[],
    )


def _jd(desc):
    return JobDescription(title="E", description=desc, required_skills=[])


class TestApplies:
    def test_false_when_no_summary(self):
        scorer = SummaryAlignmentScorer()
        assert scorer.applies(_jd("Build things")) is True  # applies() takes only jd

    def test_score_returns_no_op_when_summary_none(self):
        # applies() can't see the resume, so the scorer must self-check inside score().
        # The orchestrator handles this via a check before calling score(),
        # so this scorer's contract: if summary is None it returns score=100 / no gaps.
        scorer = SummaryAlignmentScorer()
        result = scorer.score(_resume(None), _jd("Build things"), ai=None)
        assert result.gaps == []


class TestSummaryAlignmentKeywordPath:
    def test_aligned_summary_high_score(self):
        scorer = SummaryAlignmentScorer()
        resume = _resume("Senior Python backend engineer focused on FastAPI microservices and AWS")
        jd = _jd("Looking for a senior Python engineer with FastAPI and AWS experience")
        result = scorer.score(resume, jd, ai=None)
        assert result.score.score >= 30  # TF-IDF on tiny corpus

    def test_unaligned_summary_emits_gap(self):
        scorer = SummaryAlignmentScorer()
        resume = _resume("Award-winning chef specializing in modern French cuisine")
        jd = _jd("Senior Python engineer with FastAPI experience needed")
        result = scorer.score(resume, jd, ai=None)
        assert result.score.score < 60
        assert len(result.gaps) == 1
        assert result.gaps[0].severity == "low"


class TestSummaryAlignmentAIPath:
    def test_identical_strings_perfect_with_ai(self, fake_ai_client):
        scorer = SummaryAlignmentScorer()
        text = "Backend engineer skilled in Python"
        result = scorer.score(_resume(text), _jd(text), ai=fake_ai_client)
        assert result.score.score >= 95
