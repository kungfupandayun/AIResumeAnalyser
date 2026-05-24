# Stateless Web UI for the Resume Analyzer — Design

**Date:** 2026-05-24
**Status:** Approved for implementation planning
**Scope:** Add a React-based frontend that drives the existing `POST /api/resume/analyze` endpoint. No persistence, no accounts, no history. The first slice of a larger "full-stack analyzer" effort; subsequent specs will cover persistence, PDF upload pipeline, and deployment.

---

## 1. Goal & Non-goals

### Goal
A single-page web UI that lets a user enter a structured resume and a job description, click **Analyze**, and see the existing `AnalysisResponse` (overall score, dimension breakdown, gaps, suggestions) rendered in a useful way. The frontend talks only to the existing backend; no backend changes are required for v1.

### Non-goals (explicitly out of scope for this spec)
1. **Persistence** — no DB, no saved analyses, no history. State lives in React for the session and disappears on reload.
2. **User accounts / auth.**
3. **PDF upload** — `POST /api/resume/upload-resume` exists but `parse_resume` produces only a partial Resume. Wiring it up would require fixing the parser bugs first; that's its own sub-project.
4. **Free-text resume / JD intake with LLM extraction.** Users provide structured input (resume = form fields; JD = title + description text + manual required-skills tags).
5. **Backend changes.** No new endpoints, no schema changes, no router changes. The existing `POST /api/resume/analyze` contract is taken as fixed.
6. **Deployment.** Dev workflow only (`vite dev` + `uvicorn`). Production hosting, FastAPI-serves-static-dist, CI, etc. are a later sub-project.
7. **Auto-generated TypeScript types from OpenAPI.** v1 hand-mirrors the Pydantic models; auto-gen is a v2 win.
8. **E2E tests, visual regression tests, accessibility audits.** Component + hook tests + one integration smoke test are the v1 bar.

These get their own specs after this work lands.

---

## 2. Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | **React + Vite + TypeScript** as the frontend stack. | Industry-standard SPA stack; fast dev server; type safety against the API contract; mature tooling. |
| D2 | **Tailwind CSS + shadcn/ui** for styling and components. | Copy-in (not npm-installed) accessible components built on Radix primitives. We own the code, so customization is straightforward. Covers form, input, tag, badge, card, alert out of the box. |
| D3 | Frontend lives in a new top-level **`frontend/`** directory, sibling to `app/`. | Keeps the Python backend untouched. Standard monorepo shape. |
| D4 | **Vite dev proxy** forwards `/api/*` to `http://localhost:8000`. | App code calls `fetch("/api/resume/analyze", ...)` with no CORS handling and no env-specific base URL. |
| D5 | **Structured form** for resume input, mirroring the existing `Resume` Pydantic model 1:1. | Zero backend changes; lowest risk. Friction is a v1-acceptable trade-off until free-text intake exists. |
| D6 | **Paste JD text + manual required-skills tag input** for JD. | Matches how users encounter real JDs (copy from LinkedIn) and guarantees `SkillsScorer` has something to compare against (without it, skills always scores 100). |
| D7 | **Single-page layout**: resume left, JD right, centered Analyze button, full-width results section below. | Settled visually in brainstorming (`.superpowers/brainstorm/.../layout-v2.html`). Stacks vertically on mobile. |
| D8 | **Internal React structure = feature components + one hook** (not single-file, not feature folders + state library). | Smallest structure that keeps `App.tsx` a layout file and each component independently testable. |
| D9 | **Hand-mirrored `types.ts`**, with a comment pointing at `app/models/analysis.py` as source of truth, plus one integration test using a real-shape `AnalysisResponse`. | Cheap drift safety net without adding OpenAPI codegen tooling. |
| D10 | **Test stack = Vitest + React Testing Library + MSW.** | Vite-native runner, user-centric component queries, network-level API stubs. |

---

## 3. Repo layout

```
AIResumeAnalyser/
├─ app/                           # existing FastAPI backend (untouched)
├─ frontend/                      # NEW
│  ├─ src/
│  │  ├─ App.tsx                  # layout shell + top-level state
│  │  ├─ main.tsx
│  │  ├─ index.css                # Tailwind directives
│  │  ├─ types.ts                 # Resume, JobDescription, AnalysisResponse
│  │  ├─ components/
│  │  │  ├─ ResumeForm.tsx
│  │  │  ├─ JdForm.tsx
│  │  │  ├─ Results.tsx
│  │  │  └─ ui/                   # shadcn-generated primitives
│  │  ├─ hooks/
│  │  │  └─ useAnalyze.ts
│  │  └─ lib/
│  │     └─ api.ts                # fetch wrapper, error normalization
│  ├─ tests/                      # Vitest + RTL test files mirror src/ tree
│  ├─ index.html
│  ├─ vite.config.ts              # /api proxy → http://localhost:8000
│  ├─ tailwind.config.ts
│  ├─ postcss.config.cjs
│  ├─ tsconfig.json
│  └─ package.json
├─ docs/
└─ ...
```

