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
    <section className="space-y-3" aria-label="Job details">
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
