# Holistic Resume Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the naive set-intersection `analyze_resume_logic` with a holistic, multi-dimensional analyzer (5 scorers, hybrid OpenAI/keyword paths, LLM-assisted suggestion rewrites) without changing the `/api/resume/analyze` route signature.

**Architecture:** Scorer-per-dimension registry. Each of 5 scorers (skills, experience, seniority, education, summary_alignment) implements a `Scorer` Protocol with both AI and keyword-only paths. An orchestrator iterates the registry, applies dynamic weight re-normalization for inapplicable dimensions, aggregates gaps, and calls a suggestions module (deterministic templates + optional LLM rewrites). An `AIClient` wraps OpenAI with a circuit breaker and degrades silently to `None` on failure.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2.5, pydantic-settings, spaCy 3.7 (`en_core_web_sm`), scikit-learn 1.3 (TF-IDF), rapidfuzz, openai 1.3, pyyaml, pytest.

**Conventions specific to this repo (READ FIRST):**
- Imports inside `app/` are **bare** (e.g. `from services.scorers.base import Scorer`, *not* `from app.services...`). Match this style in new files. Tests use `from app.X` because pytest runs from project root.
- Run server: `cd app && uvicorn main:app --reload`
- Run tests: `pytest` from project root (`D:/kungfupandayun/AIResumeAnalyser/`)
- Run a single test: `pytest tests/path/file.py::TestClass::test_name -v`
- Existing `tests/test_resume_router.py` asserts on legacy fields (`match_score`, `missing_keywords`, `suggestions`) — **must keep passing** after Task 14.

---

## File map

**Create:**
- `app/services/analyzer.py` — orchestrator
- `app/services/ai_client.py` — OpenAI wrapper + circuit breaker
- `app/services/suggestions.py` — phase-1 templates + phase-2 LLM rewrites
- `app/services/scorers/__init__.py` — REGISTRY list
- `app/services/scorers/base.py` — `Scorer` Protocol, `DimensionResult`
- `app/services/scorers/skills.py`
- `app/services/scorers/experience.py`
- `app/services/scorers/seniority.py`
- `app/services/scorers/education.py`
- `app/services/scorers/summary.py`
- `app/data/__init__.py` (empty marker)
- `app/data/synonyms.yaml`
- `tests/test_analyzer.py`
- `tests/test_ai_client.py`
- `tests/test_suggestions.py`
- `tests/test_scorers/__init__.py` (empty marker)
- `tests/test_scorers/test_skills.py`
- `tests/test_scorers/test_experience.py`
- `tests/test_scorers/test_seniority.py`
- `tests/test_scorers/test_education.py`
- `tests/test_scorers/test_summary.py`
- `tests/fixtures/__init__.py` (empty marker)
- `tests/fixtures/golden.py` — 5 (resume, JD) pairs

**Modify:**
- `requirements.txt` — add `pyyaml`, `pydantic-settings>=2.0,<2.1`, `rapidfuzz`
- `app/core/config.py` — populate with `Settings`
- `app/models/analysis.py` — replace with new nested shape (keep legacy aliases)
- `app/services/resume_service.py` — `analyze_resume_logic` shrinks to 3-line wrapper
- `tests/conftest.py` — add `fake_ai_client` fixture
- `tests/test_models.py` — extend for new response shape
- `tests/test_resume_router.py` — add assertions for new fields; keep legacy assertions

---

## Task overview (16 tasks)

1. Add deps + install
2. Populate `core/config.py`
3. Replace `models/analysis.py` with new shape + model tests
4. Synonyms YAML + loader (test-driven)
5. `Scorer` Protocol + `DimensionResult`
6. `AIClient` + circuit breaker
7. `FakeAIClient` fixture
8. `SkillsScorer`
9. `ExperienceScorer`
10. `SeniorityScorer`
11. `EducationScorer`
12. `SummaryAlignmentScorer`
13. Wire scorers into REGISTRY
14. `suggestions.py` (phase 1 + phase 2)
15. `analyzer.py` orchestrator + golden fixtures
16. Wire into `resume_service.py` + update router tests

---

I will now write each task in detail. Each task is its own block — implementers should be able to execute them in order without back-references except where explicitly noted.

---

## Task 1: Add dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add three lines to `requirements.txt`**

Append at the end of the file:

```
pyyaml
pydantic-settings>=2.0,<2.1
rapidfuzz
```

Why the version pin: `pydantic` is pinned to `2.5.0`. `pydantic-settings>=2.7` requires `pydantic>=2.7.0`, which would force a pydantic upgrade. `pydantic-settings 2.0.x` works with pydantic 2.5.

- [ ] **Step 2: Install**

Run from project root: `pip install pyyaml "pydantic-settings>=2.0,<2.1" rapidfuzz`
Expected: three new packages installed, no errors.

- [ ] **Step 3: Verify**

Run: `python -c "import yaml, pydantic_settings, rapidfuzz; print('ok')"`
Expected output: `ok`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "Add deps for holistic analyzer (pyyaml, pydantic-settings, rapidfuzz)"
```

---

## Task 2: Populate `core/config.py`

**Files:**
- Modify: `app/core/config.py`

- [ ] **Step 1: Replace the file contents**

Replace the entire contents of `app/core/config.py` with:

```python
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OPENAI_API_KEY: Optional[str] = None
    EMBED_MODEL: str = "text-embedding-3-small"
    CHAT_MODEL: str = "gpt-4o-mini"
    SYNONYMS_PATH: Path = Path(__file__).parent.parent / "data" / "synonyms.yaml"

    WEIGHT_SKILLS: float = 0.35
    WEIGHT_EXPERIENCE: float = 0.30
    WEIGHT_SENIORITY: float = 0.15
    WEIGHT_SUMMARY: float = 0.10
    WEIGHT_EDUCATION: float = 0.10

    AI_EMBED_TIMEOUT_S: float = 20.0
    AI_CHAT_TIMEOUT_S: float = 30.0
    AI_CIRCUIT_THRESHOLD: int = 3
    AI_CIRCUIT_WINDOW_S: float = 60.0

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from app.core.config import settings; print(settings.EMBED_MODEL)"`
Expected output: `text-embedding-3-small`

- [ ] **Step 3: Commit**

```bash
git add app/core/config.py
git commit -m "Populate core/config.py with Settings (OpenAI, weights, timeouts)"
```

---

## Task 3: Replace `models/analysis.py` with new shape

**Files:**
- Modify: `app/models/analysis.py`
- Modify: `tests/test_models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

Replace `tests/test_models.py` with:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v`
Expected: ImportErrors / failures because new model classes don't exist yet.

- [ ] **Step 3: Implement the new models**

Replace the contents of `app/models/analysis.py` with:

```python
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


DimensionName = Literal[
    "skills",
    "experience",
    "education",
    "seniority",
    "summary_alignment",
]


class DimensionScore(BaseModel):
    name: DimensionName
    score: float = Field(..., ge=0, le=100, description="Dimension score 0-100")
    weight: float = Field(..., ge=0, le=1, description="Contribution to overall, after renormalization")
    rationale: str = Field(..., description="One-line explanation of the score")


class Gap(BaseModel):
    category: DimensionName
    item: str = Field(..., description="What is missing/weak (skill name, JD sentence, etc.)")
    severity: Literal["high", "medium", "low"]


class Suggestion(BaseModel):
    text: str
    category: Literal["gap", "rewrite", "structure", "keyword"]
    priority: Literal["high", "medium", "low"]
    target_section: Optional[str] = Field(
        default=None,
        description="Dotted path into the Resume model, e.g. 'experience[0].descriptions[1]'",
    )


class AnalysisResponse(BaseModel):
    mode: Literal["hybrid", "keyword-only"]
    overall_score: float = Field(..., ge=0, le=100, description="Weighted sum of dimension scores")
    dimension_scores: List[DimensionScore]
    gaps: List[Gap]
    suggestions: List[Suggestion]
    warnings: List[str] = Field(default_factory=list)

    # Legacy aliases — kept for one minor release. Drop in v2.
    match_score: float = Field(..., description="DEPRECATED: equals overall_score")
    missing_keywords: List[str] = Field(
        ..., description="DEPRECATED: equals [g.item for g in gaps if g.category == 'skills']"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/models/analysis.py tests/test_models.py
git commit -m "Replace AnalysisResponse with nested shape (keep legacy aliases)"
```

