# AI Resume Analyser

A FastAPI service that evaluates resumes against job descriptions using keyword matching and AI-powered semantic analysis.

## Features

- Upload a resume as a PDF or raw text
- Extract and parse resume content into structured JSON
- Compare resume against a job description
- Returns:
  - **Match score** — percentage match (0–100)
  - **Missing keywords** — skills/terms in the job description not found in the resume
  - **Improvement suggestions** — AI-generated recommendations

## Tech Stack

- **FastAPI** — REST API framework
- **spaCy** — NLP pipeline for keyword extraction
- **scikit-learn** — TF-IDF weighted matching
- **OpenAI API** — semantic analysis and suggestions (falls back to keyword-only if unavailable)
- **pypdf / pdfplumber / PyMuPDF** — PDF text extraction

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `POST` | `/api/resume/analyze` | Analyze resume against job description |
| `POST` | `/api/resume/parse` | Parse resume text into structured JSON |
| `POST` | `/api/resume/upload-resume` | Upload a PDF resume and parse it |

Interactive API docs available at `/docs` when the server is running.

## Getting Started

### Prerequisites

- Python 3.9+
- An OpenAI API key (optional — falls back to keyword-only mode)

### Installation

```bash
# Clone the repository
git clone https://github.com/kungfupandayun/AIResumeAnalyser.git
cd AIResumeAnalyser

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy language model
python -m spacy download en_core_web_sm
```

### Configuration

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

### Running the Server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

### Running Tests

```bash
pytest
```
