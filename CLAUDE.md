# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

```bash
# Install dependencies + spaCy model (required once)
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Run the API (NOTE: see "Import path quirk" below — must run from inside app/)
cd app && uvicorn main:app --reload
# The README's `uvicorn app.main:app --reload` from the project root will fail
# because app/main.py uses bare imports (`from routers...` instead of `from app.routers...`).

# Run all tests (from project root)
pytest

# Run a single test file / single test / single test method
pytest tests/test_analyzer.py
pytest tests/test_resume_router.py::TestAnalyzeEndpoint::test_analyze_with_valid_resume_and_job

# Run only scorer tests
pytest tests/test_scorers/
```

`pytest.ini` sets `pythonpath = app`, which is what makes the bare imports in `app/` resolve under pytest. There is no lint/format/typecheck command configured.

The OpenAI integration reads `OPENAI_API_KEY` from `.env` (or the environment) via `app/core/config.py`. With no key set, the analyzer runs in `keyword-only` mode — every scorer takes its non-AI path and tests still pass.

## Architecture

FastAPI service that scores a resume against a job description across **five weighted dimensions**. Each dimension is a `Scorer` Protocol implementation; the orchestrator iterates them, optionally calls the LLM, and assembles a single `AnalysisResponse`.

```
HTTP /api/resume/analyze
  → routers/resume_router.py
  → services/resume_service.analyze_resume_logic  (thin pass-through)
  → services/analyzer.analyze                     (orchestrator)
       │
       ├── get_ai_client()  →  AIClient | None   (circuit breaker gate)
       │
       ├── for each Scorer in REGISTRY:
       │     if scorer.applies(jd): scorer.score(resume, jd, ai)
       │       → DimensionResult { DimensionScore, [Gap], metadata }
       │
       └── build_suggestions(...)  →  [Suggestion]
            - phase 1: templated suggestions per Gap
            - phase 2 (AI only): rewrite candidates from ExperienceScorer metadata
```

### The five scorers

All live in `app/services/scorers/` and are registered in `__init__.py:REGISTRY`. Each has a `name`, `default_weight`, `applies(jd)`, and `score(resume, jd, ai)`.

| Scorer | Default weight | AI path | Keyword fallback |
|---|---|---|---|
| `skills` (35%) | required-skill coverage % | embeddings cosine ≥ 0.80 rescues unmatched | synonyms YAML + rapidfuzz `partial_ratio` ≥ 85 |
| `experience` (30%) | avg top-1 JD-sentence ↔ bullet similarity | OpenAI embeddings | scikit-learn `TfidfVectorizer` + cosine |
| `seniority` (15%) | years-of-experience comparison | n/a (deterministic) | regex year extraction + interval merge over `Experience` dates |
| `education` (10%) | degree-rank comparison vs JD-extracted requirement | n/a | deterministic |
| `summary_alignment` (10%) | summary↔JD cosine | OpenAI embeddings | TF-IDF + cosine |

### `applies()` filtering + weight renormalization

`Scorer.applies(jd)` can drop a dimension (e.g. `SeniorityScorer` returns False when the JD lists no years). The orchestrator **renormalizes the weights of the remaining scorers** so they sum to 1.0 — registry order is informational only.

One exception: `SummaryAlignmentScorer.applies` only sees the JD, so the orchestrator additionally drops it when `resume.summary` is empty (see `analyzer._scorer_applies_with_resume`). Don't push that special case into the scorer itself.

### AI mode + circuit breaker

`services/ai_client.py` exposes a module-level `CircuitBreaker` (threshold + sliding window from `Settings`). Every `embed` / `complete` call records success/failure; once open, `get_ai_client()` returns `None` and the orchestrator runs every scorer keyword-only.

Per-call failures (timeouts, JSON parse errors in phase-2 suggestions, etc.) are caught **inside the scorer**, which sets its rationale to `[fallback] ...`. The orchestrator then reports `mode = "keyword-only"` if either no AI client was available OR every AI-using scorer fell back. Tests assert on this mode flip via `monkeypatch.setattr("app.services.analyzer.get_ai_client", ...)`.

### Suggestions module (`services/suggestions.py`)