`frontend/` has its own `package.json` and `tsconfig.json` and is self-contained. The Python project's tooling does not need to know about it.

---

## 4. Component contracts

Each component is pure and controlled. The hook owns the API call. `App.tsx` is the wiring layer.

### `<ResumeForm>`
```ts
type Props = {
  value: Resume;
  onChange: (next: Resume) => void;
  fieldErrors?: Record<string, string>;  // path → message
};
```
- Renders: name, contact (email/phone/location + optional linkedin/github/portfolio URLs), summary textarea, skills tag input, experience array (with `+ Add another` and per-row delete), education array, projects array (optional).
- Pure presentation. Calls `onChange` with the next full `Resume` on every keystroke.
- `fieldErrors` is keyed by dotted path (e.g. `"contact.email"`, `"experience[0].descriptions"`); messages render inline next to the offending field.

### `<JdForm>`
```ts
type Props = {
  value: JobDescription;
  onChange: (next: JobDescription) => void;
  fieldErrors?: Record<string, string>;
};
```
- Renders: title input, description textarea, required-skills tag input (comma or Enter to add, click-X to remove).
- Same pure controlled pattern.

### `<Results>`
```ts
type Props = {
  data: AnalysisResponse | null;
  loading: boolean;
  error: string | null;
};
```
- Three render states:
  - **Empty** (`data === null && !loading && !error`): nothing distracting (a hint like "Click Analyze to see results").
  - **Loading first run** (`data === null && loading`): skeleton placeholders.
  - **Populated** (`data !== null`): four panels — overall score, dimension breakdown, gaps, suggestions. If `loading` is also true (re-run with previous data still mounted), render a small "refreshing…" badge.
- Reads `data.mode`: renders a small **"AI-enhanced"** or **"Keyword-only"** badge next to the overall score.
- If `data.warnings` is non-empty, render a yellow alert above the panels.
- If `error` is non-null, render a red alert in place of (or above) the panels.

