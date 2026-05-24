# Stateless Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a React + Vite + TypeScript frontend that drives the existing `POST /api/resume/analyze` endpoint, plus a focused backend edit that removes PII fields (name, email, phone) from the `Resume` schema and reduces `location` to an optional `country`.

**Architecture:** Frontend is a single-page SPA in `frontend/` (sibling to `app/`). `App.tsx` owns top-level `resume` and `jd` state and wires three pure components (`<ResumeForm>`, `<JdForm>`, `<Results>`). A `useAnalyze()` hook owns the API call, loading/error state, and field-error mapping for 422s. Tailwind + shadcn/ui handles styling and accessible primitives. A tiny custom `<TagInput>` covers skills/required-skills (shadcn has no tag primitive).

**Tech Stack:** React 18, Vite 5, TypeScript 5, Tailwind CSS 3, shadcn/ui (Radix-based), Vitest, React Testing Library, MSW v2.

**Conventions specific to this repo (READ FIRST):**
- Backend imports inside `app/` are **bare** (e.g. `from models.resume import Resume`). Backend test imports use `from app.X` because `pytest.ini` sets `pythonpath = app`. Match these conventions in any backend edits.
- Run backend: `cd app && uvicorn main:app --reload` (http://localhost:8000)
- Run frontend: `cd frontend && npm run dev` (http://localhost:5173). Vite proxy forwards `/api/*` → `http://localhost:8000`.
- Run backend tests: `pytest` from project root.
- Run frontend tests: `cd frontend && npm test` (Vitest) — non-watch CI mode is `npm test -- --run`.
- The design spec is `docs/superpowers/specs/2026-05-24-stateless-web-ui-design.md` — re-read §3.1 (backend PII removal) and §4 (component contracts) before starting.
- The backend `try/except Exception` wrapper in `routers/resume_router.py:analyze_resume` swallows 422s into 500s. The plan does not touch this. The hook treats 422 specially by parsing FastAPI's `detail` shape regardless of HTTP code (see Task 7).

---

## File map

**Backend — modify:**
- `app/models/resume.py` — drop `name`, drop `ContactInfo` class, add `country: Optional[str] = None`, add `model_config = ConfigDict(extra='forbid')` on `Resume`
- `tests/conftest.py` — update `mock_resume` (drop `name` + `contact`, add `country`)
- `tests/fixtures/golden.py` — drop `ContactInfo` import + `_contact` helper, drop `name=` + `contact=` from every `Resume(...)` constructor, optionally add `country=`
- `tests/test_models.py` — no model-shape tests for Resume exist there today; verify nothing references the removed fields

**Backend — no test changes expected:**
- `tests/test_resume_router.py` — uses `mock_resume` fixture; updates flow through automatically
- `tests/test_scorers/*` — scorers don't read PII fields
- `tests/test_analyzer.py` — uses golden fixtures; updates flow through

**Frontend — create:**
- `frontend/package.json`
- `frontend/tsconfig.json`
- `frontend/tsconfig.node.json`
- `frontend/vite.config.ts`
- `frontend/tailwind.config.ts`
- `frontend/postcss.config.cjs`
- `frontend/vitest.config.ts`
- `frontend/index.html`
- `frontend/.gitignore`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/index.css`
- `frontend/src/types.ts`
- `frontend/src/lib/utils.ts` — shadcn's `cn()` helper
- `frontend/src/lib/api.ts` — fetch wrapper + error normalization
- `frontend/src/hooks/useAnalyze.ts`
- `frontend/src/components/ui/*` — shadcn primitives (button, input, textarea, label, card, badge, alert)
- `frontend/src/components/TagInput.tsx`
- `frontend/src/components/Results.tsx`
- `frontend/src/components/JdForm.tsx`
- `frontend/src/components/ResumeForm.tsx`
- `frontend/tests/setup.ts`
- `frontend/tests/mocks/handlers.ts`
- `frontend/tests/mocks/server.ts`
- `frontend/tests/lib/api.test.ts`
- `frontend/tests/hooks/useAnalyze.test.tsx`
- `frontend/tests/components/TagInput.test.tsx`
- `frontend/tests/components/Results.test.tsx`
- `frontend/tests/components/JdForm.test.tsx`
- `frontend/tests/components/ResumeForm.test.tsx`
- `frontend/tests/App.test.tsx`

**Root — modify:**
- `CLAUDE.md` — add a "Frontend" section with dev workflow

---

## Task overview (15 tasks)

1. **Backend PII removal** — model + test fixture updates, all `pytest` green
2. **Scaffold Vite + React + TypeScript** in `frontend/`, verify dev server
3. **Tailwind CSS setup** — `tailwind.config.ts`, `postcss.config.cjs`, `index.css` directives
4. **shadcn/ui init + primitives** — `components.json`, `lib/utils.ts`, scaffold needed UI components
5. **Vitest + RTL + MSW setup** — `vitest.config.ts`, `tests/setup.ts`, MSW server boilerplate
6. **`types.ts`** — Resume / JobDescription / AnalysisResponse mirroring backend
7. **`lib/api.ts`** — `analyze()` fetch wrapper + 422 normalization (TDD)
8. **`hooks/useAnalyze.ts`** — loading/data/error/fieldErrors + abort (TDD)
9. **`components/Results.tsx`** — empty/loading/populated states + mode badge + warnings (TDD)
10. **`components/TagInput.tsx`** — Enter/comma to add, click-X to remove (TDD)
11. **`components/JdForm.tsx`** — title + description textarea + TagInput (TDD)
12. **`components/ResumeForm.tsx`** — country + summary + skills TagInput + experience/education/projects arrays with add/delete (TDD)
13. **`App.tsx`** — layout shell, top-level state, minimum-valid gate, wire components
14. **`App.test.tsx`** — integration smoke test (fill form → click Analyze → MSW responds → score renders)
15. **Update `CLAUDE.md`** — frontend section + dev workflow

---

Tasks 1–15 follow below. Each step is 2–5 minutes of work.

## Task 1: Backend PII removal

**Files:**
- Modify: `app/models/resume.py`
- Modify: `tests/conftest.py`
- Modify: `tests/fixtures/golden.py`

This task is not pure-TDD: the existing test suite already exercises the model via fixtures, so we update the model and the fixtures together, then run the full suite as the verification step.

- [ ] **Step 1: Rewrite `app/models/resume.py`**

Replace the file's entire contents with:

```python
from pydantic import BaseModel, HttpUrl, Field, ConfigDict
from typing import List, Optional, Annotated
from datetime import date


class Experience(BaseModel):
    title: Annotated[str, Field(description="Job title", min_length=1)]
    company: Annotated[str, Field(description="Company name", min_length=1)]
    location: Annotated[Optional[str], Field(default=None, description="Work location")]
    start_date: Annotated[date, Field(description="Start date of employment")]
    end_date: Annotated[Optional[date], Field(default=None, description="End date or current position")]
    descriptions: Annotated[List[str], Field(description="List of job responsibilities and achievements", min_length=1)]


class Education(BaseModel):
    degree: Annotated[str, Field(description="Degree name (e.g., Bachelor, Master)", min_length=1)]
    institution: Annotated[str, Field(description="University or institution name", min_length=1)]
    graduation_year: Annotated[Optional[int], Field(default=None, description="Graduation year", ge=1900, le=2100)]
    gpa: Annotated[Optional[float], Field(default=None, description="GPA if applicable", ge=0, le=4)]


class Project(BaseModel):
    name: Annotated[str, Field(description="Project name", min_length=1)]
    tech_stack: Annotated[List[str], Field(description="Technologies used", min_length=1)]
    description: Annotated[str, Field(description="Project description", min_length=1)]
    contributions: Annotated[List[str], Field(description="Your specific contributions", min_length=1)]
    link: Annotated[Optional[HttpUrl], Field(default=None, description="Project repository or demo URL")]


class Resume(BaseModel):
    # PII intentionally not collected: no name, no email, no phone, no street/city.
    # Only `country` (optional) is retained from location info.
    model_config = ConfigDict(extra='forbid')

    country: Annotated[Optional[str], Field(default=None, description="Country only — PII like name/email/phone is intentionally not collected")]
    summary: Annotated[Optional[str], Field(default=None, description="Professional summary or objective")]
    skills: Annotated[List[str], Field(description="List of technical and soft skills", min_length=1)]
    experience: Annotated[List[Experience], Field(description="Work experience history")]
    education: Annotated[List[Education], Field(description="Educational background")]
    projects: Annotated[Optional[List[Project]], Field(default=[], description="Notable projects")]
```

Note: `ContactInfo` class is fully removed. `EmailStr` import is removed. `Resume` no longer has `name` or `contact`.

- [ ] **Step 2: Update `tests/conftest.py:mock_resume`**

Find the `mock_resume` fixture (returns a dict). Remove the `"name"` and `"contact"` keys. Add `"country": "United States"`. The fixture should now look like:

```python
@pytest.fixture
def mock_resume():
    """Mock resume data for testing"""
    return {
        "country": "United States",
        "summary": "Senior Software Engineer with 8+ years of experience in Python, FastAPI, and cloud technologies",
        "skills": [
            "Python", "FastAPI", "AWS", "Docker", "Kubernetes", "PostgreSQL",
            "JavaScript", "React", "Git", "CI/CD", "Microservices", "REST APIs"
        ],
        "experience": [
            {
                "title": "Senior Backend Engineer",
                "company": "Tech Corp",
                "location": "San Francisco, CA",
                "start_date": "2022-01-15",
                "end_date": None,
                "descriptions": [
                    "Led development of scalable microservices using FastAPI",
                    "Managed AWS infrastructure and deployment pipelines",
                    "Mentored junior developers on best practices"
                ]
            },
            {
                "title": "Backend Engineer",
                "company": "StartUp Inc",
                "location": "Remote",
                "start_date": "2019-06-01",
                "end_date": "2021-12-31",
                "descriptions": [
                    "Developed REST APIs using FastAPI and Flask",
                    "Implemented Docker containerization for microservices",
                    "Set up CI/CD pipelines using GitHub Actions"
                ]
            }
        ],
        "education": [
            {
                "degree": "Bachelor of Science",
                "institution": "University of California",
                "graduation_year": 2019,
                "gpa": 3.8
            }
        ],
        "projects": [
            {
                "name": "AI Resume Analyzer",
                "tech_stack": ["Python", "FastAPI", "spaCy", "OpenAI"],
                "description": "Tool that analyzes resumes against job descriptions",
                "contributions": [
                    "Designed architecture for text processing pipeline",
                    "Implemented keyword matching algorithm",
                    "Integrated OpenAI API for suggestion generation"
                ],
                "link": "https://github.com/johndoe/ai-resume-analyzer"
            }
        ]
    }
```

- [ ] **Step 3: Update `tests/fixtures/golden.py`**

Replace the file's entire contents with:

```python
from datetime import date

from app.models.job import JobDescription
from app.models.resume import (
    Education,
    Experience,
    Project,
    Resume,
)


def strong_match():
    """Senior Python engineer applying to a senior Python role — should score high."""
    resume = Resume(
        country="United States",
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
        country="United States",
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
        country="United States",
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

Note: `ContactInfo` is removed from the import list and the `_contact()` helper is deleted.

- [ ] **Step 4: Run the full backend test suite**

Run from project root: `pytest -q`
Expected: all tests pass. The router, analyzer, and scorer tests use the updated fixtures transparently.

If any test fails with `name` / `contact` / `email` references, grep for the broken reference and remove it (it should only exist in `mock_resume` and `golden.py`, both updated above). If `extra='forbid'` causes a test to fail because a payload includes a removed field, that test is asserting on the old shape — update it to the new shape.

- [ ] **Step 5: Commit**

```bash
git add app/models/resume.py tests/conftest.py tests/fixtures/golden.py
git commit -m "Remove PII from Resume schema (drop name/contact, add country)"
```

---

## Task 2: Scaffold Vite + React + TypeScript

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/vite.config.ts`, `frontend/index.html`, `frontend/.gitignore`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/index.css`

**Prerequisite:** Node.js ≥ 20 installed. Verify with `node --version`. If missing, install from https://nodejs.org/ before proceeding.

- [ ] **Step 1: Create `frontend/` and the bare entry files**

From project root, create the directory:

```bash
mkdir -p frontend/src
```

Create `frontend/.gitignore`:

```
node_modules/
dist/
.vite/
coverage/
*.log
```

Create `frontend/package.json`:

```json
{
  "name": "ai-resume-analyzer-frontend",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.6.3",
    "vite": "^5.4.10"
  }
}
```

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src", "tests"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `frontend/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts", "vitest.config.ts"]
}
```

Create `frontend/vite.config.ts`:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

Create `frontend/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AI Resume Analyzer</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `frontend/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

Create `frontend/src/App.tsx` (placeholder — real implementation lands in Task 13):

```tsx
export default function App() {
  return <main className="p-8">Resume Analyzer (scaffold)</main>;
}
```

Create `frontend/src/index.css` (empty for now — Tailwind directives land in Task 3):

```css
/* Tailwind directives added in Task 3 */
```

- [ ] **Step 2: Install dependencies**

```bash
cd frontend && npm install
```

Expected: completes with no errors; `node_modules/` populated.

- [ ] **Step 3: Verify dev server starts**

In one terminal:

```bash
cd frontend && npm run dev
```

Expected output includes `Local: http://localhost:5173/`. Open the URL in a browser; you should see the text "Resume Analyzer (scaffold)". Stop the server (Ctrl+C).

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "Scaffold Vite + React + TypeScript frontend"
```

---

## Task 3: Tailwind CSS setup

**Files:**
- Create: `frontend/tailwind.config.ts`, `frontend/postcss.config.cjs`
- Modify: `frontend/src/index.css`, `frontend/package.json`

- [ ] **Step 1: Install Tailwind + PostCSS**

```bash
cd frontend && npm install -D tailwindcss@^3.4.14 postcss@^8.4.49 autoprefixer@^10.4.20
```

- [ ] **Step 2: Create `frontend/tailwind.config.ts`**

```ts
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {},
  },
  plugins: [],
} satisfies Config;
```

- [ ] **Step 3: Create `frontend/postcss.config.cjs`**

```js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 4: Replace `frontend/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 5: Smoke-test by adding Tailwind classes**

Temporarily edit `frontend/src/App.tsx`:

```tsx
export default function App() {
  return <main className="p-8 text-2xl font-bold text-blue-600">Resume Analyzer (scaffold)</main>;
}
```

Run `npm run dev`, confirm the text is large, bold, blue. Then revert to the simpler version:

```tsx
export default function App() {
  return <main className="p-8">Resume Analyzer (scaffold)</main>;
}
```

Stop the dev server.

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "Add Tailwind CSS to frontend"
```