Two phases, both producing `Suggestion` objects:

1. **Phase 1 (always runs):** template-fills `_PHASE1_TEMPLATES[gap.category][gap.severity]` for every `Gap`.
2. **Phase 2 (AI only):** picks up to 3 weakest `(jd_sentence, resume_bullet)` pairs from `ExperienceScorer`'s `metadata["jd_sentence_matches"]`, sends them to the chat model with a strict "do not invent facts" system prompt, and parses a JSON array. Any parse error or empty result silently skips this phase.

This is why `DimensionResult` has a `metadata: dict` field — it's how `ExperienceScorer` hands its similarity matrix to `build_suggestions` without recomputation. `metadata` is intentionally NOT included in `AnalysisResponse`.

### Response shape

`AnalysisResponse` (in `app/models/analysis.py`) has the new holistic shape (`mode`, `overall_score`, `dimension_scores`, `gaps`, `suggestions`, `warnings`) **plus** legacy aliases `match_score` (= `overall_score`) and `missing_keywords` (= skills-category gap items) kept for one minor release. Tests assert both shapes — don't remove the aliases without updating the router tests.

## Import path quirk (read before editing imports)

The `app/` package uses **bare imports** throughout:

- `app/main.py` → `from routers.resume_router import router`
- `app/services/analyzer.py` → `from models.analysis import ...`, `from services.scorers import REGISTRY`

This means:

- `uvicorn` works only when run from inside `app/` (`uvicorn main:app`), not from the project root.
- `pytest` works because `pytest.ini` sets `pythonpath = app`. Tests import via `from app.services.analyzer import analyze` AND scorers internally import `from services.scorers.base import ...`.

### conftest module-aliasing (the gotcha)

Because both `app.models.analysis` and bare `models.analysis` are importable, Pydantic v2 would normally see them as **two different classes** with incompatible identities — a `DimensionResult` constructed from one wouldn't `isinstance`-match the other, and tests would fail with confusing validation errors.

`tests/conftest.py:_seed_app_module_aliases()` solves this by pre-importing every bare module and registering it in `sys.modules` under both keys (`models.analysis` and `app.models.analysis` point to the same module object). It also wires submodule attributes onto the `app` package so that `monkeypatch.setattr("app.services.analyzer.get_ai_client", ...)` can traverse the attribute chain.

**If you add a new module under `app/`, add it to the `bare_prefixes` list in conftest.** Otherwise tests that monkeypatch it will silently fail.

If you ever convert the package to fully-qualified `from app.xxx import ...` imports, you can delete this whole mechanism — and update the uvicorn invocation in this file at the same time.

## Settings (`app/core/config.py`)

`Settings(BaseSettings)` is loaded once at import time. Values flow from `.env` → environment → defaults. Touch points worth knowing:

- `OPENAI_API_KEY` (optional) — absent → keyword-only mode
- `EMBED_MODEL` / `CHAT_MODEL` — `text-embedding-3-small` / `gpt-4o-mini`
- `WEIGHT_*` — per-dimension default weights (currently the scorer classes hardcode the same numbers; keep them in sync)
- `AI_CIRCUIT_THRESHOLD`, `AI_CIRCUIT_WINDOW_S` — circuit breaker tuning
- `SYNONYMS_PATH` — resolves to `app/data/synonyms.yaml`

## Test fixtures

- `tests/conftest.py` provides `client`, `mock_resume`, `mock_job_description`, `fake_ai_client`, `fake_ai_with_completion(canned: str)` — reuse these instead of constructing payloads.
- `FakeAIClient` (also in conftest) produces deterministic 16-dim SHA256-derived unit-vector embeddings, so embedding-path assertions are stable across runs.
- `tests/fixtures/golden.py` exports named resume/JD pairs (`strong_match`, `weak_match`, `no_summary`, `no_years_in_jd`, `rich_jd`) used by `test_analyzer.py` integration tests.

## Design references

- `docs/superpowers/specs/2026-05-16-holistic-resume-analyzer-design.md` — the authoritative design spec (scoring rubric, gap semantics, mode-flip rules).
- `docs/superpowers/plans/2026-05-16-holistic-resume-analyzer.md` — the task-by-task implementation plan that produced the current code.

