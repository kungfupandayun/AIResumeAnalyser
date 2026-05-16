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

# Run a single test file / single test
pytest tests/test_resume_router.py
pytest tests/test_resume_router.py::TestAnalyzeEndpoint::test_analyze_with_valid_resume_and_job
```

Tests import the app via `from app.main import app` and rely on the project root being on `sys.path`. There is no lint/format/typecheck command configured.

## Architecture

FastAPI service that scores a resume against a job description. The runtime path is:

```
HTTP → app/routers/resume_router.py → app/services/resume_service.py → app/utils/{parser,pdfparser}.py
                                                  ↓
                                       Pydantic models in app/models/
```

Layer responsibilities:

- **`app/main.py`** — FastAPI app, CORS (currently `allow_origins=["*"]`), mounts `resume_router`. Single health route at `/`.
- **`app/routers/resume_router.py`** — three endpoints under `/api/resume`:
  - `POST /analyze` — takes a `Resume` and `JobDescription` as **two separate body params**, so clients must send `{"resume": {...}, "job_description": {...}}` (see `tests/test_resume_router.py` for the canonical payload shape).
  - `POST /parse` — currently declared as `request: str` (a query/form param), not the imported `ResumeRequest` model. Treat this as unfinished.
  - `POST /upload-resume` — multipart PDF upload → text extraction → `parse_resume`.
- **`app/services/resume_service.py`** — `analyze_resume_logic` does set-intersection scoring on lowercased skills (no TF-IDF / embeddings yet despite what the README and Implementation Plan describe). `parse_resume` orchestrates the parser helpers.
- **`app/utils/parser.py`** — spaCy-based name/email/skill extraction. `nlp = spacy.load("en_core_web_sm")` runs at **import time**, so importing this module is slow and requires the model to be installed. The module also contains leftover demo code (top-level `text = ...` and a `parseResume` function with `print` statements) — leave it alone unless cleaning up intentionally.
- **`app/utils/pdfparser.py`** — uses PyMuPDF (`fitz`); the `pdfplumber` variant is commented out.
- **`app/models/`** — Pydantic v2 schemas. `Resume` has rich nested models (`ContactInfo`, `Experience`, `Education`, `Project`) with strict validation; clients must satisfy these or get HTTP 422.

## Import path quirk (read before editing imports)

The `app/` package uses **bare relative-style imports**:

- `app/main.py` → `from routers.resume_router import router`
- `app/routers/resume_router.py` → `from models.resume import Resume`, `from services.resume_service import ...`

This means:

- `uvicorn` works only when run from inside `app/` (`uvicorn main:app`), not from the project root.
- `pytest` works from the project root because `from app.main import app` re-imports `app/main.py`, which then resolves the bare imports relative to whatever happens to be on `sys.path` at test time.

If you change an import, change it consistently across all modules in `app/`, or convert the whole package to `from app.xxx import ...` style and update the run instructions.

## Known rough edges

These are real bugs visible in the current code. Don't accidentally "preserve" them when editing — fix them deliberately or leave them, but be aware:

- `extract_email` regex is `r"[\\w\\.-]+@[\\w\\.-]+"` — the doubled backslashes match literal `\w`, not the word-character class, so it never matches a real email.
- `extract_skills` returns a Python `set`, which FastAPI/Pydantic will reject when serializing the `parse_resume` response. Convert to `list` if wiring it through an endpoint.
- `/parse` accepts `request: str` (treated as a query/form param) rather than the imported `ResumeRequest` body model.
- `app/core/config.py` is empty; there is no central settings object yet — `OPENAI_API_KEY` is documented in the README but not actually loaded anywhere in code.
- The README/Implementation Plan promise TF-IDF + OpenAI embeddings + AI suggestions; the current `analyze_resume_logic` is plain set intersection with hardcoded suggestion strings. Treat the docs as roadmap, not as a description of current behaviour.

## Testing notes

- `tests/conftest.py` provides `client`, `mock_resume`, and `mock_job_description` fixtures — reuse these instead of constructing payloads from scratch.
- `pytest.ini` defines `slow`, `unit`, `integration` markers (none currently applied in the test suite).
