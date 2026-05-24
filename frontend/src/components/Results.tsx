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
