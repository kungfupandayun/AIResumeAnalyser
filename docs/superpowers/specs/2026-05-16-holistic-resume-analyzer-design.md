# Holistic Resume Analyzer — Design

**Date:** 2026-05-16
**Status:** Approved for implementation planning
**Scope:** Replace the naive set-intersection scoring in `app/services/resume_service.py::analyze_resume_logic` with a holistic, multi-dimensional analyzer that produces actionable suggestions.

---

## 1. Goal & Non-goals

### Goal
`POST /api/resume/analyze` returns a richer assessment of how well a resume fits a job description: an overall score, a per-dimension breakdown, categorized gaps with severity, and prioritized suggestions (including LLM-generated bullet rewrites when an OpenAI key is available). The system degrades gracefully to keyword-only behavior when OpenAI is unavailable.

### Non-goals (explicitly out of scope for this spec)
1. Fixing the broken email regex in `app/utils/parser.py:55` (`r"[\\w\\.-]+@[\\w\\.-]+"` matches nothing real).
2. `extract_skills` returning a `set` (won't JSON-serialize — affects `/parse`, not `/analyze`).
3. `/parse` declaring `request: str` instead of the imported `ResumeRequest` body model.
4. Stray top-level demo code in `app/utils/parser.py`.
5. Bare-import quirk in `app/main.py` (requires `cd app && uvicorn main:app`).
6. Batch ranking (one resume vs many JDs, or vice versa).
7. Persistence / DB.
8. PDF → fully-populated `Resume` parsing (current `parse_resume` only extracts name/email/skills crudely).

These get their own tickets after this work lands.

---

## 2. Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Use **whole-resume vs whole-JD** signals (skills, experience text, education, seniority, summary alignment). | Single most leverage-bearing decision — anything narrower isn't "holistic". |
| D2 | **OpenAI preferred, deterministic fallback** (the `hybrid` / `keyword-only` modes). | Matches the original Implementation Plan's promise; service stays up when OpenAI is down. |
| D3 | Response shape is **nested** (sub-scores, categorized gaps, prioritized suggestions, `mode` flag). | A single flat number can't represent a holistic analysis. |
| D4 | Suggestions = **gap-pointing + LLM phrasing rewrites**. **No full-resume rewrite mode** in v1. | Avoids LLM-fabrication risk while still giving the user concrete edits. |
| D5 | Seniority in scope, **deterministic only** (regex for JD years, date math for resume years). | Cheap, covers the most common rejection reason. LLM-assisted seniority extraction is YAGNI. |
| D6 | Architecture = **scorer-per-dimension registry**. | Each dimension's with-AI / without-AI fork stays in one ≤100-line file; scorers are independently unit-testable. |
| D7 | Synonyms **YAML-loaded** from a config file, not inline. | Allows non-code edits to expand the synonym set. |
| D8 | Keep `match_score` and `missing_keywords` as **legacy aliases** on `AnalysisResponse` for one minor release. | Existing `test_resume_router.py` keeps passing; gives clients time to migrate. |
| D9 | Sequential scorer execution in v1 (no `asyncio.gather`). | At most 2 OpenAI round-trips per request — parallelism is YAGNI now. |
| D10 | No caching, no streaming in v1. | Premature. Add Redis / SSE once `/analyze` is actually hot. |

---

## 3. Architecture

### File layout

```
app/
  models/
    analysis.py              ★ replace AnalysisResponse with nested shape
  services/
    analyzer.py              ★ NEW — orchestrator (replaces analyze_resume_logic)
    ai_client.py             ★ NEW — OpenAI wrapper + circuit breaker; returns None on failure
    suggestions.py           ★ NEW — phase-1 templates + phase-2 LLM rewrites
    scorers/
      __init__.py            ★ NEW — REGISTRY list
      base.py                ★ NEW — Scorer protocol + DimensionResult
      skills.py              ★ NEW
      experience.py          ★ NEW
      seniority.py           ★ NEW
      education.py           ★ NEW
      summary.py             ★ NEW
    resume_service.py        ★ shrinks — analyze_resume_logic = 3-line wrapper around analyzer.analyze; parse_resume unchanged
  core/
    config.py                ★ populate — Pydantic Settings reading OPENAI_API_KEY, models, weights
  data/
    synonyms.yaml            ★ NEW — flat YAML, canonical skill → aliases
  routers/
    resume_router.py         (unchanged — body and route stay the same; response model becomes richer)
tests/
  test_analyzer.py           ★ NEW — orchestrator: weighting, applies() filtering, mode flip
  test_scorers/
    test_skills.py           ★ NEW
    test_experience.py       ★ NEW
    test_seniority.py        ★ NEW
    test_education.py        ★ NEW
    test_summary.py          ★ NEW
  test_suggestions.py        ★ NEW
  test_ai_client.py          ★ NEW — circuit breaker open/close, timeout handling
  fixtures/                  ★ NEW — golden (resume, JD) pairs
  test_resume_router.py      ★ updated assertions; keep legacy-field checks
  test_models.py             ★ extend for new response shape
```

### New / changed dependencies

Add to `requirements.txt`:
- `pyyaml` — load `synonyms.yaml`
- `pydantic-settings>=2.0,<2.1` — required by the new `core/config.py`; constrained to <2.1 because `pydantic` is pinned to 2.5.0 and `pydantic-settings` ≥2.7 requires `pydantic>=2.7.0`
- `rapidfuzz` — fuzzy match in `SkillsScorer` fallback path

Already present in `requirements.txt` and used here: `spacy`, `scikit-learn`, `openai`, `pydantic`, `python-dotenv`.

---

## 4. Response schema

```python
class DimensionScore(BaseModel):
    name: Literal["skills","experience","education","seniority","summary_alignment"]
    score: float          # 0-100
    weight: float         # 0-1, contribution to overall (after re-normalization)
    rationale: str        # 1-line "why this score"

class Gap(BaseModel):
    category: Literal["skills","experience","education","seniority","summary_alignment"]
    item: str             # "Kubernetes" or "Role asks 5+ yrs; resume shows 3.2"
    severity: Literal["high","medium","low"]

class Suggestion(BaseModel):
    text: str
    category: Literal["gap","rewrite","structure","keyword"]
    priority: Literal["high","medium","low"]
    target_section: Optional[str] = None   # e.g. "experience[0].descriptions[1]" for rewrites

class AnalysisResponse(BaseModel):
    mode: Literal["hybrid","keyword-only"]
    overall_score: float                    # 0-100, weighted sum of dimension_scores
    dimension_scores: list[DimensionScore]
    gaps: list[Gap]
    suggestions: list[Suggestion]
    warnings: list[str] = []                # e.g. ["SkillsScorer fell back to keyword-only"]
    # Legacy aliases (deprecation: drop in v2):
    match_score: float                      # = overall_score
    missing_keywords: list[str]             # = [g.item for g in gaps if g.category == "skills"]
```

### Default dimension weights (overridable via env)

| Dimension | Weight |
|---|---|
| `skills` | 0.35 |
| `experience` | 0.30 |
| `seniority` | 0.15 |
| `summary_alignment` | 0.10 |
| `education` | 0.10 |

When a scorer's `applies(jd) is False`, its weight is removed and the remaining weights are re-normalized to sum to 1.0.

---

## 5. Scorer details

### Common contract — `app/services/scorers/base.py`

```python
class DimensionResult(BaseModel):
    score: DimensionScore         # 0-100, weight, rationale
    gaps: list[Gap]
    metadata: dict[str, Any] = {} # internal-only; not included in AnalysisResponse.
                                  # ExperienceScorer uses this to pass its per-JD-sentence
                                  # similarity matrix to the suggestions module.

class Scorer(Protocol):
    name: str                 # one of the Literal values
    default_weight: float

    def applies(self, jd: JobDescription) -> bool: ...
    def score(self, resume: Resume, jd: JobDescription, ai: AIClient | None) -> DimensionResult: ...
```

`AIClient | None` is the fallback knob. When `ai is None`, every scorer takes its keyword-only path. When `ai` is set but the AI call throws, the scorer catches, logs a warning, and falls back to the keyword-only path *for itself only* — the response surfaces a string in `warnings` and keeps `mode = "hybrid"` (only fully-failed runs flip `mode` to `"keyword-only"`).

### `SkillsScorer`

- **Without AI:** lowercase + spaCy lemmatize both `resume.skills` and `jd.required_skills`. Apply synonym dict (`kubernetes` ≈ `k8s` ≈ `container orchestration`). RapidFuzz `partial_ratio ≥ 85` → matched.
- **With AI:** for any remaining unmatched JD skill, embed it + all resume skills; cosine ≥ 0.80 → matched. Catches `Postgres` ↔ `PostgreSQL`, `CI/CD` ↔ `GitHub Actions`.
- **Score:** `(matched / total_jd_skills) × 100`.
- **Gaps:** each unmatched JD skill — `severity = high` if it appeared in `jd.required_skills`, `medium` if only mined from `jd.description` (via spaCy noun-chunk extraction matched against the synonym dict keys).
- **`applies()`** — always True.

### `ExperienceScorer`

- **Inputs:** `Experience.descriptions` ∪ `Project.contributions` as the resume side; sentence-split `jd.description` as the JD side.
- **Without AI:** TF-IDF (sklearn `TfidfVectorizer`) over the combined corpus; cosine each JD sentence against each resume bullet; per-JD-sentence top-1 similarity.
- **With AI:** embedding cosine instead of TF-IDF. Catches paraphrase ("scaled distributed systems" ↔ "built microservices serving 10k req/s").
- **Score:** `mean(top1_sim per JD sentence) × 100`.
- **Gaps:** each JD sentence whose best resume match is < 0.5 — `severity = medium`, `item` = the JD sentence (truncated to 200 chars).
- **`applies()`** — True if `jd.description` non-empty and resume has ≥1 experience bullet, else False.

### `SeniorityScorer` (deterministic only — D5)

- **JD parsing:** regex pack on `jd.description`:
  - `(\d+)\+?\s*years?`
  - `(\d+)\s*to\s*(\d+)\s*years?`
  - `at least\s+(\d+)\s+years?`
  - `(\d+)\+?\s+yrs?`
  Take the largest year value found.
- **Resume side:** sum non-overlapping `Experience` intervals — sweep-line merge over `(start_date, end_date or date.today())`. Total = sum of merged interval widths in years (rounded to 1 decimal).
- **Score:** `min(resume_years / required, 1.0) × 100`.
- **Gap:** if shortfall ≥ 1.0 year → single gap. Severity = `high` if shortfall ≥ 3 yrs, `medium` if ≥ 1.5 yrs, `low` otherwise.
- **`applies()`** — False if no year value parsed from JD (dimension absent from response, weight redistributed).

### `EducationScorer`

- **JD parsing:** keyword set on `jd.description`: `phd`, `doctorate`, `master`, `m.s.`, `m.a.`, `mba`, `bachelor`, `b.s.`, `b.a.`. Rank: `phd > master > bachelor > other`.
- **Resume side:** highest degree in `resume.education` (rank-mapped from `Education.degree` string).
- **Score:** 100 if resume rank ≥ JD rank, else `(resume_rank / jd_rank) × 100`.
- **Gap:** if resume below required — `"Role expects Master's; resume shows Bachelor's"`, severity `medium`.
- **`applies()`** — False if no degree keyword found in JD.
- **No AI path** — keyword-rank comparison is already correct; LLM adds nothing here in v1.

### `SummaryAlignmentScorer`

- **Without AI:** TF-IDF cosine between `resume.summary` and `jd.description` × 100.
- **With AI:** embedding cosine of the same two strings × 100.
- **Gap:** if score < 60 → `"Resume summary doesn't lead with what this role emphasizes (X, Y, Z)"` where X/Y/Z are the top-3 noun chunks from the JD that don't appear in the summary. Severity `low`.
- **`applies()`** — False if `resume.summary is None`.

### Threshold summary (all empirically tunable later)

| Threshold | Where | Value |
|---|---|---|
| Synonym fuzzy match | SkillsScorer (keyword path) | RapidFuzz partial_ratio ≥ 85 |
| Embedding match | SkillsScorer (AI path) | cosine ≥ 0.80 |
| Experience bullet match | ExperienceScorer | cosine < 0.5 → gap |
| Summary alignment gap | SummaryAlignmentScorer | score < 60 → gap |
| Seniority shortfall → gap | SeniorityScorer | shortfall ≥ 1.0 yr |
| Circuit breaker trip | AIClient | ≥ 3 failures in 60 s |
| Embedding call timeout | AIClient | 20 s |
| Chat completion timeout | AIClient | 30 s |

---

## 6. AI client (`app/services/ai_client.py`)

```python
class AIClient:
    def embed(self, texts: list[str]) -> list[list[float]]: ...   # batched single call
    def complete(self, system: str, user: str, *, max_tokens: int) -> str: ...

def get_ai_client() -> AIClient | None:
    if not settings.OPENAI_API_KEY:
        return None
    if _circuit_breaker.is_open():        # ≥3 failures in last 60s → open
        return None
    return AIClient(settings.OPENAI_API_KEY, settings.EMBED_MODEL, settings.CHAT_MODEL)
```

- **Models (configurable):** `text-embedding-3-small` (cheap, 1536-dim), `gpt-4o-mini` (cheap, fast).
- **Circuit breaker:** 3 failures in 60 s opens; closes 60 s after the last attempt. Prevents one outage from making every request slow.
- **AI calls are batched within each scorer.** Each AI-using scorer issues at most one `embed()` call (its inputs batched into a single request). Worst case per analysis: 3 embed calls (skills + experience + summary) + 1 chat completion call (suggestion rewrites) = 4 round-trips. Cross-scorer batching is intentionally out of scope for v1 — adds coupling for a marginal latency win.
- **Failure handling:** every AI method is wrapped in try/except at the call site (inside each scorer). On exception → warning logged, scorer treats `ai = None` for that call.

---

## 7. Suggestions (`app/services/suggestions.py`)

Two phases.

### Phase 1 — rule-based gap suggestions (always runs)

For every gap, generate a `Suggestion` from a template keyed on `gap.category` + `gap.severity`. Examples:

| Gap | Suggestion |
|---|---|
| `skills`, high | `"Add 'Kubernetes' to your skills section — it's a required skill for this role."` |
| `seniority` | `"Role asks for 5+ years; your resume shows ~3.2. Highlight contracting, freelance, or pre-degree work that could close the gap."` |
| `experience` | `"The JD emphasizes 'X'. None of your experience bullets address this — consider adding or rewriting one to cover it."` |
| `summary_alignment` | `"Rewrite your summary to lead with [top 3 JD keywords]."` |
| `education` | `"Role expects a Master's; consider listing relevant graduate coursework or certifications."` |

Each suggestion: `category="gap"`, `priority` mirrors gap severity.

### Phase 2 — LLM bullet rewrites (only when `ai is not None`)

One chat completion. Input: extracted JD keywords + the top-3 gap-flagged JD sentences (those with no resume bullet matching ≥ 0.5 — already surfaced as `Gap` items by `ExperienceScorer`) + the user's existing experience bullets that *best* match each of those gap JD sentences (i.e., the closest existing bullet to each gap; these are the natural rewrite candidates). Output: JSON list of `{target_section, original, suggested, reason}`.

To make these candidates available without recomputing similarities, `ExperienceScorer` returns its per-JD-sentence similarity matrix on `DimensionResult.metadata` (`dict[str, Any]`, defaulting to `{}` on the base type) keyed as `{"jd_sentence_matches": [{"jd_sentence": str, "best_bullet_index": str, "best_bullet_text": str, "similarity": float}]}`. `metadata` is not serialized on the public `AnalysisResponse` — it stays inside the analyzer pipeline.

**Prompt constraint (load-bearing):** *"Do not invent facts; only rephrase or quantify what the user has already stated. If you cannot rewrite without invention, return null for `suggested`."*

If the LLM returns malformed JSON or any item with `suggested is null` → that item is skipped. Phase 1 suggestions still ship.

---

## 8. Orchestrator (`app/services/analyzer.py`)

```python
def analyze(resume: Resume, jd: JobDescription) -> AnalysisResponse:
    ai = get_ai_client()
    mode = "hybrid" if ai else "keyword-only"
    warnings: list[str] = []

    active = [s for s in REGISTRY if s.applies(jd)]
    weights = renormalize({s.name: s.default_weight for s in active})

    results: list[DimensionResult] = []
    any_ai_used = False
    for scorer in active:
        result = scorer.score(resume, jd, ai)
        # scorer reports back whether it fell back; aggregate into warnings
        if ai and result.score.rationale.startswith("[fallback]"):
            warnings.append(f"{scorer.name} fell back to keyword-only")
        else:
            any_ai_used = True
        # apply re-normalized weight
        result.score.weight = weights[scorer.name]
        results.append(result)

    if ai and not any_ai_used:
        mode = "keyword-only"

    overall = sum(r.score.score * r.score.weight for r in results)
    gaps = [g for r in results for g in r.gaps]
    suggestions = build_suggestions(resume, jd, gaps, results, ai)

    return AnalysisResponse(
        mode=mode,
        overall_score=overall,
        dimension_scores=[r.score for r in results],
        gaps=gaps,
        suggestions=suggestions,
        warnings=warnings,
        match_score=overall,
        missing_keywords=[g.item for g in gaps if g.category == "skills"],
    )
```

`REGISTRY` is a module-level list in `scorers/__init__.py`: `[SkillsScorer(), ExperienceScorer(), SeniorityScorer(), EducationScorer(), SummaryAlignmentScorer()]`.

---

## 9. Configuration (`app/core/config.py`)

```python
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OPENAI_API_KEY: str | None = None
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

settings = Settings()
```

Synonyms file format (`app/data/synonyms.yaml`):

```yaml
kubernetes:
  - k8s
  - container orchestration
postgresql:
  - postgres
  - pg
javascript:
  - js
  - ecmascript
ci/cd:
  - continuous integration
  - github actions
  - jenkins
# … (~30-50 entries to start)
```

If the file is missing or malformed at startup → hard fail at app boot (fail loud, not silent).

---

## 10. Error handling

| Failure | Where caught | User-visible |
|---|---|---|
| Pydantic request-body validation | FastAPI default | HTTP 422 |
| `OPENAI_API_KEY` unset | `get_ai_client()` returns `None` | HTTP 200, `mode: "keyword-only"` |
| OpenAI down (all calls fail) | Each scorer catches, logs, falls back | HTTP 200, `mode: "keyword-only"`, `warnings` populated |
| One scorer's AI call fails | Same — degraded for that one dimension only | HTTP 200, `mode: "hybrid"`, `warnings` lists the dimension |
| Synonyms YAML missing/malformed | `_load_synonyms()` raises at import | App refuses to start |
| Resume has no `summary` | `SummaryAlignmentScorer.applies()` returns False | Dimension absent from response; remaining weights re-normalized |
| JD has no years requirement | `SeniorityScorer.applies()` returns False | Same as above |
| LLM returns malformed JSON for rewrites | `suggestions.py` catches | Phase-1 suggestions still ship; phase-2 silently skipped |
| Analyzer crash (bug) | FastAPI exception handler | HTTP 500 |

---

## 11. Testing

### Conventions
- **AI is faked, not mocked.** `FakeAIClient` fixture returns deterministic fake embeddings (hash-based stable vectors) and canned chat responses. Lets the AI path be tested without OpenAI access.
- **Real OpenAI** only hit in a separate `@pytest.mark.integration` suite gated on `OPENAI_API_KEY`.
- **Each scorer test runs both paths**: parametrized over `[None, fake_ai_client]`.
- **Golden fixtures** in `tests/fixtures/`: 5 (resume, JD) pairs covering strong match, weak match, missing summary, no-years JD, JD with rich free-text description.
- **Asserts use ranges, not exact values** (e.g. `assert 80 <= overall_score <= 100`) so threshold tuning doesn't break tests.

### Test files (per layout above)

| File | Covers |
|---|---|
| `test_analyzer.py` | Orchestrator: registry iteration, `applies()` filtering, weight re-normalization, mode flip, warnings aggregation |
| `test_scorers/test_skills.py` | Synonyms, RapidFuzz threshold, embedding fallback path |
| `test_scorers/test_experience.py` | TF-IDF & embedding paths, JD sentence splitting, top-1 aggregation |
| `test_scorers/test_seniority.py` | Regex pack edge cases, overlapping intervals, current-job (`end_date=None`) handling |
| `test_scorers/test_education.py` | Degree rank parsing both sides |
| `test_scorers/test_summary.py` | Both paths, missing-summary → `applies()` False |
| `test_suggestions.py` | Phase-1 templates per category, phase-2 JSON parsing, malformed-JSON handling |
| `test_ai_client.py` | Circuit breaker open/close, timeout handling |
| `test_resume_router.py` | Updated to new shape; **keep** existing legacy-field assertions (`match_score`, `missing_keywords`) |
| `test_models.py` | New response-model validation |

---

## 12. Migration / rollout

1. Old `analyze_resume_logic` becomes a 3-line wrapper around `analyzer.analyze(resume, jd)` — no router signature changes.
2. Legacy fields `match_score` and `missing_keywords` stay on `AnalysisResponse` for one minor release. Mark deprecated in OpenAPI description.
3. Follow-up ticket: introduce `POST /api/resume/v2/analyze` that omits the legacy fields. Leave `v1` returning 410 with a pointer when ready.
4. No data migration (service is stateless).
