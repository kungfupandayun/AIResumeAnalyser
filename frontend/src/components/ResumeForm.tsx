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
