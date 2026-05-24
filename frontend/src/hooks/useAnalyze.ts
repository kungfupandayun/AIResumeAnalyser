import { useCallback, useRef, useState } from "react";
import type { AnalysisResponse, Resume, JobDescription } from "@/types";
import { analyze as apiAnalyze, ApiFieldError, ApiServerError, ApiNetworkError, type FieldErrorMap } from "@/lib/api";

export type UseAnalyzeReturn = {
  data: AnalysisResponse | null;
  loading: boolean;
  error: string | null;
  fieldErrors: FieldErrorMap;
  analyze: (resume: Resume, jd: JobDescription) => Promise<void>;
};

export function useAnalyze(): UseAnalyzeReturn {
  const [data, setData] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrorMap>({});
  const inflight = useRef<AbortController | null>(null);

  const analyze = useCallback(async (resume: Resume, jd: JobDescription) => {
    // Abort any in-flight request.
    inflight.current?.abort();
    const ctrl = new AbortController();
    inflight.current = ctrl;

    setLoading(true);
    setError(null);
    setFieldErrors({});

    try {
      const result = await apiAnalyze(resume, jd, ctrl.signal);
      // If we were aborted between fetch resolving and now, drop the result.
      if (ctrl.signal.aborted) return;
      setData(result);
    } catch (e) {
      if (ctrl.signal.aborted) return; // silently swallow aborts
      if (e instanceof ApiFieldError) {
        setFieldErrors(e.fieldErrors);
      } else if (e instanceof ApiServerError || e instanceof ApiNetworkError) {
        setError(e.message);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      if (!ctrl.signal.aborted) setLoading(false);
    }
  }, []);

  return { data, loading, error, fieldErrors, analyze };
}
