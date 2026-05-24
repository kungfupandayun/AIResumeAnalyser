// Source of truth: app/models/resume.py, app/models/job.py, app/models/analysis.py
// Update this file whenever those Pydantic models change.

export type Experience = {
  title: string;
  company: string;
  location?: string | null;
  start_date: string | null; // ISO YYYY-MM-DD; null while editing, enforced non-null by §5 minimum-valid gate
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