---

## Task 4: shadcn/ui init + primitives

**Files:**
- Create: `frontend/components.json`, `frontend/src/lib/utils.ts`, `frontend/src/components/ui/*.tsx` (button, input, textarea, label, card, badge, alert)
- Modify: `frontend/tailwind.config.ts`, `frontend/src/index.css`, `frontend/package.json`

shadcn/ui is a "copy-in" library — components are scaffolded as source files in your repo, not installed from npm.

- [ ] **Step 1: Install shadcn runtime deps**

```bash
cd frontend && npm install class-variance-authority clsx tailwind-merge lucide-react tailwindcss-animate
npm install -D @types/node
```

- [ ] **Step 2: Create `frontend/src/lib/utils.ts`**

```ts
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 3: Create `frontend/components.json`**

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/index.css",
    "baseColor": "slate",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui"
  }
}
```

- [ ] **Step 4: Replace `frontend/tailwind.config.ts` with the shadcn-aware version**

```ts
import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: { center: true, padding: "2rem", screens: { "2xl": "1400px" } },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
        secondary: { DEFAULT: "hsl(var(--secondary))", foreground: "hsl(var(--secondary-foreground))" },
        destructive: { DEFAULT: "hsl(var(--destructive))", foreground: "hsl(var(--destructive-foreground))" },
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        accent: { DEFAULT: "hsl(var(--accent))", foreground: "hsl(var(--accent-foreground))" },
        card: { DEFAULT: "hsl(var(--card))", foreground: "hsl(var(--card-foreground))" },
      },
      borderRadius: { lg: "var(--radius)", md: "calc(var(--radius) - 2px)", sm: "calc(var(--radius) - 4px)" },
    },
  },
  plugins: [animate],
} satisfies Config;
```

- [ ] **Step 5: Replace `frontend/src/index.css` with theme variables**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --primary: 222.2 47.4% 11.2%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 222.2 84% 4.9%;
    --radius: 0.5rem;
  }
}

@layer base {
  * { @apply border-border; }
  body { @apply bg-background text-foreground; }
}
```

- [ ] **Step 6: Scaffold the shadcn primitives we need**

Use the shadcn CLI to copy in each component:

```bash
cd frontend
npx shadcn@latest add button input textarea label card badge alert
```

If the CLI prompts for confirmations, accept defaults. Files land under `src/components/ui/`. Verify with:

```bash
ls src/components/ui/
```

Expected: `alert.tsx`, `badge.tsx`, `button.tsx`, `card.tsx`, `input.tsx`, `label.tsx`, `textarea.tsx`.

- [ ] **Step 7: Smoke-test shadcn components render**

Edit `frontend/src/App.tsx`:

```tsx
import { Button } from "@/components/ui/button";

export default function App() {
  return (
    <main className="p-8 space-y-4">
      <h1 className="text-2xl font-bold">Resume Analyzer (scaffold)</h1>
      <Button>Test button</Button>
    </main>
  );
}
```

Run `npm run dev`, confirm a styled button renders. Stop the server. Leave `App.tsx` like this; Task 13 replaces it.

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "Initialize shadcn/ui with required primitives"
```

---

## Task 5: Vitest + RTL + MSW setup

**Files:**
- Create: `frontend/vitest.config.ts`, `frontend/tests/setup.ts`, `frontend/tests/mocks/handlers.ts`, `frontend/tests/mocks/server.ts`
- Modify: `frontend/package.json`

- [ ] **Step 1: Install test deps**

```bash
cd frontend && npm install -D vitest@^2.1.4 @vitest/ui jsdom@^25.0.1 @testing-library/react@^16.0.1 @testing-library/jest-dom@^6.6.3 @testing-library/user-event@^14.5.2 msw@^2.6.4
```

