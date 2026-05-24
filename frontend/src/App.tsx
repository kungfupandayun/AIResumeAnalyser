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