Prefer these over `README.md` and `Implementation Plan.txt`, which describe an older vision.

## Frontend (`frontend/`)

React + Vite + TypeScript SPA that drives `POST /api/resume/analyze`. Lives in `frontend/` (sibling to `app/`), fully self-contained Node project.

### Dev workflow

```bash
# Terminal 1: backend (unchanged)
cd app && uvicorn main:app --reload   # http://localhost:8000

# Terminal 2: frontend
cd frontend && npm install            # one-time
cd frontend && npm run dev            # http://localhost:5173
```

Vite's `server.proxy` forwards `/api/*` to `http://localhost:8000`, so frontend code calls `fetch("/api/resume/analyze", ...)` with no env-specific base URL and no CORS handling.

Frontend tests: `cd frontend && npx vitest run` (CI mode) or `npm test` (watch mode).

### Architecture

- `src/App.tsx` — layout shell + top-level `resume` / `jd` state + minimum-valid gate.
- `src/components/ResumeForm.tsx`, `JdForm.tsx`, `Results.tsx` — pure controlled presentation components.
- `src/components/TagInput.tsx` — custom Enter/comma tag input (shadcn has no primitive for this).
- `src/components/ui/` — shadcn-generated primitives (button, input, textarea, label, card, badge, alert).
- `src/hooks/useAnalyze.ts` — owns API call, abort, loading/data/error/fieldErrors state.
- `src/lib/api.ts` — fetch wrapper. Splits errors into `ApiFieldError` (422), `ApiServerError` (5xx), `ApiNetworkError`. Flattens FastAPI's `detail[i].loc` into dotted paths.
- `src/types.ts` — hand-mirrored from `app/models/resume.py`, `app/models/job.py`, `app/models/analysis.py`. **Update this file whenever those Pydantic models change.**

### PII posture (don't regress)

`Resume` no longer accepts `name`, `email`, `phone`, or arbitrary `location`. The model has `ConfigDict(extra='forbid')` so any client trying to send those fields gets a 422. The frontend never renders inputs for them. `parse_resume()` in `app/services/resume_service.py` also drops `name` and `email` from its return dict. If you re-add any of these, update `docs/superpowers/specs/2026-05-24-stateless-web-ui-design.md` §3.1 first.

### Tests + drift safety

- `frontend/tests/App.test.tsx` integration smoke test uses a real-shape `AnalysisResponse` in MSW. Any backend response-shape change should surface as a TypeScript error in this file or in `types.ts` consumers.
- Top of `frontend/src/types.ts` points at the backend models as source of truth.
- `frontend/tests/setup.ts` contains a `PatchedRequest` shim that strips cross-realm `AbortSignal` instances before they reach undici's `Request` constructor — works around a jsdom 25 + Node 24 + MSW 2.x incompatibility. Production code is untouched.

## Known rough edges

These are real bugs visible in the current code. Don't accidentally "preserve" them when editing — fix them deliberately or leave them, but be aware:

- `app/utils/parser.py:extract_email` regex is `r"[\\w\\.-]+@[\\w\\.-]+"` — the doubled backslashes match literal `\w`, not the word-character class, so it never matches a real email.
- `extract_skills` returns a Python `set`, which FastAPI/Pydantic will reject when serializing the `parse_resume` response. Convert to `list` if wiring it through an endpoint.
- `parser.py` also contains leftover demo code (top-level `text = ...` and a `parseResume` function with `print` statements). It runs `spacy.load("en_core_web_sm")` at import time, so importing `parser.py` is slow and requires the model.
- `/parse` accepts `request: str` (treated as a query/form param) rather than the imported `ResumeRequest` body model — unfinished.
- `routers/resume_router.py:analyze_resume` wraps everything in `try/except Exception` and re-raises as 500, which swallows FastAPI's 422 validation responses for malformed Pydantic input. Tolerate this when reading tests; fix if you need real 422s.

The `parse_resume` bugs are explicitly out of scope for the holistic-analyzer work (see spec §1 non-goals). They're tracked as separate tickets.
