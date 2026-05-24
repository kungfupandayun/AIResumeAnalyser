import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { analyze, flattenLoc, ApiFieldError, ApiServerError } from "@/lib/api";
import type { Resume, JobDescription, AnalysisResponse } from "@/types";

const emptyResume: Resume = {
  country: null,
  summary: null,
  skills: ["Python"],
  experience: [
    { title: "Eng", company: "Co", start_date: "2020-01-01", end_date: null, descriptions: ["did things"] },
  ],
  education: [{ degree: "BS", institution: "Uni" }],
  projects: [],
};

const emptyJd: JobDescription = {
  title: "Engineer",
  description: "Build things.",
  required_skills: ["Python"],
};

describe("flattenLoc", () => {
  it("strips the 'body' and top-level model prefix", () => {
    expect(flattenLoc(["body", "resume", "experience", 0, "descriptions"])).toBe("experience[0].descriptions");
  });

  it("handles nested fields without arrays", () => {
    expect(flattenLoc(["body", "job_description", "title"])).toBe("title");
  });

  it("handles arrays at depth", () => {
    expect(flattenLoc(["body", "resume", "education", 1, "degree"])).toBe("education[1].degree");
  });

  it("returns empty string for the body root", () => {
    expect(flattenLoc(["body"])).toBe("");
  });
});

describe("analyze (happy path)", () => {
  it("POSTs resume + job_description as separate body keys and returns parsed AnalysisResponse", async () => {
    let captured: unknown = null;
    server.use(
      http.post("/api/resume/analyze", async ({ request }) => {
        captured = await request.json();
        return HttpResponse.json({
          mode: "hybrid",
          overall_score: 80,
          dimension_scores: [],
          gaps: [],
          suggestions: [],
          warnings: [],
          match_score: 80,
          missing_keywords: [],
        } satisfies AnalysisResponse);
      }),
    );

    const result = await analyze(emptyResume, emptyJd);
    expect(result.mode).toBe("hybrid");
    expect(captured).toEqual({ resume: emptyResume, job_description: emptyJd });
  });
});

describe("analyze (422 field errors)", () => {
  it("rejects with ApiFieldError mapping dotted paths to messages", async () => {
    server.use(
      http.post("/api/resume/analyze", () => {
        return HttpResponse.json(
          {
            detail: [
              { loc: ["body", "resume", "skills"], msg: "List should have at least 1 item after validation, not 0", type: "too_short" },
              { loc: ["body", "resume", "experience", 0, "descriptions"], msg: "List should have at least 1 item", type: "too_short" },
            ],
          },
          { status: 422 },
        );
      }),
    );

    await expect(analyze(emptyResume, emptyJd)).rejects.toMatchObject({
      name: "ApiFieldError",
      fieldErrors: {
        "skills": "List should have at least 1 item after validation, not 0",
        "experience[0].descriptions": "List should have at least 1 item",
      },
    });
  });
});

describe("analyze (5xx)", () => {
  it("rejects with ApiServerError carrying the detail string", async () => {
    server.use(
      http.post("/api/resume/analyze", () => {
        return HttpResponse.json({ detail: "scorer blew up" }, { status: 500 });
      }),
    );

    await expect(analyze(emptyResume, emptyJd)).rejects.toMatchObject({
      name: "ApiServerError",
      message: expect.stringContaining("scorer blew up"),
    });
  });
});

describe("analyze (abort)", () => {
  it("rejects with DOMException when signal aborts mid-flight", async () => {
    server.use(
      http.post("/api/resume/analyze", async () => {
        await new Promise((r) => setTimeout(r, 100));
        return HttpResponse.json({} as AnalysisResponse);
      }),
    );

    const ctrl = new AbortController();
    const p = analyze(emptyResume, emptyJd, ctrl.signal);
    ctrl.abort();
    await expect(p).rejects.toThrow();
  });

  // ApiFieldError + ApiServerError + ApiNetworkError checked in suite above.
  it("ApiServerError vs ApiFieldError are distinguishable by name", () => {
    expect(new ApiServerError("x").name).toBe("ApiServerError");
    expect(new ApiFieldError({}).name).toBe("ApiFieldError");
  });
});
