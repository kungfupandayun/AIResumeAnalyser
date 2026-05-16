import pytest
from pydantic import ValidationError

from app.models.analysis import (
    AnalysisResponse,
    DimensionScore,
    Gap,
    Suggestion,
)


class TestDimensionScore:
    def test_valid(self):
        d = DimensionScore(name="skills", score=82.5, weight=0.35, rationale="6/7 matched")
        assert d.name == "skills"
        assert d.score == 82.5

    def test_invalid_name_rejected(self):
        with pytest.raises(ValidationError):
            DimensionScore(name="foo", score=80, weight=0.3, rationale="x")


class TestGap:
    def test_valid(self):
        g = Gap(category="skills", item="Kubernetes", severity="high")
        assert g.severity == "high"

    def test_invalid_severity(self):
        with pytest.raises(ValidationError):
            Gap(category="skills", item="X", severity="urgent")


class TestSuggestion:
    def test_optional_target_section(self):
        s = Suggestion(text="Add K8s", category="gap", priority="high")
        assert s.target_section is None

    def test_with_target_section(self):
        s = Suggestion(
            text="Rewrite bullet",
            category="rewrite",
            priority="medium",
            target_section="experience[0].descriptions[1]",
        )
        assert s.target_section == "experience[0].descriptions[1]"


class TestAnalysisResponse:
    def _minimal(self) -> dict:
        return {
            "mode": "hybrid",
            "overall_score": 75.0,
            "dimension_scores": [
                {"name": "skills", "score": 80.0, "weight": 0.5, "rationale": "x"},
                {"name": "experience", "score": 70.0, "weight": 0.5, "rationale": "x"},
            ],
            "gaps": [{"category": "skills", "item": "K8s", "severity": "high"}],
            "suggestions": [{"text": "Add K8s", "category": "gap", "priority": "high"}],
            "match_score": 75.0,
            "missing_keywords": ["K8s"],
        }

    def test_constructs(self):
        r = AnalysisResponse(**self._minimal())
        assert r.mode == "hybrid"
        assert r.overall_score == 75.0
        assert r.warnings == []

    def test_legacy_aliases_present(self):
        r = AnalysisResponse(**self._minimal())
        # Legacy fields exist for backwards compatibility with v1 clients.
        assert r.match_score == r.overall_score
        assert r.missing_keywords == ["K8s"]

    def test_mode_must_be_known(self):
        bad = self._minimal()
        bad["mode"] = "magic"
        with pytest.raises(ValidationError):
            AnalysisResponse(**bad)

    def test_warnings_defaults_empty(self):
        r = AnalysisResponse(**self._minimal())
        assert r.warnings == []

    def test_warnings_explicit(self):
        data = self._minimal()
        data["warnings"] = ["skills fell back to keyword-only"]
        r = AnalysisResponse(**data)
        assert len(r.warnings) == 1
