import { describe, it, expect } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import App from "@/App";

describe("App (integration smoke)", () => {
  it("fills minimum-valid form, clicks Analyze, and renders the overall score", async () => {
    server.use(
      http.post("/api/resume/analyze", () =>
        HttpResponse.json({
          mode: "hybrid",
          overall_score: 77,
          dimension_scores: [
            { name: "skills", score: 100, weight: 0.5, rationale: "1/1 matched" },
            { name: "experience", score: 50, weight: 0.5, rationale: "x" },
          ],
          gaps: [],
          suggestions: [],
          warnings: [],
          match_score: 77,
          missing_keywords: [],
        }),
      ),
    );

    const user = userEvent.setup();
    const { container } = render(<App />);

    // Skills tag input — label text "Skills" is unique in the full app
    await user.type(screen.getByLabelText(/^skills$/i), "Python{Enter}");

    // Experience #1 fields — use stable IDs to avoid label-text collisions
    // ("Job title" label appears in both Resume and JD sections)
    await user.type(
      container.querySelector("#exp-0-title") as HTMLInputElement,
      "Engineer",
    );
    await user.type(
      container.querySelector("#exp-0-company") as HTMLInputElement,
      "Acme",
    );

    // Date input — user.type may not work on <input type="date"> in jsdom,
    // so use fireEvent.change as a reliable fallback.
    fireEvent.change(
      container.querySelector("#exp-0-start") as HTMLInputElement,
      { target: { value: "2020-01-01" } },
    );

    // Fill the pre-rendered bullet via aria-label (added in Task 12)
    await user.type(
      screen.getByLabelText(/Bullet 1 for experience 1/i),
      "Built things",
    );

    // JD title — use stable ID to avoid collision with experience "Job title"
    await user.type(
      container.querySelector("#jd-title") as HTMLInputElement,
      "Engineer",
    );

    // Click Analyze — the button text is "Analyze ↓"
    const analyzeBtn = screen.getByRole("button", { name: /analyze/i });
    await waitFor(() => expect(analyzeBtn).toBeEnabled());
    await user.click(analyzeBtn);

    // Score 77 appears in the Results card
    await waitFor(() => expect(screen.getByText("77")).toBeInTheDocument());
  });
});