---

## Task 4: Synonyms YAML + loader

**Files:**
- Create: `app/data/__init__.py`
- Create: `app/data/synonyms.yaml`
- Create: `tests/test_synonyms.py`

The synonym dict is loaded once at module import and lives behind a tiny helper so tests can inject a fixture instead of touching disk.

- [ ] **Step 1: Create empty package marker**

Create `app/data/__init__.py` with this exact content:

```python
# Package marker for static data files (YAML lookups, etc.).
```

- [ ] **Step 2: Create the synonyms YAML**

Create `app/data/synonyms.yaml` with this exact content (these are starter entries — extend later as needed):

```yaml
# Canonical skill -> list of aliases. All matching is case-insensitive.
kubernetes:
  - k8s
  - container orchestration
postgresql:
  - postgres
  - pg
  - postgre
javascript:
  - js
  - ecmascript
typescript:
  - ts
fastapi:
  - fast api
python:
  - python3
  - py
"ci/cd":
  - continuous integration
  - continuous delivery
  - github actions
  - jenkins
  - gitlab ci
aws:
  - amazon web services
  - ec2
  - s3
gcp:
  - google cloud
  - google cloud platform
azure:
  - microsoft azure
docker:
  - containers
  - containerization
"rest apis":
  - rest
  - restful
  - http api
graphql:
  - gql
microservices:
  - micro services
  - service oriented architecture
sql:
  - relational database
nosql:
  - mongodb
  - dynamodb
  - cassandra
redis:
  - in-memory cache
  - key-value store
machine learning:
  - ml
  - machine-learning
deep learning:
  - dl
  - neural networks
nlp:
  - natural language processing
react:
  - reactjs
  - react.js
node.js:
  - nodejs
  - node
git:
  - version control
```

- [ ] **Step 3: Write failing tests for the loader**

Create `tests/test_synonyms.py`:

