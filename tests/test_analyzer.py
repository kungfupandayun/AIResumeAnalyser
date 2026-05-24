import pytest

from app.models.analysis import AnalysisResponse
from app.services.analyzer import analyze
from tests.fixtures.golden import (
    strong_match,
    weak_match,
    no_summary,
    no_years_in_jd,
    rich_jd,
)


class TestAnalyzerOutputShape:
    def test_returns_analysis_response(self):
        resume, jd = strong_match()
        result = analyze(resume, jd)
        assert isinstance(result, AnalysisResponse)

    def test_legacy_aliases_populated(self):
        resume, jd = strong_match()
        result = analyze(resume, jd)
        assert result.match_score == result.overall_score
        # missing_keywords mirrors skills gaps only.
        skills_gap_items = [g.item for g in result.gaps if g.category == "skills"]
        assert result.missing_keywords == skills_gap_items


class TestModeFlip:
    def test_keyword_only_when_no_ai(self, monkeypatch):
        # When OPENAI_API_KEY is unset, get_ai_client returns None,
        # the orchestrator runs all scorers via keyword-only paths,
        # and mode is "keyword-only".
        monkeypatch.setattr("app.services.analyzer.get_ai_client", lambda: None)
        resume, jd = strong_match()
        result = analyze(resume, jd)
        assert result.mode == "keyword-only"

    def test_hybrid_when_ai_available(self, monkeypatch, fake_ai_client):
        monkeypatch.setattr("app.services.analyzer.get_ai_client", lambda: fake_ai_client)
        resume, jd = strong_match()
        result = analyze(resume, jd)
        assert result.mode == "hybrid"


class TestAppliesFiltering:
    def test_seniority_dropped_when_no_years(self, monkeypatch):
        monkeypatch.setattr("app.services.analyzer.get_ai_client", lambda: None)
        resume, jd = no_years_in_jd()
        result = analyze(resume, jd)
        dimension_names = [d.name for d in result.dimension_scores]
        assert "seniority" not in dimension_names

    def test_summary_dropped_when_no_summary(self, monkeypatch):
        monkeypatch.setattr("app.services.analyzer.get_ai_client", lambda: None)
        resume, jd = no_summary()
        result = analyze(resume, jd)
        dimension_names = [d.name for d in result.dimension_scores]
        assert "summary_alignment" not in dimension_names


class TestWeightRenormalization:
    def test_active_weights_sum_to_one(self, monkeypatch):
        monkeypatch.setattr("app.services.analyzer.get_ai_client", lambda: None)
        for fixture in (strong_match, weak_match, no_years_in_jd, no_summary, rich_jd):
            resume, jd = fixture()
            result = analyze(resume, jd)
            total = sum(d.weight for d in result.dimension_scores)
            assert abs(total - 1.0) < 1e-6, f"weights for {fixture.__name__} sum to {total}"


class TestScoreRanges:
    def test_strong_match_high_score(self, monkeypatch):
        monkeypatch.setattr("app.services.analyzer.get_ai_client", lambda: None)
        resume, jd = strong_match()
        result = analyze(resume, jd)
        assert result.overall_score >= 60

    def test_weak_match_low_score(self, monkeypatch):
        monkeypatch.setattr("app.services.analyzer.get_ai_client", lambda: None)
        resume, jd = weak_match()
        result = analyze(resume, jd)
        assert result.overall_score < 40


class TestRichJDProducesExperienceGaps:
    def test_unaddressed_jd_sentences_become_gaps(self, monkeypatch):
        monkeypatch.setattr("app.services.analyzer.get_ai_client", lambda: None)
        resume, jd = rich_jd()
        result = analyze(resume, jd)
        # "Mentor junior data engineers" isn't in the resume bullets.
        exp_gaps = [g for g in result.gaps if g.category == "experience"]
        assert any("mentor" in g.item.lower() for g in exp_gaps)
