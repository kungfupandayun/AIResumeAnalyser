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