```python
import pytest

from app.services.scorers.skills import load_synonyms, expand_with_synonyms


def test_load_synonyms_returns_dict():
    syns = load_synonyms()
    assert isinstance(syns, dict)
    assert "kubernetes" in syns
    assert "k8s" in syns["kubernetes"]


def test_load_synonyms_lowercases_keys_and_values():
    syns = load_synonyms()
    for canonical, aliases in syns.items():
        assert canonical == canonical.lower()
        for alias in aliases:
            assert alias == alias.lower()


def test_expand_with_synonyms_matches_alias_to_canonical():
    syns = {"kubernetes": ["k8s", "container orchestration"]}
    # Given a resume mentioning "K8s", expansion lets us match a JD asking "Kubernetes".
    expanded = expand_with_synonyms("k8s", syns)
    assert "kubernetes" in expanded
    assert "k8s" in expanded


def test_expand_with_synonyms_matches_canonical_to_aliases():
    syns = {"kubernetes": ["k8s", "container orchestration"]}
    expanded = expand_with_synonyms("Kubernetes", syns)
    assert "kubernetes" in expanded
    assert "k8s" in expanded
    assert "container orchestration" in expanded


def test_expand_with_synonyms_unknown_term_returns_only_lowered_self():
    expanded = expand_with_synonyms("MadeUpThing", {})
    assert expanded == {"madeupthing"}
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_synonyms.py -v`
Expected: ImportError (the `skills` module doesn't exist yet).

- [ ] **Step 5: Create the scorers package marker**

Create `app/services/scorers/__init__.py` with this exact content (REGISTRY stays empty until Task 13):

```python
# Scorer registry — populated in Task 13 once individual scorers exist.
REGISTRY: list = []
```

- [ ] **Step 6: Create minimal `skills.py` with just the loader (full scorer comes in Task 8)**

Create `app/services/scorers/skills.py`:

```python
from functools import lru_cache
from typing import Dict, List, Set

import yaml

from core.config import settings


@lru_cache(maxsize=1)
def load_synonyms() -> Dict[str, List[str]]:
    """Load the synonym dictionary from disk once.

    Hard-fails at first call if the YAML is missing or malformed —
    we want loud failure at startup, not silent skill-matching degradation.
    """
    path = settings.SYNONYMS_PATH
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Synonyms YAML at {path} must be a mapping, got {type(raw).__name__}")
    out: Dict[str, List[str]] = {}
    for canonical, aliases in raw.items():
        if not isinstance(aliases, list):
            raise ValueError(f"Synonyms for '{canonical}' must be a list, got {type(aliases).__name__}")
        out[str(canonical).lower()] = [str(a).lower() for a in aliases]
    return out


def expand_with_synonyms(term: str, syns: Dict[str, List[str]]) -> Set[str]:
    """Return the lowercased term plus all of its synonyms (canonical + aliases)."""
    lowered = term.lower()
    out: Set[str] = {lowered}
    for canonical, aliases in syns.items():
        if lowered == canonical or lowered in aliases:
            out.add(canonical)
            out.update(aliases)
    return out
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_synonyms.py -v`
Expected: all 5 tests pass.

- [ ] **Step 8: Commit**

```bash
git add app/data/__init__.py app/data/synonyms.yaml app/services/scorers/__init__.py app/services/scorers/skills.py tests/test_synonyms.py
git commit -m "Add synonyms YAML + loader (skills scorer stub)"
```

---

## Task 5: `Scorer` Protocol + `DimensionResult`

**Files:**
- Create: `app/services/scorers/base.py`
- Create: `tests/test_scorers/__init__.py`
- Test: covered by later scorer tests (no standalone test file for the Protocol itself; `DimensionResult` is exercised via scorer tests starting Task 8)

- [ ] **Step 1: Create the test package marker**

Create `tests/test_scorers/__init__.py` with:

```python
# Test package for scorer modules.
```

- [ ] **Step 2: Create `base.py`**

Create `app/services/scorers/base.py`:

```python
from typing import Any, Dict, List, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from models.analysis import DimensionScore, Gap
from models.job import JobDescription
from models.resume import Resume


class DimensionResult(BaseModel):
    """The output of one scorer.

    `metadata` is intentionally internal — it is NOT included in AnalysisResponse.
    ExperienceScorer uses it to pass the per-JD-sentence similarity matrix to
    the suggestions module without recomputation.
    """

    score: DimensionScore
    gaps: List[Gap]
    metadata: Dict[str, Any] = Field(default_factory=dict)


# We import AIClient lazily inside scorers to avoid a circular import,
# so the Protocol uses `object` for the ai parameter type and each scorer
# narrows it internally.
@runtime_checkable
class Scorer(Protocol):
    name: str  # one of the DimensionName Literals
    default_weight: float

    def applies(self, jd: JobDescription) -> bool:
        """Return False to drop this dimension; weights re-normalize."""
        ...

    def score(self, resume: Resume, jd: JobDescription, ai: object) -> DimensionResult:
        """Compute the dimension. `ai` is `AIClient | None`."""
        ...
```

- [ ] **Step 3: Quick smoke import**

Run: `python -c "from app.services.scorers.base import Scorer, DimensionResult; print('ok')"`
Expected output: `ok`

- [ ] **Step 4: Commit**

```bash
git add app/services/scorers/base.py tests/test_scorers/__init__.py
git commit -m "Add Scorer Protocol and DimensionResult"
```

---

## Task 6: `AIClient` + circuit breaker

**Files:**
- Create: `app/services/ai_client.py`
- Create: `tests/test_ai_client.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ai_client.py`:

```python
import time
from unittest.mock import patch, MagicMock

import pytest

from app.services.ai_client import (
    AIClient,
    CircuitBreaker,
    get_ai_client,
    _circuit_breaker,
)


class TestCircuitBreaker:
    def test_closed_initially(self):
        cb = CircuitBreaker(threshold=3, window_s=60)
        assert not cb.is_open()

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(threshold=3, window_s=60)
        for _ in range(3):
            cb.record_failure()
        assert cb.is_open()

    def test_does_not_open_on_fewer_failures(self):
        cb = CircuitBreaker(threshold=3, window_s=60)
        cb.record_failure()
        cb.record_failure()
        assert not cb.is_open()

    def test_old_failures_age_out(self):
        cb = CircuitBreaker(threshold=3, window_s=0.05)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open()
        time.sleep(0.1)
        assert not cb.is_open()

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(threshold=3, window_s=60)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        # Two failures after a success; still not open.
        assert not cb.is_open()


class TestGetAIClient:
    def setup_method(self):
        _circuit_breaker.reset()

    def test_returns_none_when_no_key(self):
        with patch("app.services.ai_client.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.AI_CIRCUIT_THRESHOLD = 3
            mock_settings.AI_CIRCUIT_WINDOW_S = 60
            assert get_ai_client() is None

    def test_returns_client_when_key_set(self):
        with patch("app.services.ai_client.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.EMBED_MODEL = "text-embedding-3-small"
            mock_settings.CHAT_MODEL = "gpt-4o-mini"
            mock_settings.AI_EMBED_TIMEOUT_S = 20
            mock_settings.AI_CHAT_TIMEOUT_S = 30
            client = get_ai_client()
            assert client is not None
            assert isinstance(client, AIClient)

    def test_returns_none_when_circuit_open(self):
        _circuit_breaker.threshold = 1
        _circuit_breaker.record_failure()
        with patch("app.services.ai_client.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.EMBED_MODEL = "x"
            mock_settings.CHAT_MODEL = "y"
            mock_settings.AI_EMBED_TIMEOUT_S = 20
            mock_settings.AI_CHAT_TIMEOUT_S = 30
            assert get_ai_client() is None


class TestAIClientEmbed:
    def test_calls_openai_and_returns_vectors(self):
        with patch("app.services.ai_client.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.embeddings.create.return_value.data = [
                MagicMock(embedding=[0.1, 0.2, 0.3]),
                MagicMock(embedding=[0.4, 0.5, 0.6]),
            ]
            c = AIClient("sk-x", embed_model="m", chat_model="c", embed_timeout=20, chat_timeout=30)
            out = c.embed(["foo", "bar"])
            assert out == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
            mock_client.embeddings.create.assert_called_once()

    def test_records_failure_on_exception(self):
        _circuit_breaker.reset()
        with patch("app.services.ai_client.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.embeddings.create.side_effect = RuntimeError("boom")
            c = AIClient("sk-x", embed_model="m", chat_model="c", embed_timeout=20, chat_timeout=30)
            with pytest.raises(RuntimeError):
                c.embed(["foo"])
        # Failure was recorded:
        assert _circuit_breaker.failure_count() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ai_client.py -v`
Expected: ImportError (`app.services.ai_client` doesn't exist).

- [ ] **Step 3: Implement `ai_client.py`**

Create `app/services/ai_client.py`:

```python
import logging
import time
from collections import deque
from typing import List, Optional

from openai import OpenAI

from core.config import settings

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Simple time-window circuit breaker.

    Opens after `threshold` failures within `window_s` seconds.
    A single success resets the failure deque.
    """

    def __init__(self, threshold: int, window_s: float):
        self.threshold = threshold
        self.window_s = window_s
        self._failures: deque = deque()

    def _evict_old(self) -> None:
        now = time.monotonic()
        while self._failures and (now - self._failures[0]) > self.window_s:
            self._failures.popleft()

    def is_open(self) -> bool:
        self._evict_old()
        return len(self._failures) >= self.threshold

    def record_failure(self) -> None:
        self._failures.append(time.monotonic())

    def record_success(self) -> None:
        self._failures.clear()

    def failure_count(self) -> int:
        self._evict_old()
        return len(self._failures)

    def reset(self) -> None:
        self._failures.clear()


_circuit_breaker = CircuitBreaker(
    threshold=settings.AI_CIRCUIT_THRESHOLD,
    window_s=settings.AI_CIRCUIT_WINDOW_S,
)


class AIClient:
    """Thin wrapper around the OpenAI SDK.

    Each public method records success/failure with the module-level circuit
    breaker. Scorers wrap calls in their own try/except and treat any
    exception as 'AI not available for this call'.
    """

    def __init__(
        self,
        api_key: str,
        embed_model: str,
        chat_model: str,
        embed_timeout: float,
        chat_timeout: float,
    ):
        self._client = OpenAI(api_key=api_key)
        self._embed_model = embed_model
        self._chat_model = chat_model
        self._embed_timeout = embed_timeout
        self._chat_timeout = chat_timeout

    def embed(self, texts: List[str]) -> List[List[float]]:
        try:
            resp = self._client.embeddings.create(
                model=self._embed_model,
                input=texts,
                timeout=self._embed_timeout,
            )
            _circuit_breaker.record_success()
            return [d.embedding for d in resp.data]
        except Exception:
            _circuit_breaker.record_failure()
            raise

    def complete(self, system: str, user: str, *, max_tokens: int) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self._chat_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                timeout=self._chat_timeout,
            )
            _circuit_breaker.record_success()
            return resp.choices[0].message.content or ""
        except Exception:
            _circuit_breaker.record_failure()
            raise


def get_ai_client() -> Optional[AIClient]:
    """Return an AIClient if usable, else None.

    None means: no API key configured, OR the circuit breaker is open
    after recent failures. Either way: scorers take their keyword-only path.
    """
    if not settings.OPENAI_API_KEY:
        return None
    if _circuit_breaker.is_open():
        logger.warning("AI circuit breaker open; falling back to keyword-only mode.")
        return None
    return AIClient(
        api_key=settings.OPENAI_API_KEY,
        embed_model=settings.EMBED_MODEL,
        chat_model=settings.CHAT_MODEL,
        embed_timeout=settings.AI_EMBED_TIMEOUT_S,
        chat_timeout=settings.AI_CHAT_TIMEOUT_S,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ai_client.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/services/ai_client.py tests/test_ai_client.py
git commit -m "Add AIClient with circuit breaker + get_ai_client factory"
```

---

## Task 7: `FakeAIClient` test fixture

**Files:**
- Modify: `tests/conftest.py`

Scorer tests need an `AIClient` that doesn't hit OpenAI. We use deterministic hash-based vectors so `embed()` is repeatable across runs.

- [ ] **Step 1: Append to `tests/conftest.py`**

Add these imports at the top of `tests/conftest.py` (after the existing imports):

```python
import hashlib
import json
import math
from typing import List, Optional
```

Then append at the end of the file:

```python
class FakeAIClient:
    """Drop-in replacement for AIClient in tests.

    `embed`: deterministic, hash-based 16-dim unit vectors. Two identical
        strings always get the same vector; different strings get
        different-but-stable vectors. Cosine similarity is well-defined
        and not random, so threshold assertions are stable.
    `complete`: returns a canned response. Tests that need a specific
        response set `canned_completion` on the instance.
    """

    DIM = 16

    def __init__(self):
        self.canned_completion: Optional[str] = None
        self.embed_calls: List[List[str]] = []
        self.complete_calls: List[tuple] = []

    @classmethod
    def _vec(cls, text: str) -> List[float]:
        # SHA256 hash -> DIM floats in [-1, 1], then L2-normalized.
        h = hashlib.sha256(text.lower().encode("utf-8")).digest()
        raw = [(b / 127.5) - 1.0 for b in h[: cls.DIM]]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]

    def embed(self, texts: List[str]) -> List[List[float]]:
        self.embed_calls.append(list(texts))
        return [self._vec(t) for t in texts]

    def complete(self, system: str, user: str, *, max_tokens: int) -> str:
        self.complete_calls.append((system, user, max_tokens))
        if self.canned_completion is not None:
            return self.canned_completion
        # Default canned response is an empty JSON array — safe for
        # the suggestions module's phase-2 parser.
        return json.dumps([])


@pytest.fixture
def fake_ai_client():
    """A fresh FakeAIClient per test (no state leaks across tests)."""
    return FakeAIClient()


@pytest.fixture
def fake_ai_with_completion():
    """Factory: returns a FakeAIClient pre-loaded with a canned completion."""
    def _make(completion: str) -> FakeAIClient:
        c = FakeAIClient()
        c.canned_completion = completion
        return c
    return _make
```

- [ ] **Step 2: Verify the fixture is discoverable**

Create a one-off test `tests/test_fakeai_smoke.py` with this exact content:

```python
def test_fake_ai_embed_is_stable(fake_ai_client):
    a = fake_ai_client.embed(["hello", "world"])
    b = fake_ai_client.embed(["hello", "world"])
    assert a == b


def test_fake_ai_embed_unit_norm(fake_ai_client):
    [v] = fake_ai_client.embed(["anything"])
    norm = sum(x * x for x in v) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_fake_ai_complete_default_is_empty_json_array(fake_ai_client):
    out = fake_ai_client.complete("sys", "user", max_tokens=10)
    assert out == "[]"


def test_fake_ai_with_completion_factory(fake_ai_with_completion):
    c = fake_ai_with_completion('{"foo": 1}')
    assert c.complete("s", "u", max_tokens=5) == '{"foo": 1}'
```

Run: `pytest tests/test_fakeai_smoke.py -v`
Expected: all 4 tests pass.

- [ ] **Step 3: Remove the smoke test (it was for verification only)**

```bash
rm tests/test_fakeai_smoke.py
```

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "Add FakeAIClient fixture for deterministic scorer tests"
```

---

## Task 8: `SkillsScorer`

**Files:**
- Modify: `app/services/scorers/skills.py` (extend Task 4 stub with the scorer class)
- Create: `tests/test_scorers/test_skills.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_scorers/test_skills.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scorers/test_skills.py -v`
Expected: failures because `SkillsScorer` class doesn't exist yet.

- [ ] **Step 3: Extend `app/services/scorers/skills.py` with the full scorer**

**Append** this code to the existing `app/services/scorers/skills.py` (keep `load_synonyms` and `expand_with_synonyms` from Task 4):

```python
import math
from typing import List, Optional, Set

from rapidfuzz import fuzz

from models.analysis import DimensionScore, Gap
from models.job import JobDescription
from models.resume import Resume
from services.scorers.base import DimensionResult


_FUZZY_THRESHOLD = 85
_EMBED_COSINE_THRESHOLD = 0.80


def _normalize(skill: str) -> str:
    return skill.strip().lower()


def _matches_keyword(jd_skill: str, resume_skills: Set[str], syns: dict) -> bool:
    jd_norm = _normalize(jd_skill)
    jd_expanded = expand_with_synonyms(jd_norm, syns)

    for r in resume_skills:
        r_expanded = expand_with_synonyms(r, syns)
        if jd_expanded & r_expanded:
            return True
        # Fuzzy fallback for typos / spacing differences.
        if fuzz.partial_ratio(jd_norm, r) >= _FUZZY_THRESHOLD:
            return True
    return False


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


class SkillsScorer:
    name = "skills"
    default_weight = 0.35

    def applies(self, jd: JobDescription) -> bool:
        return True

    def score(self, resume: Resume, jd: JobDescription, ai: Optional[object]) -> DimensionResult:
        syns = load_synonyms()
        resume_skills = {_normalize(s) for s in resume.skills}
        required = [s for s in (jd.required_skills or []) if s.strip()]

        if not required:
            # No required skills -> nothing to gap on, perfect score.
            return DimensionResult(
                score=DimensionScore(
                    name=self.name,
                    score=100.0,
                    weight=self.default_weight,
                    rationale="JD lists no required skills",
                ),
                gaps=[],
            )

        unmatched: List[str] = []
        for req in required:
            if _matches_keyword(req, resume_skills, syns):
                continue
            unmatched.append(req)

        # AI path: try to rescue remaining unmatched via embedding similarity.
        ai_fallback = False
        if unmatched and ai is not None:
            try:
                texts = unmatched + list(resume_skills)
                vectors = ai.embed(texts)  # type: ignore[attr-defined]
                jd_vecs = vectors[: len(unmatched)]
                rs_vecs = vectors[len(unmatched):]
                still_unmatched: List[str] = []
                for jd_skill, jvec in zip(unmatched, jd_vecs):
                    if any(_cosine(jvec, rv) >= _EMBED_COSINE_THRESHOLD for rv in rs_vecs):
                        continue
                    still_unmatched.append(jd_skill)
                unmatched = still_unmatched
            except Exception:
                ai_fallback = True  # noqa: F841 — recorded in rationale below

        matched_count = len(required) - len(unmatched)
        score_pct = (matched_count / len(required)) * 100.0
        gaps = [
            Gap(category="skills", item=u, severity="high")
            for u in unmatched
        ]
        rationale = f"{matched_count}/{len(required)} required skills matched"
        if ai_fallback:
            rationale = "[fallback] " + rationale

        return DimensionResult(
            score=DimensionScore(
                name=self.name,
                score=score_pct,
                weight=self.default_weight,
                rationale=rationale,
            ),
            gaps=gaps,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scorers/test_skills.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/services/scorers/skills.py tests/test_scorers/test_skills.py
git commit -m "Add SkillsScorer (synonyms + fuzzy + embedding paths)"
```

---

## Task 9: `ExperienceScorer`

**Files:**
- Create: `app/services/scorers/experience.py`
- Create: `tests/test_scorers/test_experience.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_scorers/test_experience.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scorers/test_experience.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `experience.py`**

Create `app/services/scorers/experience.py`:

```python
import math
import re
from typing import List, Optional, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from models.analysis import DimensionScore, Gap
from models.job import JobDescription
from models.resume import Resume
from services.scorers.base import DimensionResult


_GAP_THRESHOLD = 0.5
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> List[str]:
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text) if p and p.strip()]
    return parts


def _collect_resume_bullets(resume: Resume) -> List[Tuple[str, str]]:
    """Return (path, text) pairs so suggestions can target the source bullet."""
    out: List[Tuple[str, str]] = []
    for i, exp in enumerate(resume.experience):
        for j, desc in enumerate(exp.descriptions):
            out.append((f"experience[{i}].descriptions[{j}]", desc))
    for i, proj in enumerate(resume.projects or []):
        for j, c in enumerate(proj.contributions):
            out.append((f"projects[{i}].contributions[{j}]", c))
    return out


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


class ExperienceScorer:
    name = "experience"
    default_weight = 0.30

    def applies(self, jd: JobDescription) -> bool:
        return bool(jd.description and jd.description.strip())

    def score(self, resume: Resume, jd: JobDescription, ai: Optional[object]) -> DimensionResult:
        jd_sentences = _split_sentences(jd.description or "")
        bullets = _collect_resume_bullets(resume)

        if not jd_sentences:
            return DimensionResult(
                score=DimensionScore(
                    name=self.name,
                    score=100.0,
                    weight=self.default_weight,
                    rationale="JD has no descriptive content",
                ),
                gaps=[],
            )

        if not bullets:
            gap = Gap(
                category="experience",
                item="Resume has no experience bullets to evaluate against the JD",
                severity="high",
            )
            return DimensionResult(
                score=DimensionScore(
                    name=self.name,
                    score=0.0,
                    weight=self.default_weight,
                    rationale="Resume has no experience bullets",
                ),
                gaps=[gap],
            )

        bullet_paths = [b[0] for b in bullets]
        bullet_texts = [b[1] for b in bullets]

        ai_fallback = False
        sims: List[List[float]] = []
        if ai is not None:
            try:
                all_vecs = ai.embed(jd_sentences + bullet_texts)  # type: ignore[attr-defined]
                jd_vecs = all_vecs[: len(jd_sentences)]
                bullet_vecs = all_vecs[len(jd_sentences):]
                sims = [
                    [_cosine(jv, bv) for bv in bullet_vecs]
                    for jv in jd_vecs
                ]
            except Exception:
                ai_fallback = True
                sims = []

        if not sims:
            # Keyword (TF-IDF) path.
            vec = TfidfVectorizer().fit(jd_sentences + bullet_texts)
            jd_tfidf = vec.transform(jd_sentences)
            bullet_tfidf = vec.transform(bullet_texts)
            sim_matrix = cosine_similarity(jd_tfidf, bullet_tfidf)
            sims = sim_matrix.tolist()

        # Per-JD-sentence top-1 similarity + best bullet.
        sentence_matches = []
        gaps: List[Gap] = []
        top1s: List[float] = []
        for s_idx, jd_sentence in enumerate(jd_sentences):
            row = sims[s_idx]
            best_idx = max(range(len(row)), key=lambda i: row[i])
            best_sim = row[best_idx]
            top1s.append(best_sim)
            sentence_matches.append({
                "jd_sentence": jd_sentence,
                "best_bullet_index": bullet_paths[best_idx],
                "best_bullet_text": bullet_texts[best_idx],
                "similarity": float(best_sim),
            })
            if best_sim < _GAP_THRESHOLD:
                trimmed = jd_sentence if len(jd_sentence) <= 200 else jd_sentence[:197] + "..."
                gaps.append(Gap(category="experience", item=trimmed, severity="medium"))

        avg = sum(top1s) / len(top1s)
        score_pct = max(0.0, min(100.0, avg * 100.0))
        rationale = f"avg top-1 sim {avg:.2f} across {len(jd_sentences)} JD sentence(s)"
        if ai_fallback:
            rationale = "[fallback] " + rationale

        return DimensionResult(
            score=DimensionScore(
                name=self.name,
                score=score_pct,
                weight=self.default_weight,
                rationale=rationale,
            ),
            gaps=gaps,
            metadata={"jd_sentence_matches": sentence_matches},
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scorers/test_experience.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/services/scorers/experience.py tests/test_scorers/test_experience.py
git commit -m "Add ExperienceScorer (TF-IDF + embedding paths, metadata for suggestions)"
```

---

## Task 10: `SeniorityScorer`

**Files:**
- Create: `app/services/scorers/seniority.py`
- Create: `tests/test_scorers/test_seniority.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_scorers/test_seniority.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scorers/test_seniority.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `seniority.py`**

Create `app/services/scorers/seniority.py`:

```python
import re
from datetime import date
from typing import List, Optional, Tuple

from models.analysis import DimensionScore, Gap
from models.job import JobDescription
from models.resume import Experience, Resume
from services.scorers.base import DimensionResult


# Order matters: ranges first so "3 to 5 years" parses as 5, not 3.
_PATTERNS = [
    re.compile(r"(\d+)\s*(?:-|to)\s*(\d+)\s*(?:\+)?\s*(?:years?|yrs?)", re.IGNORECASE),
    re.compile(r"at\s+least\s+(\d+)\s+(?:years?|yrs?)", re.IGNORECASE),
    re.compile(r"(\d+)\s*\+\s*(?:years?|yrs?)", re.IGNORECASE),
    re.compile(r"(\d+)\s+(?:years?|yrs?)", re.IGNORECASE),
]


def extract_required_years(text: str) -> Optional[int]:
    """Return the largest year value mentioned in the JD text, or None."""
    if not text:
        return None
    values: List[int] = []
    for pat in _PATTERNS:
        for m in pat.finditer(text):
            groups = [g for g in m.groups() if g is not None]
            values.extend(int(g) for g in groups if g.isdigit())
    return max(values) if values else None


def _merge_intervals(intervals: List[Tuple[date, date]]) -> List[Tuple[date, date]]:
    if not intervals:
        return []
    sorted_iv = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_iv[0]]
    for start, end in sorted_iv[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def sum_resume_years(experiences: List[Experience]) -> float:
    intervals: List[Tuple[date, date]] = []
    today = date.today()
    for exp in experiences:
        end = exp.end_date or today
        if end < exp.start_date:
            continue
        intervals.append((exp.start_date, end))
    merged = _merge_intervals(intervals)
    days = sum((e - s).days for s, e in merged)
    return round(days / 365.25, 1)


class SeniorityScorer:
    name = "seniority"
    default_weight = 0.15

    def applies(self, jd: JobDescription) -> bool:
        return extract_required_years(jd.description or "") is not None

    def score(self, resume: Resume, jd: JobDescription, ai: Optional[object]) -> DimensionResult:
        required = extract_required_years(jd.description or "")
        # applies() should have prevented this, but be defensive.
        if required is None:
            return DimensionResult(
                score=DimensionScore(
                    name=self.name,
                    score=100.0,
                    weight=self.default_weight,
                    rationale="No years requirement in JD",
                ),
                gaps=[],
            )

        resume_years = sum_resume_years(resume.experience)
        ratio = min(resume_years / required, 1.0) if required > 0 else 1.0
        score_pct = ratio * 100.0

        gaps: List[Gap] = []
        shortfall = max(0.0, required - resume_years)
        if shortfall >= 1.0:
            if shortfall >= 3.0:
                sev = "high"
            elif shortfall >= 1.5:
                sev = "medium"
            else:
                sev = "low"
            gaps.append(Gap(
                category="seniority",
                item=f"Role asks for {required}+ yrs; resume shows {resume_years} yrs",
                severity=sev,
            ))

        return DimensionResult(
            score=DimensionScore(
                name=self.name,
                score=score_pct,
                weight=self.default_weight,
                rationale=f"{resume_years} yrs vs required {required}",
            ),
            gaps=gaps,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scorers/test_seniority.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/services/scorers/seniority.py tests/test_scorers/test_seniority.py
git commit -m "Add SeniorityScorer (regex year extraction + interval merge)"
```

---

## Task 11: `EducationScorer`

**Files:**
- Create: `app/services/scorers/education.py`
- Create: `tests/test_scorers/test_education.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_scorers/test_education.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scorers/test_education.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `education.py`**

Create `app/services/scorers/education.py`:

```python
import re
from typing import Optional

from models.analysis import DimensionScore, Gap
from models.job import JobDescription
from models.resume import Resume
from services.scorers.base import DimensionResult


# Degree rank — higher number = higher degree.
_RANK_PATTERNS = [
    (4, re.compile(r"\b(phd|ph\.d|doctorate|doctoral)\b", re.IGNORECASE)),
    (3, re.compile(r"\b(master|m\.?s\.?|m\.?a\.?|mba)\b", re.IGNORECASE)),
    (2, re.compile(r"\b(bachelor|b\.?s\.?|b\.?a\.?|undergrad)\b", re.IGNORECASE)),
    (1, re.compile(r"\b(diploma|associate|high school|ged)\b", re.IGNORECASE)),
]

_RANK_NAMES = {0: "no degree", 1: "Diploma", 2: "Bachelor's", 3: "Master's", 4: "PhD"}


def rank_degree(text: str) -> int:
    if not text:
        return 0
    for rank, pat in _RANK_PATTERNS:
        if pat.search(text):
            return rank
    return 0


def _highest_resume_rank(resume: Resume) -> int:
    return max((rank_degree(e.degree) for e in resume.education), default=0)


def _jd_required_rank(jd: JobDescription) -> int:
    return rank_degree(jd.description or "")


class EducationScorer:
    name = "education"
    default_weight = 0.10

    def applies(self, jd: JobDescription) -> bool:
        return _jd_required_rank(jd) > 0

    def score(self, resume: Resume, jd: JobDescription, ai: Optional[object]) -> DimensionResult:
        required_rank = _jd_required_rank(jd)
        resume_rank = _highest_resume_rank(resume)

        if required_rank == 0:
            return DimensionResult(
                score=DimensionScore(
                    name=self.name,
                    score=100.0,
                    weight=self.default_weight,
                    rationale="No degree requirement in JD",
                ),
                gaps=[],
            )

        if resume_rank >= required_rank:
            return DimensionResult(
                score=DimensionScore(
                    name=self.name,
                    score=100.0,
                    weight=self.default_weight,
                    rationale=f"Resume {_RANK_NAMES[resume_rank]} meets/exceeds required {_RANK_NAMES[required_rank]}",
                ),
                gaps=[],
            )

        score_pct = (resume_rank / required_rank) * 100.0
        gap = Gap(
            category="education",
            item=f"Role expects {_RANK_NAMES[required_rank]}; resume shows {_RANK_NAMES[resume_rank]}",
            severity="medium",
        )
        return DimensionResult(
            score=DimensionScore(
                name=self.name,
                score=score_pct,
                weight=self.default_weight,
                rationale=f"Resume {_RANK_NAMES[resume_rank]} below required {_RANK_NAMES[required_rank]}",
            ),
            gaps=[gap],
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scorers/test_education.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/services/scorers/education.py tests/test_scorers/test_education.py
git commit -m "Add EducationScorer (degree rank comparison)"
```

---

## Task 12: `SummaryAlignmentScorer`

**Files:**
- Create: `app/services/scorers/summary.py`
- Create: `tests/test_scorers/test_summary.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_scorers/test_summary.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scorers/test_summary.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `summary.py`**

Create `app/services/scorers/summary.py`:

```python
import math
from typing import List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from models.analysis import DimensionScore, Gap
from models.job import JobDescription
from models.resume import Resume
from services.scorers.base import DimensionResult


_GAP_THRESHOLD = 60.0


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


class SummaryAlignmentScorer:
    name = "summary_alignment"
    default_weight = 0.10

    def applies(self, jd: JobDescription) -> bool:
        # applies() can't see the resume; the orchestrator additionally checks
        # `resume.summary is not None` before including this scorer's result
        # in dimension_scores. See Task 15.
        return bool(jd.description and jd.description.strip())

    def score(self, resume: Resume, jd: JobDescription, ai: Optional[object]) -> DimensionResult:
        summary = resume.summary or ""
        jd_desc = (jd.description or "").strip()

        if not summary.strip() or not jd_desc:
            return DimensionResult(
                score=DimensionScore(
                    name=self.name,
                    score=100.0,
                    weight=self.default_weight,
                    rationale="No summary or no JD description (no-op)",
                ),
                gaps=[],
            )

        ai_fallback = False
        score_pct: float = 0.0
        if ai is not None:
            try:
                vecs = ai.embed([summary, jd_desc])  # type: ignore[attr-defined]
                score_pct = max(0.0, min(100.0, _cosine(vecs[0], vecs[1]) * 100.0))
            except Exception:
                ai_fallback = True

        if ai is None or ai_fallback:
            vec = TfidfVectorizer().fit([summary, jd_desc])
            tfidf = vec.transform([summary, jd_desc])
            sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
            score_pct = max(0.0, min(100.0, float(sim) * 100.0))

        gaps: List[Gap] = []
        if score_pct < _GAP_THRESHOLD:
            gaps.append(Gap(
                category="summary_alignment",
                item="Resume summary doesn't strongly align with the role's emphasis",
                severity="low",
            ))

        rationale = f"summary/JD cosine = {score_pct:.0f}"
        if ai_fallback:
            rationale = "[fallback] " + rationale

        return DimensionResult(
            score=DimensionScore(
                name=self.name,
                score=score_pct,
                weight=self.default_weight,
                rationale=rationale,
            ),
            gaps=gaps,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scorers/test_summary.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/services/scorers/summary.py tests/test_scorers/test_summary.py
git commit -m "Add SummaryAlignmentScorer (TF-IDF + embedding paths)"
```

---

## Task 13: Wire scorers into REGISTRY

**Files:**
- Modify: `app/services/scorers/__init__.py`

- [ ] **Step 1: Replace `__init__.py`**

Replace the contents of `app/services/scorers/__init__.py` with:

```python
from services.scorers.education import EducationScorer
from services.scorers.experience import ExperienceScorer
from services.scorers.seniority import SeniorityScorer
from services.scorers.skills import SkillsScorer
from services.scorers.summary import SummaryAlignmentScorer


# Order is informational only — the orchestrator iterates and re-normalizes
# weights, so registry order does not affect the score.
REGISTRY = [
    SkillsScorer(),
    ExperienceScorer(),
    SeniorityScorer(),
    EducationScorer(),
    SummaryAlignmentScorer(),
]
```

- [ ] **Step 2: Smoke test the registry**

Run: `python -c "from app.services.scorers import REGISTRY; print([s.name for s in REGISTRY])"`
Expected output: `['skills', 'experience', 'seniority', 'education', 'summary_alignment']`

- [ ] **Step 3: Commit**

```bash
git add app/services/scorers/__init__.py
git commit -m "Wire scorers into REGISTRY"
```

---

## Task 14: `suggestions.py` (phase 1 templates + phase 2 LLM rewrites)

**Files:**
- Create: `app/services/suggestions.py`
- Create: `tests/test_suggestions.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_suggestions.py`:

```python
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
        # Optionally: still produce zero (template module only fires on gaps).
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
        # Need at least one gap to trigger phase 2 candidate selection.
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
        # Phase 1 still ships; phase 2 is silently skipped.
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_suggestions.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `suggestions.py`**

Create `app/services/suggestions.py`:

```python
import json
import logging
from typing import List, Optional

from models.analysis import Gap, Suggestion
from models.job import JobDescription
from models.resume import Resume
from services.scorers.base import DimensionResult

logger = logging.getLogger(__name__)


_REWRITE_PROMPT_SYSTEM = (
    "You are a senior resume coach. You will be given a job description's emphasis "
    "and three of the candidate's existing experience bullets. Suggest one improved "
    "version of each bullet that better aligns with the JD. "
    "CRITICAL RULE: Do not invent facts. Only rephrase or quantify what the user has "
    "already stated. If you cannot rewrite a bullet without invention, set 'suggested' to null. "
    "Output strictly a JSON array of objects, no surrounding prose. Each object has keys: "
    "target_section (string), original (string), suggested (string or null), reason (string)."
)

_PHASE1_TEMPLATES = {
    "skills": {
        "high": "Add '{item}' to your skills section — it's a required skill for this role.",
        "medium": "Consider adding '{item}' to your skills — it appears in the JD's description.",
        "low": "Consider mentioning '{item}' if you have any exposure to it.",
    },
    "experience": {
        "high": "The JD emphasizes '{item}'. None of your experience bullets address this — consider adding or rewriting one to cover it.",
        "medium": "The JD emphasizes '{item}'. Consider rewriting a bullet to highlight relevant work.",
        "low": "The JD mentions '{item}'. Consider whether any of your bullets could be tightened to call it out.",
    },
    "seniority": {
        "high": "{item}. Highlight any contracting, freelance, internship, or pre-degree work that could close the gap.",
        "medium": "{item}. Highlight any contracting or side projects that could close the gap.",
        "low": "{item}. Consider lightly emphasizing relevant early-career work.",
    },
    "education": {
        "high": "{item}. Consider listing relevant graduate coursework, certifications, or equivalent experience.",
        "medium": "{item}. Consider listing relevant coursework or certifications.",
        "low": "{item}. A line of relevant certification could help.",
    },
    "summary_alignment": {
        "high": "Rewrite your summary to lead with the role's key themes.",
        "medium": "Rewrite your summary to lead with the role's key themes.",
        "low": "Lightly adjust your summary to mention one or two of the role's key themes.",
    },
}


def _phase1(gaps: List[Gap]) -> List[Suggestion]:
    out: List[Suggestion] = []
    for g in gaps:
        template = _PHASE1_TEMPLATES.get(g.category, {}).get(g.severity)
        if not template:
            continue
        out.append(Suggestion(
            text=template.format(item=g.item),
            category="gap",
            priority=g.severity,
        ))
    return out


_GAP_SIMILARITY_THRESHOLD = 0.5  # Mirrors ExperienceScorer._GAP_THRESHOLD.


def _select_rewrite_candidates(
    dimension_results: List[DimensionResult],
    limit: int = 3,
) -> List[dict]:
    """From ExperienceScorer metadata, pick the (best-existing-bullet, gap-sentence)
    pairs that are *both* gap-flagged (similarity < threshold) and have the lowest
    similarity. These are the natural rewrite candidates per spec §7 phase 2.
    """
    matches: List[dict] = []
    for r in dimension_results:
        if r.score.name != "experience":
            continue
        sm = r.metadata.get("jd_sentence_matches", [])
        if not sm:
            continue
        weak = [m for m in sm if m.get("similarity", 0.0) < _GAP_SIMILARITY_THRESHOLD]
        weak_sorted = sorted(weak, key=lambda m: m.get("similarity", 0.0))
        matches.extend(weak_sorted)
    return matches[:limit]


def _phase2_rewrites(
    candidates: List[dict],
    jd: JobDescription,
    ai: object,
) -> List[Suggestion]:
    if not candidates:
        return []

    payload_lines = ["JD emphasis:", (jd.description or "")[:1500], "", "Existing bullets:"]
    for c in candidates:
        payload_lines.append(
            f"- target: {c['best_bullet_index']}\n  text: {c['best_bullet_text']}"
        )
    user_payload = "\n".join(payload_lines)

    try:
        raw = ai.complete(  # type: ignore[attr-defined]
            system=_REWRITE_PROMPT_SYSTEM,
            user=user_payload,
            max_tokens=600,
        )
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            return []
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Phase-2 suggestions skipped: %s", e)
        return []

    out: List[Suggestion] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        suggested = item.get("suggested")
        target = item.get("target_section")
        reason = item.get("reason", "")
        if not suggested or not isinstance(suggested, str):
            continue
        text = suggested if not reason else f"{suggested}  (Why: {reason})"
        out.append(Suggestion(
            text=text,
            category="rewrite",
            priority="medium",
            target_section=target if isinstance(target, str) else None,
        ))
    return out


def build_suggestions(
    resume: Resume,
    jd: JobDescription,
    gaps: List[Gap],
    dimension_results: List[DimensionResult],
    ai: Optional[object],
) -> List[Suggestion]:
    """Combine phase-1 templated suggestions with optional phase-2 LLM rewrites."""
    suggestions = _phase1(gaps)

    if ai is not None:
        candidates = _select_rewrite_candidates(dimension_results, limit=3)
        suggestions.extend(_phase2_rewrites(candidates, jd, ai))

    return suggestions
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_suggestions.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/services/suggestions.py tests/test_suggestions.py
git commit -m "Add suggestions module (phase-1 templates + phase-2 LLM rewrites)"
```

---

## Task 15: `analyzer.py` orchestrator + golden fixtures

**Files:**
- Create: `app/services/analyzer.py`
- Create: `tests/fixtures/__init__.py`
- Create: `tests/fixtures/golden.py`
- Create: `tests/test_analyzer.py`

- [ ] **Step 1: Create the fixtures package marker**

Create `tests/fixtures/__init__.py` with:

```python
# Golden (resume, JD) fixtures for analyzer integration tests.
```

- [ ] **Step 2: Create golden fixtures**

Create `tests/fixtures/golden.py`:

```python
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
```

- [ ] **Step 3: Write failing tests for the orchestrator**

Create `tests/test_analyzer.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_analyzer.py -v`
Expected: ImportError (`app.services.analyzer` doesn't exist).

- [ ] **Step 5: Implement `analyzer.py`**

Create `app/services/analyzer.py`:

```python
from typing import Dict, List

from models.analysis import AnalysisResponse, Gap
from models.job import JobDescription
from models.resume import Resume
from services.ai_client import get_ai_client
from services.scorers import REGISTRY
from services.scorers.base import DimensionResult
from services.suggestions import build_suggestions


def _renormalize(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return {k: 0.0 for k in weights}
    return {k: v / total for k, v in weights.items()}


def _scorer_applies_with_resume(scorer, resume: Resume, jd: JobDescription) -> bool:
    """Apply Scorer.applies(jd) plus dimension-specific resume checks.

    SummaryAlignmentScorer.applies takes only the JD, so the orchestrator
    handles the resume.summary-is-None check here to avoid leaking resume
    knowledge into every applies() method.
    """
    if not scorer.applies(jd):
        return False
    if scorer.name == "summary_alignment" and not (resume.summary and resume.summary.strip()):
        return False
    return True


def analyze(resume: Resume, jd: JobDescription) -> AnalysisResponse:
    ai = get_ai_client()
    warnings: List[str] = []

    active = [s for s in REGISTRY if _scorer_applies_with_resume(s, resume, jd)]
    weights = _renormalize({s.name: s.default_weight for s in active})

    results: List[DimensionResult] = []
    any_ai_used = False
    for scorer in active:
        result = scorer.score(resume, jd, ai)
        if ai is not None:
            if result.score.rationale.startswith("[fallback]"):
                warnings.append(f"{scorer.name} fell back to keyword-only")
            else:
                any_ai_used = True
        # Apply re-normalized weight onto the DimensionScore.
        result.score.weight = weights[scorer.name]
        results.append(result)

    if ai is None:
        mode = "keyword-only"
    elif not any_ai_used:
        # Every AI-using scorer fell back; effectively keyword-only.
        mode = "keyword-only"
    else:
        mode = "hybrid"

    overall = sum(r.score.score * r.score.weight for r in results)
    all_gaps: List[Gap] = [g for r in results for g in r.gaps]
    suggestions = build_suggestions(resume, jd, all_gaps, results, ai)

    return AnalysisResponse(
        mode=mode,
        overall_score=round(overall, 2),
        dimension_scores=[r.score for r in results],
        gaps=all_gaps,
        suggestions=suggestions,
        warnings=warnings,
        # Legacy aliases:
        match_score=round(overall, 2),
        missing_keywords=[g.item for g in all_gaps if g.category == "skills"],
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_analyzer.py -v`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/services/analyzer.py tests/fixtures/__init__.py tests/fixtures/golden.py tests/test_analyzer.py
git commit -m "Add analyzer orchestrator + golden fixtures + integration tests"
```

---

## Task 16: Wire into `resume_service.py` + update router tests

**Files:**
- Modify: `app/services/resume_service.py`
- Modify: `tests/test_resume_router.py`

- [ ] **Step 1: Shrink `analyze_resume_logic` to a wrapper**

Replace the contents of `app/services/resume_service.py` with:

```python
# Resume analysis business logic

from models.analysis import AnalysisResponse
from models.job import JobDescription
from models.resume import Resume
from services.analyzer import analyze
from utils.parser import extract_email, extract_name, extract_skills


def parse_resume(text: str):
    # Unchanged behavior; bugs in this function are tracked as separate tickets
    # (see spec section 1 non-goals).
    return {
        "name": extract_name(text),
        "email": extract_email(text),
        "skills": extract_skills(text),
    }


def analyze_resume_logic(resume: Resume, job: JobDescription) -> AnalysisResponse:
    return analyze(resume, job)
```

- [ ] **Step 2: Run the existing router tests to confirm legacy fields still pass**

Run: `pytest tests/test_resume_router.py -v`
Expected: all tests pass — the legacy fields (`match_score`, `missing_keywords`, `suggestions`) keep working because `AnalysisResponse` preserves them.

If `test_analyze_returns_high_match_score_for_perfect_match` fails because the new analyzer's overall score for the mock data is below 95, **do not loosen the test arbitrarily** — instead, replace just that one test with the version below (the mock resume only matches skills 1:1, but the experience/seniority/summary dimensions drag the holistic score down):

```python
    def test_analyze_returns_high_match_score_for_perfect_match(self, client, mock_resume, mock_job_description):
        """When resume.skills == jd.required_skills, the skills dimension scores 100.

        Note: under the holistic analyzer the overall score blends skills with
        experience/seniority/summary/education — so a 'perfect skills match'
        does NOT necessarily yield 95+ overall. We assert skills dimension == 100.
        """
        from fastapi import status
        resume = mock_resume.copy()
        resume["skills"] = mock_job_description["required_skills"]

        payload = {"resume": resume, "job_description": mock_job_description}
        response = client.post("/api/resume/analyze", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        skills_dim = next(
            (d for d in data["dimension_scores"] if d["name"] == "skills"),
            None,
        )
        assert skills_dim is not None
        assert skills_dim["score"] == 100.0
```

- [ ] **Step 3: Add new-shape assertions to `tests/test_resume_router.py`**

Append this class to `tests/test_resume_router.py`:

```python
class TestAnalyzeNewShape:
    """Assertions for the holistic analyzer's new response fields."""

    def test_response_has_mode_field(self, client, mock_resume, mock_job_description):
        from fastapi import status
        payload = {"resume": mock_resume, "job_description": mock_job_description}
        response = client.post("/api/resume/analyze", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["mode"] in ("hybrid", "keyword-only")

    def test_response_has_dimension_scores(self, client, mock_resume, mock_job_description):
        from fastapi import status
        payload = {"resume": mock_resume, "job_description": mock_job_description}
        response = client.post("/api/resume/analyze", json=payload)
        data = response.json()
        assert isinstance(data["dimension_scores"], list)
        assert len(data["dimension_scores"]) >= 1
        for d in data["dimension_scores"]:
            assert d["name"] in (
                "skills", "experience", "education", "seniority", "summary_alignment"
            )
            assert 0 <= d["score"] <= 100
            assert 0 <= d["weight"] <= 1

    def test_dimension_weights_sum_to_one(self, client, mock_resume, mock_job_description):
        from fastapi import status
        payload = {"resume": mock_resume, "job_description": mock_job_description}
        response = client.post("/api/resume/analyze", json=payload)
        data = response.json()
        total = sum(d["weight"] for d in data["dimension_scores"])
        assert abs(total - 1.0) < 1e-3

    def test_gaps_have_required_fields(self, client, mock_resume, mock_job_description):
        from fastapi import status
        # Use a JD with skills the resume lacks to force gaps.
        jd = dict(mock_job_description)
        jd["required_skills"] = mock_job_description["required_skills"] + ["MadeUpSkill"]
        payload = {"resume": mock_resume, "job_description": jd}
        response = client.post("/api/resume/analyze", json=payload)
        data = response.json()
        for g in data["gaps"]:
            assert g["category"] in (
                "skills", "experience", "education", "seniority", "summary_alignment"
            )
            assert g["severity"] in ("high", "medium", "low")
            assert isinstance(g["item"], str) and g["item"]

    def test_legacy_match_score_equals_overall_score(self, client, mock_resume, mock_job_description):
        from fastapi import status
        payload = {"resume": mock_resume, "job_description": mock_job_description}
        response = client.post("/api/resume/analyze", json=payload)
        data = response.json()
        assert data["match_score"] == data["overall_score"]
```

- [ ] **Step 4: Run the full test suite**

Run: `pytest -v`
Expected: every test passes — old and new.

- [ ] **Step 5: Manual smoke test of the running server**

```bash
cd app && uvicorn main:app --port 8001
```

In another shell, hit `/api/resume/analyze` with a small payload (use `/docs` Swagger UI or `curl`) and verify the response includes `mode`, `dimension_scores`, `gaps`, `suggestions`, **and** legacy `match_score` / `missing_keywords`.

Stop the server (Ctrl-C) when done.

- [ ] **Step 6: Commit**

```bash
git add app/services/resume_service.py tests/test_resume_router.py
git commit -m "Wire analyzer into resume_service; update router tests for new shape"
```

---

## Done

After Task 16, every requirement in the spec is implemented and tested. The `/api/resume/analyze` route is unchanged in signature; its response gained `mode`, `dimension_scores`, `gaps`, `suggestions`, and `warnings`, while preserving the legacy `match_score` and `missing_keywords` fields.

### Suggested follow-ups (out-of-scope tickets — see spec §1)
1. Fix broken email regex in `app/utils/parser.py`.
2. Fix `extract_skills` returning `set` (won't JSON-serialize).
3. Fix `/parse` parameter type (`request: str` → `ResumeRequest`).
4. Remove demo code from `app/utils/parser.py`.
5. Convert bare imports to `app.X` style to unify uvicorn + pytest run paths.
6. PDF → fully-populated `Resume` parser.
7. Batch ranking endpoint(s).
8. `/v2/analyze` route that drops legacy fields.


