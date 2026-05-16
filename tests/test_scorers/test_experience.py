from datetime import date

import pytest

from app.models.job import JobDescription
from app.models.resume import Resume, ContactInfo, Experience
from app.services.scorers.experience import ExperienceScorer


def _resume_with_bullets(bullets):
    return Resume(
        name="Test",
        contact=ContactInfo(email="t@x.com", phone="555-0", location="X"),
        skills=["Python"],
        experience=[
            Experience(
                title="Engineer",
                company="Co",
                start_date=date(2020, 1, 1),
                end_date=date(2023, 1, 1),
                descriptions=bullets,
            )
        ],
        education=[],
        projects=[],
    )


def _jd(description):
    return JobDescription(
        title="Engineer",
        description=description,
        required_skills=[],
    )


class TestExperienceScorerKeywordPath:
    def test_strong_overlap_high_score(self):
        scorer = ExperienceScorer()
        resume = _resume_with_bullets([
            "Built FastAPI microservices on AWS",
            "Managed Docker containerization for backend services",
        ])
        jd = _jd("Build FastAPI microservices. Manage Docker containers on AWS.")
        result = scorer.score(resume, jd, ai=None)
        assert result.score.score >= 30  # TF-IDF on tiny corpus is noisy; range-based.

    def test_no_overlap_low_score_and_gaps(self):
        scorer = ExperienceScorer()
        resume = _resume_with_bullets([
            "Curated rare manuscripts in archival storage",
        ])
        jd = _jd("Design distributed systems. Optimize database queries.")
        result = scorer.score(resume, jd, ai=None)
        assert result.score.score < 30
        assert len(result.gaps) >= 1

    def test_metadata_includes_jd_sentence_matches(self):
        scorer = ExperienceScorer()
        resume = _resume_with_bullets(["Built FastAPI services"])
        jd = _jd("Build FastAPI services. Run incident response.")
        result = scorer.score(resume, jd, ai=None)
        matches = result.metadata.get("jd_sentence_matches")
        assert isinstance(matches, list)
        assert len(matches) == 2  # two JD sentences
        for m in matches:
            assert "jd_sentence" in m
            assert "best_bullet_text" in m
            assert "similarity" in m

    def test_applies_false_when_no_jd_description(self):
        scorer = ExperienceScorer()
        assert scorer.applies(_jd("")) is False

    def test_applies_false_when_no_resume_bullets(self):
        # applies() takes only jd, so this is checked at score() time:
        scorer = ExperienceScorer()
        resume = Resume(
            name="N",
            contact=ContactInfo(email="t@x.com", phone="5", location="X"),
            skills=["Python"],
            experience=[],
            education=[],
            projects=[],
        )
        result = scorer.score(resume, _jd("Build things"), ai=None)
        # Score 0, single high-severity gap pointing at the empty-experience case.
        assert result.score.score == 0.0


class TestExperienceScorerAIPath:
    def test_uses_embeddings_when_ai_present(self, fake_ai_client):
        scorer = ExperienceScorer()
        resume = _resume_with_bullets(["Identical sentence."])
        jd = _jd("Identical sentence.")
        result = scorer.score(resume, jd, ai=fake_ai_client)
        # FakeAIClient returns deterministic vectors; identical strings → cosine 1.0.
        assert result.score.score >= 95
