from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from routers.resume_router import router as resume_router

app = FastAPI(
    title="AI Resume Analyzer API",
    description="API for analyzing resumes against job descriptions using keyword matching and AI.",
    version="1.0.0"
)

# Configure CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins, adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume_router)

@app.get("/", tags=["Health"])
async def root():
    return {"message": "Welcome to the AI Resume Analyzer API. Visit /docs for documentation."}