- [ ] **Step 2: Create `frontend/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
  },
});
```

- [ ] **Step 3: Create `frontend/tests/mocks/handlers.ts`**

```ts
import { http, HttpResponse } from "msw";
import type { AnalysisResponse } from "@/types";

// Default canned response. Individual tests override via server.use(...).
export const defaultAnalysisResponse: AnalysisResponse = {
  mode: "hybrid",
  overall_score: 82.5,
  dimension_scores: [
    { name: "skills", score: 90, weight: 0.35, rationale: "5/5 matched" },
    { name: "experience", score: 75, weight: 0.30, rationale: "avg top-1 sim 0.75" },
    { name: "seniority", score: 80, weight: 0.15, rationale: "8y vs 5y required" },
    { name: "education", score: 100, weight: 0.10, rationale: "Bachelor's >= required" },
    { name: "summary_alignment", score: 65, weight: 0.10, rationale: "summary/JD cosine = 65" },
  ],
  gaps: [],
  suggestions: [],
  warnings: [],
  match_score: 82.5,
  missing_keywords: [],
};

export const handlers = [
  http.post("/api/resume/analyze", () => HttpResponse.json(defaultAnalysisResponse)),
];
```

- [ ] **Step 4: Create `frontend/tests/mocks/server.ts`**

```ts
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
```

- [ ] **Step 5: Create `frontend/tests/setup.ts`**

```ts
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./mocks/server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

Note: `types.ts` (referenced by `handlers.ts`) lands in Task 6. The test setup won't actually run until then. That's fine — we set up the wiring first.

- [ ] **Step 6: Add a sanity placeholder test**

Create `frontend/tests/sanity.test.ts`:

```ts
import { describe, it, expect } from "vitest";

describe("test setup", () => {
  it("runs at all", () => {
    expect(1 + 1).toBe(2);
  });
});
```

- [ ] **Step 7: Run the test (Task 6 not done yet — `handlers.ts` will fail to typecheck but Vitest will still run plain JS-importable tests)**

For now, run only the sanity test:

```bash
cd frontend && npx vitest run tests/sanity.test.ts
```

Expected: 1 test passes. (If MSW's setup throws because `@/types` doesn't exist yet, comment out the line `import type { AnalysisResponse } from "@/types"` and the `defaultAnalysisResponse` typing in `handlers.ts` temporarily — restore it after Task 6.)

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "Add Vitest + RTL + MSW test infrastructure"
```

---

## Task 6: types.ts

**Files:**
- Create: `frontend/src/types.ts`

These types mirror `app/models/resume.py`, `app/models/job.py`, and `app/models/analysis.py`. Dates are represented as `string | null` (ISO `YYYY-MM-DD`) during editing per spec §6.

- [ ] **Step 1: Create `frontend/src/types.ts`**

```ts
// Source of truth: app/models/resume.py, app/models/job.py, app/models/analysis.py
// Update this file whenever those Pydantic models change.

export type Experience = {
  title: string;
  company: string;
  location?: string | null;
  start_date: string | null;  // ISO YYYY-MM-DD; null while editing, enforced non-null by §5 minimum-valid gate
  end_date: string | null;
  descriptions: string[];
};

export type Education = {
  degree: string;
  institution: string;
  graduation_year?: number | null;
  gpa?: number | null;
};

export type Project = {
  name: string;
  tech_stack: string[];
  description: string;
  contributions: string[];
  link?: string | null;
};

export type Resume = {
  country?: string | null;
  summary?: string | null;
  skills: string[];
  experience: Experience[];
  education: Education[];
  projects?: Project[];
};

export type JobDescription = {
  title: string;
  description: string | null;
  required_skills: string[] | null;
};

export type DimensionName =
  | "skills"
  | "experience"
  | "education"
  | "seniority"
  | "summary_alignment";

export type DimensionScore = {
  name: DimensionName;
  score: number;
  weight: number;
  rationale: string;
};

export type Gap = {
  category: DimensionName;
  item: string;
  severity: "high" | "medium" | "low";
};

export type Suggestion = {
  text: string;
  category: "gap" | "rewrite" | "structure" | "keyword";
  priority: "high" | "medium" | "low";
  target_section?: string | null;
};

export type AnalysisResponse = {
  mode: "hybrid" | "keyword-only";
  overall_score: number;
  dimension_scores: DimensionScore[];
  gaps: Gap[];
  suggestions: Suggestion[];
  warnings: string[];
  // Legacy aliases — kept for backwards compatibility; equal to overall_score
  // and skills-only gap items respectively.
  match_score: number;
  missing_keywords: string[];
};
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors. If Task 5's `handlers.ts` import was commented out, restore it now:

```ts
import type { AnalysisResponse } from "@/types";
```

- [ ] **Step 3: Re-run the sanity test**

```bash
cd frontend && npx vitest run tests/sanity.test.ts
```

Expected: passes; no MSW errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "Add types.ts mirroring backend Pydantic models"
```

---

## Task 7: lib/api.ts with 422 error normalization

**Files:**
- Create: `frontend/src/lib/api.ts`, `frontend/tests/lib/api.test.ts`

The hook in Task 8 owns request lifecycle (loading, abort). This module owns request shape and error normalization (turning FastAPI's `{ detail: [{ loc, msg }, ...] }` into a flat `{ "experience[0].descriptions": "msg" }` map).

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/lib/api.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { analyze, flattenLoc, ApiFieldError, ApiServerError } from "@/lib/api";
import type { Resume, JobDescription, AnalysisResponse } from "@/types";

const emptyResume: Resume = {
  country: null,
  summary: null,
  skills: ["Python"],
  experience: [
    { title: "Eng", company: "Co", start_date: "2020-01-01", end_date: null, descriptions: ["did things"] },
  ],
  education: [{ degree: "BS", institution: "Uni" }],
  projects: [],
};

const emptyJd: JobDescription = {
  title: "Engineer",
  description: "Build things.",
  required_skills: ["Python"],
};

describe("flattenLoc", () => {
  it("strips the 'body' and top-level model prefix", () => {
    expect(flattenLoc(["body", "resume", "experience", 0, "descriptions"])).toBe("experience[0].descriptions");
  });

  it("handles nested fields without arrays", () => {
    expect(flattenLoc(["body", "job_description", "title"])).toBe("title");
  });

  it("handles arrays at depth", () => {
    expect(flattenLoc(["body", "resume", "education", 1, "degree"])).toBe("education[1].degree");
  });

  it("returns empty string for the body root", () => {
    expect(flattenLoc(["body"])).toBe("");
  });
});

describe("analyze (happy path)", () => {
  it("POSTs resume + job_description as separate body keys and returns parsed AnalysisResponse", async () => {
    let captured: unknown = null;
    server.use(
      http.post("/api/resume/analyze", async ({ request }) => {
        captured = await request.json();
        return HttpResponse.json({
          mode: "hybrid",
          overall_score: 80,
          dimension_scores: [],
          gaps: [],
          suggestions: [],
          warnings: [],
          match_score: 80,
          missing_keywords: [],
        } satisfies AnalysisResponse);
      }),
    );

    const result = await analyze(emptyResume, emptyJd);
    expect(result.mode).toBe("hybrid");
    expect(captured).toEqual({ resume: emptyResume, job_description: emptyJd });
  });
});

describe("analyze (422 field errors)", () => {
  it("rejects with ApiFieldError mapping dotted paths to messages", async () => {
    server.use(
      http.post("/api/resume/analyze", () => {
        return HttpResponse.json(
          {
            detail: [
              { loc: ["body", "resume", "skills"], msg: "List should have at least 1 item after validation, not 0", type: "too_short" },
              { loc: ["body", "resume", "experience", 0, "descriptions"], msg: "List should have at least 1 item", type: "too_short" },
            ],
          },
          { status: 422 },
        );
      }),
    );

    await expect(analyze(emptyResume, emptyJd)).rejects.toMatchObject({
      name: "ApiFieldError",
      fieldErrors: {
        "skills": "List should have at least 1 item after validation, not 0",
        "experience[0].descriptions": "List should have at least 1 item",
      },
    });
  });
});

describe("analyze (5xx)", () => {
  it("rejects with ApiServerError carrying the detail string", async () => {
    server.use(
      http.post("/api/resume/analyze", () => {
        return HttpResponse.json({ detail: "scorer blew up" }, { status: 500 });
      }),
    );

    await expect(analyze(emptyResume, emptyJd)).rejects.toMatchObject({
      name: "ApiServerError",
      message: expect.stringContaining("scorer blew up"),
    });
  });
});

describe("analyze (abort)", () => {
  it("rejects with DOMException when signal aborts mid-flight", async () => {
    server.use(
      http.post("/api/resume/analyze", async () => {
        await new Promise((r) => setTimeout(r, 100));
        return HttpResponse.json({} as AnalysisResponse);
      }),
    );

    const ctrl = new AbortController();
    const p = analyze(emptyResume, emptyJd, ctrl.signal);
    ctrl.abort();
    await expect(p).rejects.toThrow();
  });

  // ApiFieldError + ApiServerError + ApiNetworkError checked in suite above.
  it("ApiServerError vs ApiFieldError are distinguishable by name", () => {
    expect(new ApiServerError("x").name).toBe("ApiServerError");
    expect(new ApiFieldError({}).name).toBe("ApiFieldError");
  });
});
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
cd frontend && npx vitest run tests/lib/api.test.ts
```

Expected: all fail with "Cannot find module '@/lib/api'" or similar.

- [ ] **Step 3: Implement `frontend/src/lib/api.ts`**

```ts
import type { AnalysisResponse, JobDescription, Resume } from "@/types";

export type FieldErrorMap = Record<string, string>;

export class ApiFieldError extends Error {
  fieldErrors: FieldErrorMap;
  constructor(fieldErrors: FieldErrorMap) {
    super("Validation failed");
    this.name = "ApiFieldError";
    this.fieldErrors = fieldErrors;
  }
}

export class ApiServerError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiServerError";
  }
}