### `useAnalyze()`
```ts
function useAnalyze(): {
  data: AnalysisResponse | null;
  loading: boolean;
  error: string | null;                  // network / 5xx / other
  fieldErrors: Record<string, string>;   // 422 detail flattened
  analyze: (resume: Resume, jd: JobDescription) => Promise<void>;
};
```
- Owns `POST /api/resume/analyze` with body `{ resume, job_description: jd }` (the existing router's two-body-key shape — see `tests/test_resume_router.py`).
- 422 → flatten FastAPI's `{ detail: [{ loc, msg }, ...] }` into `fieldErrors` keyed by dotted path. Strips the `"body"` and top-level model prefix from `loc`.
- 5xx / network error → `error` populated.
- Aborts in-flight requests via `AbortController` when `analyze` is re-invoked; the cancelled call resolves silently and does not update state.
- Previous `data` is kept across re-runs (set `loading=true`, leave `data` populated).

### `App.tsx`
- Owns `resume: Resume` and `jd: JobDescription` state with defaults that satisfy the form's minimum-valid shape (see §6).
- Renders the layout shell (header → two-column inputs → centered Analyze button → results section).
- Disables Analyze while `loading` or while inputs fail the minimum-valid check.
- On click: `analyze(resume, jd)`.

---

## 5. Data flow & error handling

### Happy path
1. User types in either form → top-level `resume` / `jd` state updates on each keystroke.
2. User clicks **Analyze**. Button disables; `useAnalyze.analyze(resume, jd)` fires.
3. `POST /api/resume/analyze` with `{ resume, job_description: jd }`.
4. 200 OK → `data = AnalysisResponse`, `loading=false`, `error=null`, `fieldErrors={}`. `<Results>` re-renders.
5. User edits a field and clicks Analyze again → previous `data` stays mounted, `loading=true` triggers the "refreshing…" badge, new result swaps in on resolve.

### Error matrix
Every failure has a defined render target so the user knows what to fix.

| Failure | Render target |
|---|---|
| `422 Unprocessable Entity` | Hook populates `fieldErrors`; `<ResumeForm>` / `<JdForm>` show messages inline next to each offending field. No top-level alert. |
| `500` from `try/except Exception` in the router | Red alert at top of `<Results>`: "Analysis failed: {detail}". |
| Network error / fetch reject | Red alert: "Couldn't reach the analyzer. Is the backend running?" |
| Aborted (re-click) | Silently swallowed — no error rendered. |
| `data.warnings` non-empty | Yellow alert at top of `<Results>`, data still renders normally. |
| `data.mode === "keyword-only"` | Small "Keyword-only mode" badge next to the overall score, not an alert. |

### Pre-submit edge cases
- **Minimum-valid gate (Analyze button disabled until satisfied).** The button stays disabled until every backend-required constraint passes, so the user never sees a 422 for something the UI could have caught. The check covers:
  - `resume.name` non-empty
  - `resume.contact.email` parses as an email (`EmailStr`)
  - `resume.contact.phone` matches `^[0-9\-\+\(\)\s]+$`
  - `resume.contact.location` non-empty
  - `resume.skills.length >= 1` (schema `min_length=1`)
  - Each `resume.experience[i]`: `title`, `company`, valid `start_date` (ISO date), `descriptions.length >= 1` with each entry non-empty
  - Each `resume.education[i]`: `degree`, `institution` non-empty
  - `jd.title` non-empty
  - `jd.description` present (string or explicit `null` — `Optional[str]` with no default is treated as required by Pydantic v2)
  - `jd.required_skills` present (list or explicit `null` — same reason)

  When disabled, render a small "Required fields missing" hint near the button. We do **not** auto-create empty array rows behind the user's back.
- **No `required_skills` in JD.** Backend silently scores skills 100. The skills dimension bar in `<Results>` renders an inline notice: *"No required skills listed in the JD — add some for a meaningful skills score."* This is the only place we surface a known UX-confusing backend behavior.
- **Empty `resume.experience` list.** Schema-allowed but `ExperienceScorer` returns 0 with a high-severity gap. We don't block this in the gate — the score itself communicates the problem.

---

## 6. Initial form state (the "empty-but-valid skeleton")

To make `+ Add another` meaningful (clone-an-existing-row) and the empty form non-broken, `App.tsx` initializes state as:

```ts
// Note on dates: the TS Experience type permits `start_date: string | null` and
// `end_date: string | null` during editing. The minimum-valid gate (§5) ensures
// `null` start_dates can't be submitted. On submit, dates are serialized as
// ISO `YYYY-MM-DD` strings, which Pydantic's `date` accepts.
const initialResume: Resume = {
  name: "",
  contact: { email: "", phone: "", location: "" },
  summary: null,
  skills: [],                     // populated via tag input
  experience: [
    { title: "", company: "", start_date: null, end_date: null, descriptions: [""] },
  ],
  education: [],
  projects: [],
};

const initialJd: JobDescription = {
  title: "",
  description: "",
  required_skills: [],
};
```

Pre-rendering one empty experience row gives the user something visible to fill in and a template for `+ Add another` to clone.

---

## 7. Testing strategy

**Stack:** Vitest, React Testing Library, MSW.

### What to test
- **`useAnalyze` hook**: 200 → data populated, loading flips. 422 → `fieldErrors` populated, FastAPI `loc` flattening is correct. 500 → `error` populated. Abort behavior: two rapid calls, only the latest result lands.
- **`<ResumeForm>`**: renders all field labels. `+ Add another experience` appends an empty row. `fieldErrors` render next to the matching field by dotted path. Tag input adds on Enter and removes on click-X.
- **`<JdForm>`**: tag input behavior, field error rendering.
- **`<Results>`**: empty / loading / populated states each render correctly. `mode === "keyword-only"` shows the badge. Non-empty `warnings` shows the yellow alert. Skills dimension shows the "no required skills" notice when `data.gaps` for skills is empty AND the JD had no required skills.
- **`App.tsx` (integration smoke test)**: render `<App>`, fill in a minimum-valid resume + JD using the same fixture shape as `tests/conftest.py:mock_resume`, click Analyze, MSW returns a canned `AnalysisResponse`, assert the overall score number appears on screen.

### What to skip in v1
- E2E (Playwright/Cypress).
- Visual regression tests.
- Re-testing backend behavior from the frontend — backend has its own pytest suite.

### Contract drift safety net
Two cheap mitigations against `types.ts` drifting from `app/models/analysis.py`:
1. The integration smoke test's MSW fixture uses a real-shape `AnalysisResponse` (copied from a successful backend test run). Any backend response-shape change surfaces as a TypeScript error.
2. Top-of-file comment in `types.ts` pointing at `app/models/analysis.py` as the source of truth.

---

## 8. Dev workflow

```bash
# Terminal 1: backend
cd app && uvicorn main:app --reload   # http://localhost:8000

# Terminal 2: frontend
cd frontend && npm install            # one-time
cd frontend && npm run dev            # http://localhost:5173

# Vite proxy forwards /api/* → http://localhost:8000
# Browser → http://localhost:5173
```

Frontend tests: `cd frontend && npm test`. Backend tests are unchanged: `pytest` from project root.

`.gitignore` additions: `frontend/node_modules/`, `frontend/dist/`, `frontend/.vite/`, `frontend/coverage/`.

---

## 9. What this spec does NOT decide (deferred to writing-plans or later specs)

- Exact shadcn/ui components to scaffold (the implementation plan picks what to copy in).
- Exact Tailwind theme (colors, spacing scale) — picked during build.
- Whether to use React Hook Form vs plain controlled state — implementation detail. Either works with the contracts in §4.
- Production deployment topology — its own sub-project.
- Auto-generated TS types from OpenAPI — its own sub-project once contract drift becomes a real pain.
