import type { AnalysisResponse, JobDescription, Resume } from "@/types";

export type FieldErrorMap = Record<string, string>;

export class ApiFieldError extends Error {
  fieldErrors: FieldErrorMap;
  constructor(fieldErrors: FieldErrorMap) {
    super("Validation failed");
    this.name = "ApiFieldError";
    this.fieldErrors = fieldErrors;
  }
}

export class ApiServerError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiServerError";
  }
}

export class ApiNetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiNetworkError";
  }
}

type LocPart = string | number;

/**
 * FastAPI's 422 `detail[i].loc` is shaped like ["body", "<param-name>", ...rest].
 * We drop "body" + the top-level param name and join the rest into a dotted path
 * with `[i]` for numeric indices. E.g.:
 *   ["body", "resume", "experience", 0, "descriptions"] -> "experience[0].descriptions"
 *   ["body", "job_description", "title"] -> "title"
 */
export function flattenLoc(loc: LocPart[]): string {
  const stripped = loc.slice(2); // drop "body" and the top-level param name
  if (stripped.length === 0) return "";
  let out = "";
  for (const part of stripped) {
    if (typeof part === "number") {
      out += `[${part}]`;
    } else {
      if (out.length > 0) out += ".";
      out += part;
    }
  }
  return out;
}

type FastApiDetail =
  | { detail: string }
  | { detail: { loc: LocPart[]; msg: string; type: string }[] };

/**
 * POST /api/resume/analyze with the body shape the router expects:
 *   { resume: Resume, job_description: JobDescription }
 *
 * Throws:
 *  - ApiFieldError on 422 (FastAPI validation)
 *  - ApiServerError on other non-ok responses
 *  - ApiNetworkError on fetch reject (network down)
 *  - DOMException on abort (re-thrown unchanged)
 */
export async function analyze(
  resume: Resume,
  jd: JobDescription,
  signal?: AbortSignal,
): Promise<AnalysisResponse> {
  let resp: Response;
  try {
    resp = await fetch("/api/resume/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume, job_description: jd }),
      signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiNetworkError("Couldn't reach the analyzer. Is the backend running?");
  }

  if (resp.ok) {
    return (await resp.json()) as AnalysisResponse;
  }

  // Try to parse the FastAPI error body.
  let body: FastApiDetail | null = null;
  try {
    body = (await resp.json()) as FastApiDetail;
  } catch {
    // fall through to plain status-text error
  }

  if (body && Array.isArray((body as any).detail)) {
    const fieldErrors: FieldErrorMap = {};
    for (const item of (body as { detail: { loc: LocPart[]; msg: string }[] }).detail) {
      const path = flattenLoc(item.loc);
      if (path) fieldErrors[path] = item.msg;
    }
    throw new ApiFieldError(fieldErrors);
  }

  const detailStr =
    body && typeof (body as any).detail === "string"
      ? (body as { detail: string }).detail
      : `HTTP ${resp.status}`;
  throw new ApiServerError(`Analysis failed: ${detailStr}`);
}