export class ApiNetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiNetworkError";
  }
}

type LocPart = string | number;

/**
 * FastAPI's 422 `detail[i].loc` is shaped like ["body", "<param-name>", ...rest].
 * We drop "body" + the top-level param name and join the rest into a dotted path
 * with `[i]` for numeric indices. E.g.:
 *   ["body", "resume", "experience", 0, "descriptions"] -> "experience[0].descriptions"
 *   ["body", "job_description", "title"] -> "title"
 */
export function flattenLoc(loc: LocPart[]): string {
  const stripped = loc.slice(2); // drop "body" and the top-level param name
  if (stripped.length === 0) return "";
  let out = "";
  for (const part of stripped) {
    if (typeof part === "number") {
      out += `[${part}]`;
    } else {
      if (out.length > 0) out += ".";
      out += part;
    }
  }
  return out;
}

type FastApiDetail =
  | { detail: string }
  | { detail: { loc: LocPart[]; msg: string; type: string }[] };

/**
 * POST /api/resume/analyze with the body shape the router expects:
 *   { resume: Resume, job_description: JobDescription }
 *
 * Throws:
 *  - ApiFieldError on 422 (FastAPI validation)
 *  - ApiFieldError on 500 whose detail looks like a validation list
 *    (the router wraps everything in try/except Exception → 500)
 *  - ApiServerError on other 5xx
 *  - ApiNetworkError on fetch reject
 *  - DOMException on abort (re-thrown unchanged)
 */
