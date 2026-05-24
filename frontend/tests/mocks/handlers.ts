import { http, HttpResponse } from "msw";
// import type { AnalysisResponse } from "@/types";  // Uncommented in Task 6

// Default canned response. Individual tests override via server.use(...).
// Type assertion to AnalysisResponse is restored in Task 6.
export const defaultAnalysisResponse = {
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
