import { describe, it, expect } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { useAnalyze } from "@/hooks/useAnalyze";
import type { AnalysisResponse, Resume, JobDescription } from "@/types";

const minResume: Resume = {
  country: null,
  summary: null,
  skills: ["Python"],
  experience: [
    { title: "Eng", company: "Co", start_date: "2020-01-01", end_date: null, descriptions: ["did things"] },
  ],
  education: [{ degree: "BS", institution: "Uni" }],
  projects: [],
};
const minJd: JobDescription = {
  title: "Engineer",
  description: "Build things.",
  required_skills: ["Python"],
};

const canned: AnalysisResponse = {
  mode: "hybrid",
  overall_score: 80,
  dimension_scores: [{ name: "skills", score: 80, weight: 1, rationale: "x" }],
  gaps: [],
  suggestions: [],
  warnings: [],
  match_score: 80,
  missing_keywords: [],
};

describe("useAnalyze", () => {
  it("starts idle", () => {
    const { result } = renderHook(() => useAnalyze());
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.fieldErrors).toEqual({});
  });

  it("flips loading and lands data on 200", async () => {
    server.use(http.post("/api/resume/analyze", () => HttpResponse.json(canned)));
    const { result } = renderHook(() => useAnalyze());

    await act(async () => {
      await result.current.analyze(minResume, minJd);
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.data?.overall_score).toBe(80);
    expect(result.current.error).toBeNull();
    expect(result.current.fieldErrors).toEqual({});
  });

  it("populates fieldErrors on 422", async () => {
    server.use(
      http.post("/api/resume/analyze", () =>
        HttpResponse.json(
          { detail: [{ loc: ["body", "resume", "skills"], msg: "too short", type: "too_short" }] },
          { status: 422 },
        ),
      ),
    );
    const { result } = renderHook(() => useAnalyze());

    await act(async () => {
      await result.current.analyze(minResume, minJd);
    });

    expect(result.current.fieldErrors).toEqual({ skills: "too short" });
    expect(result.current.error).toBeNull();
    expect(result.current.data).toBeNull();
  });

  it("populates error on 500", async () => {
    server.use(
      http.post("/api/resume/analyze", () => HttpResponse.json({ detail: "boom" }, { status: 500 })),
    );
    const { result } = renderHook(() => useAnalyze());

    await act(async () => {
      await result.current.analyze(minResume, minJd);
    });

    expect(result.current.error).toMatch(/boom/);
    expect(result.current.fieldErrors).toEqual({});
    expect(result.current.data).toBeNull();
  });

  it("keeps previous data mounted across re-runs (loading=true with stale data)", async () => {
    server.use(http.post("/api/resume/analyze", () => HttpResponse.json(canned)));
    const { result } = renderHook(() => useAnalyze());

    await act(async () => {
      await result.current.analyze(minResume, minJd);
    });
    expect(result.current.data?.overall_score).toBe(80);

    // Second call: make it slow so we can observe the intermediate state.
    server.use(
      http.post("/api/resume/analyze", async () => {
        await new Promise((r) => setTimeout(r, 50));
        return HttpResponse.json({ ...canned, overall_score: 90 });
      }),
    );

    let promise: Promise<void>;
    act(() => {
      promise = result.current.analyze(minResume, minJd);
    });
    await waitFor(() => expect(result.current.loading).toBe(true));
    expect(result.current.data?.overall_score).toBe(80); // stale data still mounted

    await act(async () => {
      await promise!;
    });
    expect(result.current.data?.overall_score).toBe(90);
    expect(result.current.loading).toBe(false);
  });

  it("aborts in-flight request when analyze() is called again before resolution", async () => {
    let resolveFirst: (() => void) | null = null;
    const firstStarted = new Promise<void>((r) => {
      resolveFirst = r;
    });

    server.use(
      http.post("/api/resume/analyze", async ({ request }) => {
        const body = (await request.json()) as { resume: Resume };
        if (body.resume.summary === "first") {
          resolveFirst?.();
          await new Promise((r) => setTimeout(r, 500));
          return HttpResponse.json({ ...canned, overall_score: 11 });
        }
        return HttpResponse.json({ ...canned, overall_score: 22 });
      }),
    );

    const { result } = renderHook(() => useAnalyze());
    act(() => {
      result.current.analyze({ ...minResume, summary: "first" }, minJd);
    });
    await firstStarted;
    await act(async () => {
      await result.current.analyze({ ...minResume, summary: "second" }, minJd);
    });

    // Only the second result lands.
    expect(result.current.data?.overall_score).toBe(22);
  });
});