export async function analyze(
  resume: Resume,
  jd: JobDescription,
  signal?: AbortSignal,
): Promise<AnalysisResponse> {
  let resp: Response;
  try {
    resp = await fetch("/api/resume/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume, job_description: jd }),
      signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiNetworkError("Couldn't reach the analyzer. Is the backend running?");
  }

  if (resp.ok) {
    return (await resp.json()) as AnalysisResponse;
  }

  // Try to parse the FastAPI error body.
  let body: FastApiDetail | null = null;
  try {
    body = (await resp.json()) as FastApiDetail;
  } catch {
    // fall through to plain status-text error
  }

  if (body && Array.isArray((body as any).detail)) {
    const fieldErrors: FieldErrorMap = {};
    for (const item of (body as { detail: { loc: LocPart[]; msg: string }[] }).detail) {
      const path = flattenLoc(item.loc);
      if (path) fieldErrors[path] = item.msg;
    }
    throw new ApiFieldError(fieldErrors);
  }

  const detailStr =
    body && typeof (body as any).detail === "string"
      ? (body as { detail: string }).detail
      : `HTTP ${resp.status}`;
  throw new ApiServerError(`Analysis failed: ${detailStr}`);
}
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
cd frontend && npx vitest run tests/lib/api.test.ts
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "Add api.ts with analyze() + 422 normalization"
```

---

## Task 8: useAnalyze hook

**Files:**
- Create: `frontend/src/hooks/useAnalyze.ts`, `frontend/tests/hooks/useAnalyze.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/hooks/useAnalyze.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { useAnalyze } from "@/hooks/useAnalyze";
import type { AnalysisResponse, Resume, JobDescription } from "@/types";

const minResume: Resume = {
  country: null,
  summary: null,
  skills: ["Python"],
  experience: [
    { title: "Eng", company: "Co", start_date: "2020-01-01", end_date: null, descriptions: ["did things"] },
  ],
  education: [{ degree: "BS", institution: "Uni" }],
  projects: [],
};
const minJd: JobDescription = {
  title: "Engineer",
  description: "Build things.",
  required_skills: ["Python"],
};

const canned: AnalysisResponse = {
  mode: "hybrid",
  overall_score: 80,
  dimension_scores: [{ name: "skills", score: 80, weight: 1, rationale: "x" }],
  gaps: [],
  suggestions: [],
  warnings: [],
  match_score: 80,
  missing_keywords: [],
};

describe("useAnalyze", () => {
  it("starts idle", () => {
    const { result } = renderHook(() => useAnalyze());
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.fieldErrors).toEqual({});
  });

  it("flips loading and lands data on 200", async () => {
    server.use(http.post("/api/resume/analyze", () => HttpResponse.json(canned)));
    const { result } = renderHook(() => useAnalyze());

    await act(async () => {
      await result.current.analyze(minResume, minJd);
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.data?.overall_score).toBe(80);
    expect(result.current.error).toBeNull();
    expect(result.current.fieldErrors).toEqual({});
  });

  it("populates fieldErrors on 422", async () => {
    server.use(
      http.post("/api/resume/analyze", () =>
        HttpResponse.json(
          { detail: [{ loc: ["body", "resume", "skills"], msg: "too short", type: "too_short" }] },
          { status: 422 },
        ),
      ),
    );
    const { result } = renderHook(() => useAnalyze());

    await act(async () => {
      await result.current.analyze(minResume, minJd);
    });

    expect(result.current.fieldErrors).toEqual({ skills: "too short" });
    expect(result.current.error).toBeNull();
    expect(result.current.data).toBeNull();
  });

  it("populates error on 500", async () => {
    server.use(
      http.post("/api/resume/analyze", () => HttpResponse.json({ detail: "boom" }, { status: 500 })),
    );
    const { result } = renderHook(() => useAnalyze());

    await act(async () => {
      await result.current.analyze(minResume, minJd);
    });

    expect(result.current.error).toMatch(/boom/);
    expect(result.current.fieldErrors).toEqual({});
    expect(result.current.data).toBeNull();
  });

  it("keeps previous data mounted across re-runs (loading=true with stale data)", async () => {
    server.use(http.post("/api/resume/analyze", () => HttpResponse.json(canned)));
    const { result } = renderHook(() => useAnalyze());

    await act(async () => {
      await result.current.analyze(minResume, minJd);
    });
    expect(result.current.data?.overall_score).toBe(80);

    // Second call: make it slow so we can observe the intermediate state.
    server.use(
      http.post("/api/resume/analyze", async () => {
        await new Promise((r) => setTimeout(r, 50));
        return HttpResponse.json({ ...canned, overall_score: 90 });
      }),
    );

    let promise: Promise<void>;
    act(() => {
      promise = result.current.analyze(minResume, minJd);
    });
    await waitFor(() => expect(result.current.loading).toBe(true));
    expect(result.current.data?.overall_score).toBe(80); // stale data still mounted

    await act(async () => {
      await promise!;
    });
    expect(result.current.data?.overall_score).toBe(90);
    expect(result.current.loading).toBe(false);
  });

  it("aborts in-flight request when analyze() is called again before resolution", async () => {
    let resolveFirst: (() => void) | null = null;
    const firstStarted = new Promise<void>((r) => {
      resolveFirst = r;
    });

    server.use(
      http.post("/api/resume/analyze", async ({ request }) => {
        const body = (await request.json()) as { resume: Resume };
        if (body.resume.summary === "first") {
          resolveFirst?.();
          await new Promise((r) => setTimeout(r, 500));
          return HttpResponse.json({ ...canned, overall_score: 11 });
        }
        return HttpResponse.json({ ...canned, overall_score: 22 });
      }),
    );

    const { result } = renderHook(() => useAnalyze());
    act(() => {
      result.current.analyze({ ...minResume, summary: "first" }, minJd);
    });
    await firstStarted;
    await act(async () => {
      await result.current.analyze({ ...minResume, summary: "second" }, minJd);
    });

    // Only the second result lands.
    expect(result.current.data?.overall_score).toBe(22);
  });
});
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
cd frontend && npx vitest run tests/hooks/useAnalyze.test.tsx
```

Expected: all fail (module not found).

- [ ] **Step 3: Implement `frontend/src/hooks/useAnalyze.ts`**

```ts
import { useCallback, useRef, useState } from "react";
import type { AnalysisResponse, Resume, JobDescription } from "@/types";
import { analyze as apiAnalyze, ApiFieldError, ApiServerError, ApiNetworkError, type FieldErrorMap } from "@/lib/api";

export type UseAnalyzeReturn = {
  data: AnalysisResponse | null;
  loading: boolean;
  error: string | null;
  fieldErrors: FieldErrorMap;
  analyze: (resume: Resume, jd: JobDescription) => Promise<void>;
};

export function useAnalyze(): UseAnalyzeReturn {
  const [data, setData] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrorMap>({});
  const inflight = useRef<AbortController | null>(null);

  const analyze = useCallback(async (resume: Resume, jd: JobDescription) => {
    // Abort any in-flight request.
    inflight.current?.abort();
    const ctrl = new AbortController();
    inflight.current = ctrl;

    setLoading(true);
    setError(null);
    setFieldErrors({});

    try {
      const result = await apiAnalyze(resume, jd, ctrl.signal);
      // If we were aborted between fetch resolving and now, drop the result.
      if (ctrl.signal.aborted) return;
      setData(result);
    } catch (e) {
      if (ctrl.signal.aborted) return; // silently swallow aborts
      if (e instanceof ApiFieldError) {
        setFieldErrors(e.fieldErrors);
      } else if (e instanceof ApiServerError || e instanceof ApiNetworkError) {
        setError(e.message);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      if (!ctrl.signal.aborted) setLoading(false);
    }
  }, []);

  return { data, loading, error, fieldErrors, analyze };
}
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
cd frontend && npx vitest run tests/hooks/useAnalyze.test.tsx
```

Expected: all pass. If the abort test is flaky due to timing, increase the `setTimeout` in the slow handler to 1000ms.

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "Add useAnalyze hook with abort + 422/5xx splitting"
```

---

## Task 9: components/Results.tsx

**Files:**
- Create: `frontend/src/components/Results.tsx`, `frontend/tests/components/Results.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/components/Results.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Results } from "@/components/Results";
import type { AnalysisResponse } from "@/types";

function makeResponse(overrides: Partial<AnalysisResponse> = {}): AnalysisResponse {
  return {
    mode: "hybrid",
    overall_score: 82,
    dimension_scores: [
      { name: "skills", score: 90, weight: 0.35, rationale: "5/5 matched" },
      { name: "experience", score: 70, weight: 0.30, rationale: "avg top-1 sim 0.70" },
    ],
    gaps: [{ category: "skills", item: "Kubernetes", severity: "high" }],
    suggestions: [{ text: "Add Kubernetes", category: "gap", priority: "high" }],
    warnings: [],
    match_score: 82,
    missing_keywords: ["Kubernetes"],
    ...overrides,
  };
}

describe("<Results />", () => {
  it("empty state: renders nothing distracting when data is null and not loading", () => {
    render(<Results data={null} loading={false} error={null} />);
    expect(screen.queryByText(/overall/i)).not.toBeInTheDocument();
    expect(screen.getByText(/click analyze/i)).toBeInTheDocument();
  });

  it("loading-first-run state: renders a skeleton hint", () => {
    render(<Results data={null} loading={true} error={null} />);
    expect(screen.getByText(/analyzing/i)).toBeInTheDocument();
  });

  it("populated state: renders overall score and each dimension", () => {
    render(<Results data={makeResponse()} loading={false} error={null} />);
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(screen.getByText(/skills/i)).toBeInTheDocument();
    expect(screen.getByText(/experience/i)).toBeInTheDocument();
    expect(screen.getByText(/5\/5 matched/i)).toBeInTheDocument();
  });

  it("renders gaps grouped by category", () => {
    render(<Results data={makeResponse()} loading={false} error={null} />);
    expect(screen.getByText(/kubernetes/i)).toBeInTheDocument();
  });

  it("renders suggestion text with category and priority badges", () => {
    render(<Results data={makeResponse()} loading={false} error={null} />);
    expect(screen.getByText(/add kubernetes/i)).toBeInTheDocument();
    expect(screen.getAllByText(/high/i).length).toBeGreaterThan(0);
  });

  it("mode='keyword-only' shows the keyword-only badge", () => {
    render(<Results data={makeResponse({ mode: "keyword-only" })} loading={false} error={null} />);
    expect(screen.getByText(/keyword-only/i)).toBeInTheDocument();
  });

  it("mode='hybrid' shows the AI-enhanced badge", () => {
    render(<Results data={makeResponse({ mode: "hybrid" })} loading={false} error={null} />);
    expect(screen.getByText(/ai-enhanced/i)).toBeInTheDocument();
  });

  it("warnings render a yellow alert above panels but data still renders", () => {
    const data = makeResponse({ warnings: ["summary_alignment fell back to keyword-only"] });
    render(<Results data={data} loading={false} error={null} />);
    expect(screen.getByText(/fell back/i)).toBeInTheDocument();
    expect(screen.getByText("82")).toBeInTheDocument();
  });

  it("error prop renders a red alert", () => {
    render(<Results data={null} loading={false} error="Analysis failed: boom" />);
    expect(screen.getByText(/analysis failed: boom/i)).toBeInTheDocument();
  });

  it("re-run: shows refreshing badge when loading=true with previous data", () => {
    render(<Results data={makeResponse()} loading={true} error={null} />);
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(screen.getByText(/refreshing/i)).toBeInTheDocument();
  });

  it("no required_skills + no skills gaps: shows the inline notice on skills dimension", () => {
    const data = makeResponse({ gaps: [] });
    // Use a query for the notice text — implementation reads gaps and shows the notice when skills score is 100 with empty gaps.
    // To trigger reliably: skills score 100 + empty gaps signals "no required skills".
    data.dimension_scores = [{ name: "skills", score: 100, weight: 1, rationale: "JD lists no required skills" }];
    render(<Results data={data} loading={false} error={null} />);
    expect(screen.getByText(/no required skills listed/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
cd frontend && npx vitest run tests/components/Results.test.tsx
```

Expected: all fail (module not found).

- [ ] **Step 3: Implement `frontend/src/components/Results.tsx`**

```tsx
import type { AnalysisResponse, DimensionScore, Gap, Suggestion } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";

type Props = {
  data: AnalysisResponse | null;
  loading: boolean;
  error: string | null;
};

export function Results({ data, loading, error }: Props) {
  if (error && !data) {
    return (
      <Alert variant="destructive" className="mt-4">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (!data && loading) {
    return (
      <div className="mt-4 text-muted-foreground">Analyzing…</div>
    );
  }

  if (!data) {
    return (
      <div className="mt-4 text-muted-foreground italic">
        Click Analyze to see results.
      </div>
    );
  }

  return (
    <div className="mt-6 space-y-4">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {data.warnings.length > 0 && (
        <Alert>
          <AlertDescription>
            <ul className="list-disc pl-5">
              {data.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Overall</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="text-5xl font-bold">{Math.round(data.overall_score)}</div>
            <div className="mt-2 flex items-center gap-2">
              <Badge variant={data.mode === "hybrid" ? "default" : "secondary"}>
                {data.mode === "hybrid" ? "AI-enhanced" : "Keyword-only"}
              </Badge>
              {loading && <span className="text-xs text-muted-foreground">refreshing…</span>}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Dimensions</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {data.dimension_scores.map((d) => (
              <DimensionRow
                key={d.name}
                dim={d}
                showNoSkillsNotice={
                  d.name === "skills" &&
                  d.score === 100 &&
                  data.gaps.every((g) => g.category !== "skills")
                }
              />
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Gaps</CardTitle></CardHeader>
          <CardContent>
            {data.gaps.length === 0 ? (
              <p className="text-sm text-muted-foreground italic">No gaps identified.</p>
            ) : (
              <ul className="space-y-2">
                {data.gaps.map((g, i) => (
                  <GapRow key={i} gap={g} />
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Suggestions</CardTitle></CardHeader>
          <CardContent>
            {data.suggestions.length === 0 ? (
              <p className="text-sm text-muted-foreground italic">No suggestions.</p>
            ) : (
              <ul className="space-y-2">
                {data.suggestions.map((s, i) => (
                  <SuggestionRow key={i} sug={s} />
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function DimensionRow({ dim, showNoSkillsNotice }: { dim: DimensionScore; showNoSkillsNotice: boolean }) {
  const pct = Math.max(0, Math.min(100, dim.score));
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium capitalize">{dim.name.replace("_", " ")}</span>
        <span className="tabular-nums">{Math.round(dim.score)}</span>
      </div>
      <div className="h-2 bg-secondary rounded mt-1">
        <div className="h-2 bg-primary rounded" style={{ width: `${pct}%` }} />
      </div>
      <p className="text-xs text-muted-foreground mt-1">{dim.rationale}</p>
      {showNoSkillsNotice && (
        <p className="text-xs text-amber-700 mt-1">
          No required skills listed in the JD — add some for a meaningful skills score.
        </p>
      )}
    </div>
  );
}

function GapRow({ gap }: { gap: Gap }) {
  return (
    <li className="flex items-start gap-2">
      <Badge variant={gap.severity === "high" ? "destructive" : "secondary"}>{gap.severity}</Badge>
      <div>
        <div className="text-xs uppercase text-muted-foreground">{gap.category.replace("_", " ")}</div>
        <div className="text-sm">{gap.item}</div>
      </div>
    </li>
  );
}

function SuggestionRow({ sug }: { sug: Suggestion }) {
  return (
    <li className="flex items-start gap-2">
      <Badge variant="outline">{sug.category}</Badge>
      <Badge variant={sug.priority === "high" ? "destructive" : "secondary"}>{sug.priority}</Badge>
      <div className="text-sm">{sug.text}</div>
    </li>
  );
}
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
cd frontend && npx vitest run tests/components/Results.test.tsx
```

Expected: all 11 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "Add Results component with mode badge + warnings + no-skills notice"
```

---

## Task 10: components/TagInput.tsx

**Files:**
- Create: `frontend/src/components/TagInput.tsx`, `frontend/tests/components/TagInput.test.tsx`

A small reusable input control used by `<JdForm>` (required_skills) and `<ResumeForm>` (skills). Enter or comma adds the current text as a tag; click-X on a tag removes it.

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/components/TagInput.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TagInput } from "@/components/TagInput";

describe("<TagInput />", () => {
  it("renders existing tags", () => {
    render(<TagInput value={["Python", "AWS"]} onChange={() => {}} label="Skills" />);
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("AWS")).toBeInTheDocument();
  });

  it("adds a tag on Enter", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} label="Skills" />);
    const input = screen.getByLabelText("Skills");
    await user.type(input, "Python{Enter}");
    expect(onChange).toHaveBeenCalledWith(["Python"]);
  });

  it("adds a tag on comma", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} label="Skills" />);
    await user.type(screen.getByLabelText("Skills"), "Python,");
    expect(onChange).toHaveBeenCalledWith(["Python"]);
  });

  it("trims whitespace and ignores empty additions", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} label="Skills" />);
    await user.type(screen.getByLabelText("Skills"), "  {Enter}");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("does not add duplicates (case-insensitive)", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TagInput value={["Python"]} onChange={onChange} label="Skills" />);
    await user.type(screen.getByLabelText("Skills"), "python{Enter}");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("removes a tag when its remove button is clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TagInput value={["Python", "AWS"]} onChange={onChange} label="Skills" />);
    await user.click(screen.getByRole("button", { name: /remove python/i }));
    expect(onChange).toHaveBeenCalledWith(["AWS"]);
  });

  it("renders the error message when error prop is set", () => {
    render(<TagInput value={[]} onChange={() => {}} label="Skills" error="At least 1 required" />);
    expect(screen.getByText(/at least 1 required/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
cd frontend && npx vitest run tests/components/TagInput.test.tsx
```

Expected: all fail (module not found).

- [ ] **Step 3: Implement `frontend/src/components/TagInput.tsx`**

```tsx
import { useId, useState, type KeyboardEvent, type ChangeEvent } from "react";
import { X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

type Props = {
  value: string[];
  onChange: (next: string[]) => void;
  label: string;
  placeholder?: string;
  error?: string;
};

export function TagInput({ value, onChange, label, placeholder, error }: Props) {
  const id = useId();
  const [draft, setDraft] = useState("");

  const commit = (raw: string) => {
    const t = raw.trim();
    if (!t) return;
    if (value.some((v) => v.toLowerCase() === t.toLowerCase())) return;
    onChange([...value, t]);
    setDraft("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      commit(draft);
    } else if (e.key === "Backspace" && draft === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  };

  const onChangeInput = (e: ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value;
    if (v.endsWith(",")) {
      commit(v.slice(0, -1));
    } else {
      setDraft(v);
    }
  };

  const remove = (tag: string) => onChange(value.filter((v) => v !== tag));

  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <div className="flex flex-wrap gap-1 mb-1">
        {value.map((tag) => (
          <Badge key={tag} variant="secondary" className="flex items-center gap-1">
            {tag}
            <button
              type="button"
              aria-label={`Remove ${tag}`}
              onClick={() => remove(tag)}
              className="ml-1 inline-flex"
            >
              <X className="h-3 w-3" />
            </button>
          </Badge>
        ))}
      </div>
      <Input
        id={id}
        value={draft}
        onChange={onChangeInput}
        onKeyDown={onKeyDown}
        placeholder={placeholder ?? "Type and press Enter or comma"}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
cd frontend && npx vitest run tests/components/TagInput.test.tsx
```

Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "Add TagInput component (Enter/comma to add, X to remove)"
```

---

## Task 11: components/JdForm.tsx

**Files:**
- Create: `frontend/src/components/JdForm.tsx`, `frontend/tests/components/JdForm.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/components/JdForm.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { JdForm } from "@/components/JdForm";
import type { JobDescription } from "@/types";

const empty: JobDescription = { title: "", description: "", required_skills: [] };

describe("<JdForm />", () => {
  it("renders title, description, and required-skills inputs", () => {
    render(<JdForm value={empty} onChange={() => {}} />);
    expect(screen.getByLabelText(/job title/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/required skills/i)).toBeInTheDocument();
  });

  it("updates title via onChange", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<JdForm value={empty} onChange={onChange} />);
    await user.type(screen.getByLabelText(/job title/i), "X");
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ title: "X" }));
  });

  it("updates description via onChange", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<JdForm value={empty} onChange={onChange} />);
    await user.type(screen.getByLabelText(/description/i), "Y");
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ description: "Y" }));
  });

  it("adds a required skill via the tag input", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<JdForm value={empty} onChange={onChange} />);
    await user.type(screen.getByLabelText(/required skills/i), "Python{Enter}");
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ required_skills: ["Python"] }));
  });

  it("renders inline field error for title", () => {
    render(<JdForm value={empty} onChange={() => {}} fieldErrors={{ title: "Required" }} />);
    expect(screen.getByText(/^required$/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
cd frontend && npx vitest run tests/components/JdForm.test.tsx
```

- [ ] **Step 3: Implement `frontend/src/components/JdForm.tsx`**

```tsx
import type { JobDescription } from "@/types";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { TagInput } from "@/components/TagInput";

type Props = {
  value: JobDescription;
  onChange: (next: JobDescription) => void;
  fieldErrors?: Record<string, string>;
};

export function JdForm({ value, onChange, fieldErrors = {} }: Props) {
  const set = <K extends keyof JobDescription>(k: K, v: JobDescription[K]) =>
    onChange({ ...value, [k]: v });

  return (
    <section className="space-y-3" aria-label="Job description">
      <h2 className="text-lg font-semibold">Job description</h2>

      <div className="space-y-1">
        <Label htmlFor="jd-title">Job title</Label>
        <Input
          id="jd-title"
          value={value.title}
          onChange={(e) => set("title", e.target.value)}
        />
        {fieldErrors.title && <p className="text-xs text-destructive">{fieldErrors.title}</p>}
      </div>

      <div className="space-y-1">
        <Label htmlFor="jd-description">Description</Label>
        <Textarea
          id="jd-description"
          rows={10}
          value={value.description ?? ""}
          onChange={(e) => set("description", e.target.value)}
        />
        {fieldErrors.description && <p className="text-xs text-destructive">{fieldErrors.description}</p>}
      </div>

      <TagInput
        value={value.required_skills ?? []}
        onChange={(next) => set("required_skills", next)}
        label="Required skills"
        placeholder="e.g. Python, AWS, Docker"
        error={fieldErrors.required_skills}
      />
    </section>
  );
}
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
cd frontend && npx vitest run tests/components/JdForm.test.tsx
```

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "Add JdForm (title + description + required-skills tags)"
```

---

## Task 12: components/ResumeForm.tsx

**Files:**
- Create: `frontend/src/components/ResumeForm.tsx`, `frontend/tests/components/ResumeForm.test.tsx`

Largest component. Renders country, summary, skills (TagInput), and three dynamic arrays (experience, education, projects) with add/delete.

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/components/ResumeForm.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResumeForm } from "@/components/ResumeForm";
import type { Resume } from "@/types";

const seed: Resume = {
  country: null,
  summary: null,
  skills: [],
  experience: [
    { title: "", company: "", start_date: null, end_date: null, descriptions: [""] },
  ],
  education: [],
  projects: [],
};

describe("<ResumeForm />", () => {
  it("does NOT render name, email, phone inputs (PII removed)", () => {
    render(<ResumeForm value={seed} onChange={() => {}} />);
    expect(screen.queryByLabelText(/name/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/phone/i)).not.toBeInTheDocument();
  });

  it("renders the PII notice", () => {
    render(<ResumeForm value={seed} onChange={() => {}} />);
    expect(screen.getByText(/don.t collect your name, email/i)).toBeInTheDocument();
  });

  it("renders country, summary, skills, and one experience row by default", () => {
    render(<ResumeForm value={seed} onChange={() => {}} />);
    expect(screen.getByLabelText(/country/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/summary/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/skills/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/job title/i)).toBeInTheDocument();
  });

  it("updates country", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ResumeForm value={seed} onChange={onChange} />);
    await user.type(screen.getByLabelText(/country/i), "Canada");
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ country: "Canada" }));
  });

  it("adds an experience row via + Add another", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ResumeForm value={seed} onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /add another experience/i }));
    const lastCall = onChange.mock.lastCall![0] as Resume;
    expect(lastCall.experience.length).toBe(2);
  });

  it("removes an experience row via delete button", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const twoExp: Resume = {
      ...seed,
      experience: [
        { title: "A", company: "X", start_date: "2020-01-01", end_date: null, descriptions: ["d"] },
        { title: "B", company: "Y", start_date: "2021-01-01", end_date: null, descriptions: ["d"] },
      ],
    };
    render(<ResumeForm value={twoExp} onChange={onChange} />);
    const removes = screen.getAllByRole("button", { name: /remove experience/i });
    await user.click(removes[0]);
    const lastCall = onChange.mock.lastCall![0] as Resume;
    expect(lastCall.experience.length).toBe(1);
    expect(lastCall.experience[0].title).toBe("B");
  });

  it("adds an education row", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ResumeForm value={seed} onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /add another education/i }));
    const lastCall = onChange.mock.lastCall![0] as Resume;
    expect(lastCall.education.length).toBe(1);
  });

  it("renders fieldErrors at the matching dotted path", () => {
    render(
      <ResumeForm
        value={seed}
        onChange={() => {}}
        fieldErrors={{ "experience[0].title": "Required field" }}
      />,
    );
    expect(screen.getByText(/required field/i)).toBeInTheDocument();
  });

  it("adds a description bullet within an experience", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ResumeForm value={seed} onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /add bullet/i }));
    const lastCall = onChange.mock.lastCall![0] as Resume;
    expect(lastCall.experience[0].descriptions.length).toBe(2);
  });
});
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
cd frontend && npx vitest run tests/components/ResumeForm.test.tsx
```

- [ ] **Step 3: Implement `frontend/src/components/ResumeForm.tsx`**

```tsx
import type { Education, Experience, Project, Resume } from "@/types";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TagInput } from "@/components/TagInput";

