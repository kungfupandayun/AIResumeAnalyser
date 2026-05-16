import json

import pytest

from app.models.analysis import DimensionScore, Gap
from app.models.job import JobDescription
from app.models.resume import Resume, ContactInfo, Experience
from app.services.scorers.base import DimensionResult
from app.services.suggestions import build_suggestions
from datetime import date


def _minimal_resume(bullets=None):
    return Resume(
        name="T",
        contact=ContactInfo(email="t@x.com", phone="5", location="X"),
        skills=["Python"],
        experience=[
            Experience(
                title="Eng",
                company="Co",
                start_date=date(2022, 1, 1),
                end_date=date(2024, 1, 1),
                descriptions=bullets or ["Built things"],
            )
        ],
        education=[],
        projects=[],
    )


def _jd(desc="Build FastAPI services"):
    return JobDescription(title="E", description=desc, required_skills=["FastAPI"])


def _dummy_result(name="experience"):
    return DimensionResult(
        score=DimensionScore(name=name, score=50.0, weight=0.3, rationale="x"),
        gaps=[],
        metadata={},
    )


class TestPhase1Templates:
    def test_skills_high_severity_template(self):
        gaps = [Gap(category="skills", item="Kubernetes", severity="high")]
        suggestions = build_suggestions(_minimal_resume(), _jd(), gaps, [], ai=None)
        assert any("Kubernetes" in s.text for s in suggestions)
        assert any(s.priority == "high" for s in suggestions)

    def test_seniority_gap_template(self):
        gaps = [Gap(category="seniority", item="Role asks 5+ yrs; resume shows 3", severity="medium")]
        suggestions = build_suggestions(_minimal_resume(), _jd(), gaps, [], ai=None)
        texts = " ".join(s.text for s in suggestions)
        assert "5+" in texts or "years" in texts.lower()

    def test_no_ai_means_only_phase1(self):
        gaps = [Gap(category="skills", item="Docker", severity="high")]
        suggestions = build_suggestions(_minimal_resume(), _jd(), gaps, [], ai=None)
        assert all(s.category == "gap" for s in suggestions)

    def test_no_gaps_produces_no_suggestions(self):
        suggestions = build_suggestions(_minimal_resume(), _jd(), [], [], ai=None)
        assert suggestions == []


class TestPhase2LLMRewrites:
    def test_valid_json_response_produces_rewrite_suggestion(self, fake_ai_with_completion):
        canned = json.dumps([
            {
                "target_section": "experience[0].descriptions[0]",
                "original": "Built things",
                "suggested": "Built scalable FastAPI services serving 10k req/s",
                "reason": "Add specificity and a quantified metric",
            }
        ])
        ai = fake_ai_with_completion(canned)
        exp_result = DimensionResult(
            score=DimensionScore(name="experience", score=30.0, weight=0.3, rationale="x"),
            gaps=[Gap(category="experience", item="Build FastAPI services", severity="medium")],
            metadata={
                "jd_sentence_matches": [
                    {
                        "jd_sentence": "Build FastAPI services",
                        "best_bullet_index": "experience[0].descriptions[0]",
                        "best_bullet_text": "Built things",
                        "similarity": 0.2,
                    }
                ]
            },
        )
        gaps = exp_result.gaps
        suggestions = build_suggestions(_minimal_resume(), _jd(), gaps, [exp_result], ai=ai)
        rewrites = [s for s in suggestions if s.category == "rewrite"]
        assert len(rewrites) == 1
        assert rewrites[0].target_section == "experience[0].descriptions[0]"
        assert "FastAPI" in rewrites[0].text

    def test_malformed_json_is_skipped_silently(self, fake_ai_with_completion):
        ai = fake_ai_with_completion("not valid json {{{")
        exp_result = DimensionResult(
            score=DimensionScore(name="experience", score=30.0, weight=0.3, rationale="x"),
            gaps=[Gap(category="experience", item="Build FastAPI", severity="medium")],
            metadata={
                "jd_sentence_matches": [
                    {
                        "jd_sentence": "Build FastAPI",
                        "best_bullet_index": "experience[0].descriptions[0]",
                        "best_bullet_text": "Built things",
                        "similarity": 0.1,
                    }
                ]
            },
        )
        gaps = exp_result.gaps
        suggestions = build_suggestions(_minimal_resume(), _jd(), gaps, [exp_result], ai=ai)
        assert all(s.category != "rewrite" for s in suggestions)

    def test_null_suggested_field_is_skipped(self, fake_ai_with_completion):
        canned = json.dumps([
            {
                "target_section": "experience[0].descriptions[0]",
                "original": "Built things",
                "suggested": None,
                "reason": "Cannot rewrite without invention",
            }
        ])
        ai = fake_ai_with_completion(canned)
        exp_result = DimensionResult(
            score=DimensionScore(name="experience", score=30.0, weight=0.3, rationale="x"),
            gaps=[Gap(category="experience", item="Build FastAPI", severity="medium")],
            metadata={
                "jd_sentence_matches": [
                    {
                        "jd_sentence": "Build FastAPI",
                        "best_bullet_index": "experience[0].descriptions[0]",
                        "best_bullet_text": "Built things",
                        "similarity": 0.1,
                    }
                ]
            },
        )
        suggestions = build_suggestions(_minimal_resume(), _jd(), exp_result.gaps, [exp_result], ai=ai)
        assert all(s.category != "rewrite" for s in suggestions)
