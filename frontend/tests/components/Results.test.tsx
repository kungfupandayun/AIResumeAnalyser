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
    expect(screen.getAllByText(/skills/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/experience/i)).toBeInTheDocument();
    expect(screen.getByText(/5\/5 matched/i)).toBeInTheDocument();
  });

  it("renders gaps grouped by category", () => {
    render(<Results data={makeResponse()} loading={false} error={null} />);
    expect(screen.getAllByText(/kubernetes/i).length).toBeGreaterThan(0);
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

  it("no required_skills in JD: shows the inline notice on skills dimension", () => {
    // The notice fires on the backend's specific rationale, NOT on a
    // score===100 + no-gaps proxy (which false-positive'd a perfect match
    // against a real required-skills list — caught via Playwright).
    const data = makeResponse({ gaps: [] });
    data.dimension_scores = [{ name: "skills", score: 100, weight: 1, rationale: "JD lists no required skills" }];
    render(<Results data={data} loading={false} error={null} />);
    expect(screen.getByText(/no required skills listed/i)).toBeInTheDocument();
  });

  it("perfect skills match WITH required_skills: does NOT show the no-skills notice", () => {
    // Regression test: previously the predicate was `score===100 && no-skills-gaps`
    // which incorrectly fired here too. Now it keys off the rationale string.
    const data = makeResponse({ gaps: [] });
    data.dimension_scores = [{ name: "skills", score: 100, weight: 1, rationale: "1/1 required skills matched" }];
    render(<Results data={data} loading={false} error={null} />);
    expect(screen.queryByText(/no required skills listed/i)).not.toBeInTheDocument();
  });
});