type Props = {
  value: Resume;
  onChange: (next: Resume) => void;
  fieldErrors?: Record<string, string>;
};

const blankExperience = (): Experience => ({
  title: "",
  company: "",
  start_date: null,
  end_date: null,
  descriptions: [""],
});

const blankEducation = (): Education => ({ degree: "", institution: "" });

const blankProject = (): Project => ({
  name: "",
  tech_stack: [],
  description: "",
  contributions: [""],
});

export function ResumeForm({ value, onChange, fieldErrors = {} }: Props) {
  const set = <K extends keyof Resume>(k: K, v: Resume[K]) =>
    onChange({ ...value, [k]: v });

  const updateExperience = (i: number, patch: Partial<Experience>) => {
    const next = value.experience.map((e, idx) => (idx === i ? { ...e, ...patch } : e));
    set("experience", next);
  };
  const addExperience = () => set("experience", [...value.experience, blankExperience()]);
  const removeExperience = (i: number) =>
    set("experience", value.experience.filter((_, idx) => idx !== i));

  const updateEducation = (i: number, patch: Partial<Education>) => {
    const next = value.education.map((e, idx) => (idx === i ? { ...e, ...patch } : e));
    set("education", next);
  };
  const addEducation = () => set("education", [...value.education, blankEducation()]);
  const removeEducation = (i: number) =>
    set("education", value.education.filter((_, idx) => idx !== i));

  const projects = value.projects ?? [];
  const updateProject = (i: number, patch: Partial<Project>) => {
    const next = projects.map((p, idx) => (idx === i ? { ...p, ...patch } : p));
    set("projects", next);
  };
  const addProject = () => set("projects", [...projects, blankProject()]);
  const removeProject = (i: number) =>
    set("projects", projects.filter((_, idx) => idx !== i));

  return (
    <section className="space-y-4" aria-label="Resume">
      <h2 className="text-lg font-semibold">Resume</h2>
      <p className="text-xs text-muted-foreground italic">
        We don't collect your name, email, or phone — only the parts the analyzer actually uses.
      </p>

      <div className="space-y-1">
        <Label htmlFor="country">Country (optional)</Label>
        <Input
          id="country"
          value={value.country ?? ""}
          onChange={(e) => set("country", e.target.value || null)}
        />
      </div>

      <div className="space-y-1">
        <Label htmlFor="summary">Summary</Label>
        <Textarea
          id="summary"
          rows={4}
          value={value.summary ?? ""}
          onChange={(e) => set("summary", e.target.value || null)}
        />
      </div>

      <TagInput
        value={value.skills}
        onChange={(next) => set("skills", next)}
        label="Skills"
        placeholder="e.g. Python, FastAPI, AWS"
        error={fieldErrors.skills}
      />

      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Experience</h3>
        {value.experience.map((exp, i) => (
          <Card key={i}>
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-sm">Experience #{i + 1}</CardTitle>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={`Remove experience ${i + 1}`}
                onClick={() => removeExperience(i)}
              >
                ×
              </Button>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label htmlFor={`exp-${i}-title`}>Job title</Label>
                  <Input
                    id={`exp-${i}-title`}
                    value={exp.title}
                    onChange={(e) => updateExperience(i, { title: e.target.value })}
                  />
                  {fieldErrors[`experience[${i}].title`] && (
                    <p className="text-xs text-destructive">{fieldErrors[`experience[${i}].title`]}</p>
                  )}
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`exp-${i}-company`}>Company</Label>
                  <Input
                    id={`exp-${i}-company`}
                    value={exp.company}
                    onChange={(e) => updateExperience(i, { company: e.target.value })}
                  />
                  {fieldErrors[`experience[${i}].company`] && (
                    <p className="text-xs text-destructive">{fieldErrors[`experience[${i}].company`]}</p>
                  )}
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`exp-${i}-start`}>Start date</Label>
                  <Input
                    id={`exp-${i}-start`}
                    type="date"
                    value={exp.start_date ?? ""}
                    onChange={(e) => updateExperience(i, { start_date: e.target.value || null })}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`exp-${i}-end`}>End date (blank = current)</Label>
                  <Input
                    id={`exp-${i}-end`}
                    type="date"
                    value={exp.end_date ?? ""}
                    onChange={(e) => updateExperience(i, { end_date: e.target.value || null })}
                  />
                </div>
              </div>
              <div className="space-y-1">
                <Label>Bullets</Label>
                {exp.descriptions.map((d, j) => (
                  <div key={j} className="flex gap-2">
                    <Input
                      value={d}
                      onChange={(e) => {
                        const next = exp.descriptions.map((x, idx) => (idx === j ? e.target.value : x));
                        updateExperience(i, { descriptions: next });
                      }}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      aria-label={`Remove bullet ${j + 1} from experience ${i + 1}`}
                      onClick={() => {
                        const next = exp.descriptions.filter((_, idx) => idx !== j);
                        updateExperience(i, { descriptions: next.length ? next : [""] });
                      }}
                    >
                      ×
                    </Button>
                  </div>
                ))}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    updateExperience(i, { descriptions: [...exp.descriptions, ""] })
                  }
                >
                  + Add bullet
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
        <Button type="button" variant="outline" size="sm" onClick={addExperience}>
          + Add another experience
        </Button>
      </div>

      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Education</h3>
        {value.education.map((ed, i) => (
          <Card key={i}>
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-sm">Education #{i + 1}</CardTitle>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={`Remove education ${i + 1}`}
                onClick={() => removeEducation(i)}
              >
                ×
              </Button>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label htmlFor={`ed-${i}-degree`}>Degree</Label>
                <Input
                  id={`ed-${i}-degree`}
                  value={ed.degree}
                  onChange={(e) => updateEducation(i, { degree: e.target.value })}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor={`ed-${i}-institution`}>Institution</Label>
                <Input
                  id={`ed-${i}-institution`}
                  value={ed.institution}
                  onChange={(e) => updateEducation(i, { institution: e.target.value })}
                />
              </div>
            </CardContent>
          </Card>
        ))}
        <Button type="button" variant="outline" size="sm" onClick={addEducation}>
          + Add another education
        </Button>
      </div>

      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Projects (optional)</h3>
        {projects.map((p, i) => (
          <Card key={i}>
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-sm">Project #{i + 1}</CardTitle>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={`Remove project ${i + 1}`}
                onClick={() => removeProject(i)}
              >
                ×
              </Button>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="space-y-1">
                <Label htmlFor={`p-${i}-name`}>Name</Label>
                <Input
                  id={`p-${i}-name`}
                  value={p.name}
                  onChange={(e) => updateProject(i, { name: e.target.value })}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor={`p-${i}-description`}>Description</Label>
                <Textarea
                  id={`p-${i}-description`}
                  rows={2}
                  value={p.description}
                  onChange={(e) => updateProject(i, { description: e.target.value })}
                />
              </div>
              <TagInput
                value={p.tech_stack}
                onChange={(next) => updateProject(i, { tech_stack: next })}
                label={`Tech stack #${i + 1}`}
              />
              <div className="space-y-1">
                <Label>Contributions</Label>
                {p.contributions.map((c, j) => (
                  <Input
                    key={j}
                    value={c}
                    onChange={(e) => {
                      const next = p.contributions.map((x, idx) => (idx === j ? e.target.value : x));
                      updateProject(i, { contributions: next });
                    }}
                  />
                ))}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => updateProject(i, { contributions: [...p.contributions, ""] })}
                >
                  + Add contribution
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
        <Button type="button" variant="outline" size="sm" onClick={addProject}>
          + Add another project
        </Button>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
cd frontend && npx vitest run tests/components/ResumeForm.test.tsx
```

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "Add ResumeForm with country + dynamic experience/education/projects"
```

---

## Task 13: App.tsx — layout shell + state + minimum-valid gate

**Files:**
- Modify: `frontend/src/App.tsx`

This is the wiring step. No new tests here — the integration smoke test in Task 14 covers behavior end-to-end.

- [ ] **Step 1: Replace `frontend/src/App.tsx`**

```tsx
import { useMemo, useState } from "react";
import type { Resume, JobDescription } from "@/types";
import { ResumeForm } from "@/components/ResumeForm";
import { JdForm } from "@/components/JdForm";
import { Results } from "@/components/Results";
import { Button } from "@/components/ui/button";
import { useAnalyze } from "@/hooks/useAnalyze";

const initialResume: Resume = {
  country: null,
  summary: null,
  skills: [],
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

function isMinimumValid(resume: Resume, jd: JobDescription): boolean {
  if (resume.skills.length === 0) return false;
  for (const exp of resume.experience) {
    if (!exp.title || !exp.company) return false;
    if (!exp.start_date) return false;
    if (exp.descriptions.length === 0) return false;
    if (exp.descriptions.some((d) => !d.trim())) return false;
  }
  for (const ed of resume.education) {
    if (!ed.degree || !ed.institution) return false;
  }
  if (!jd.title) return false;
  // jd.description and jd.required_skills are Optional but required keys;
  // initial state provides empty string and empty list, both acceptable.
  return true;
}

export default function App() {
  const [resume, setResume] = useState<Resume>(initialResume);
  const [jd, setJd] = useState<JobDescription>(initialJd);
  const { data, loading, error, fieldErrors, analyze } = useAnalyze();

  const canSubmit = useMemo(() => isMinimumValid(resume, jd), [resume, jd]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="container py-4">
          <h1 className="text-2xl font-bold">AI Resume Analyzer</h1>
        </div>
      </header>

      <main className="container py-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <ResumeForm value={resume} onChange={setResume} fieldErrors={fieldErrors} />
          <JdForm value={jd} onChange={setJd} fieldErrors={fieldErrors} />
        </div>

        <div className="flex flex-col items-center my-6 gap-2">
          <Button
            size="lg"
            disabled={!canSubmit || loading}
            onClick={() => void analyze(resume, jd)}
          >
            {loading ? "Analyzing…" : "Analyze ↓"}
          </Button>
          {!canSubmit && (
            <p className="text-xs text-muted-foreground">Required fields missing</p>
          )}
        </div>

        <Results data={data} loading={loading} error={error} />
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Smoke-test in browser**

In one terminal: `cd app && uvicorn main:app --reload`
In another: `cd frontend && npm run dev`
Open http://localhost:5173, confirm the two-column layout renders with the Analyze button below. Fill in minimal data, click Analyze, confirm results appear. Stop both servers.

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "Wire App.tsx layout shell + minimum-valid gate"
```

---

## Task 14: App integration smoke test

**Files:**
- Create: `frontend/tests/App.test.tsx`

One end-to-end test that drives the actual `<App>`, fills in a minimum-valid resume + JD via user interactions, clicks Analyze, lets MSW respond, and asserts the score appears.

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/App.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import App from "@/App";

describe("App (integration smoke)", () => {
  it("fills minimum-valid form, clicks Analyze, and renders the overall score", async () => {
    server.use(
      http.post("/api/resume/analyze", () =>
        HttpResponse.json({
          mode: "hybrid",
          overall_score: 77,
          dimension_scores: [
            { name: "skills", score: 100, weight: 0.5, rationale: "1/1 matched" },
            { name: "experience", score: 50, weight: 0.5, rationale: "x" },
          ],
          gaps: [],
          suggestions: [],
          warnings: [],
          match_score: 77,
          missing_keywords: [],
        }),
      ),
    );

    const user = userEvent.setup();
    render(<App />);

    // Skills tag input
    await user.type(screen.getByLabelText(/^skills$/i), "Python{Enter}");

    // Experience #1 fields
    await user.type(screen.getByLabelText(/job title/i, { selector: "input" }), "Engineer");
    await user.type(screen.getByLabelText(/company/i), "Acme");
    // Native date input — fireEvent-style typing via userEvent.type works for YYYY-MM-DD
    const startDate = screen.getByLabelText(/start date/i);
    await user.type(startDate, "2020-01-01");
    // Fill the pre-rendered bullet
    const bulletInputs = screen.getAllByRole("textbox").filter(
      (el) => (el as HTMLInputElement).id === "" || !(el as HTMLInputElement).id.startsWith("exp-"),
    );
    // Easier: directly target the only empty bullet input below the Bullets label.
    const bulletGroup = screen.getByText(/^bullets$/i).parentElement!;
    const bullet = bulletGroup.querySelector("input") as HTMLInputElement;
    await user.type(bullet, "Built things");

    // JD title (search by accessible name, scoped to the JD section)
    const jdTitle = screen.getAllByLabelText(/job title/i).find(
      (el) => (el as HTMLInputElement).id === "jd-title",
    ) as HTMLInputElement;
    await user.type(jdTitle, "Engineer");

    // Click Analyze
    const analyzeBtn = screen.getByRole("button", { name: /analyze/i });
    await waitFor(() => expect(analyzeBtn).toBeEnabled());
    await user.click(analyzeBtn);

    // Score 77 appears
    await waitFor(() => expect(screen.getByText("77")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run the test, verify it passes**

```bash
cd frontend && npx vitest run tests/App.test.tsx
```

Expected: PASS. If the bullet field selector flakes due to ambiguous queries, simplify by replacing the lookup with `container.querySelector("section[aria-label='Resume'] input[type='text']:not([id])")` after destructuring `{ container }` from `render(<App />)`.

- [ ] **Step 3: Run the entire frontend suite**

```bash
cd frontend && npx vitest run
```

Expected: all suites pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "Add App integration smoke test"
```

---

## Task 15: Update CLAUDE.md with frontend section

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add a "Frontend" section to `CLAUDE.md`**

Append the following section to `CLAUDE.md`, **before** the "Known rough edges" section (so it sits with the architecture docs):

```markdown
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

`Resume` no longer accepts `name`, `email`, `phone`, or arbitrary `location`. The model has `ConfigDict(extra='forbid')` so any client trying to send those fields gets a 422. The frontend never renders inputs for them. If you re-add them, update `docs/superpowers/specs/2026-05-24-stateless-web-ui-design.md` §3.1 first.

### Tests + drift safety

- `frontend/tests/App.test.tsx` integration smoke test uses a real-shape `AnalysisResponse` in MSW. Any backend response-shape change should surface as a TypeScript error in this file or in `types.ts` consumers.
- Top of `frontend/src/types.ts` points at the backend models as source of truth.
```

- [ ] **Step 2: Verify the CLAUDE.md still reads well**

Read the full file. The new section should sit between the existing "Settings (`app/core/config.py`)" / "Test fixtures" area and the "Known rough edges" section.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "Document frontend in CLAUDE.md"
```

---

## Self-review checklist (run after writing the plan)

**Spec coverage:** every section in `docs/superpowers/specs/2026-05-24-stateless-web-ui-design.md` is covered:
- §1 Goal + non-goals — out-of-scope items not in the plan; in-scope items all have tasks.
- §2 Decisions D1–D10 — D1 (Vite/React/TS) → Task 2; D2 (Tailwind/shadcn) → Tasks 3-4; D3 (`frontend/` layout) → Task 2; D4 (proxy) → Task 2; D5 (structured form) → Task 12; D6 (paste-text JD + tag input) → Task 11; D7 (layout) → Task 13; D8 (component structure) → Tasks 9-13; D9 (hand-mirrored types) → Task 6 + Task 14; D10 (Vitest/RTL/MSW) → Task 5.
- §2 Decision D11 (PII removal) → Task 1.
- §3 Repo layout — matches Tasks 2-12.
- §3.1 Backend schema changes — Task 1.
- §4 Component contracts — `<ResumeForm>` Task 12, `<JdForm>` Task 11, `<Results>` Task 9, `useAnalyze` Task 8, `App.tsx` Task 13.
- §5 Data flow + error matrix — Task 7 (api.ts) + Task 8 (hook) + Task 9 (Results renders error/warnings/mode badge) + Task 13 (gate + button disable).
- §5 minimum-valid gate — Task 13 `isMinimumValid`.
- §5 "no required_skills" notice — Task 9 `DimensionRow` `showNoSkillsNotice`.
- §6 Initial form state — Task 13.
- §7 Tests — covered task-by-task; integration smoke test = Task 14.
- §8 Dev workflow — documented in Task 15 (CLAUDE.md).
- §9 Deferred items — TagInput vs RHF, shadcn theme, etc. — correctly NOT in plan.

**Placeholder scan:** no "TBD", "TODO", or "similar to Task N" patterns. Every code step has full code.

**Type consistency:**
- `analyze()` signature: `(Resume, JobDescription, AbortSignal?) => Promise<AnalysisResponse>` — same in Task 7 (definition), Task 8 (call site), Task 14 (smoke).
- `ApiFieldError.fieldErrors` shape `Record<string, string>` — same in Task 7, Task 8.
- `useAnalyze` return shape — defined in Task 8, consumed in Task 13.
- `Resume` / `JobDescription` shapes — defined in Task 6, used everywhere downstream.
- `flattenLoc` — defined and tested in Task 7; spec §5 mentions stripping `"body"` and top-level model prefix, matching the implementation.

No issues found. Plan is ready.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-24-stateless-web-ui.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

