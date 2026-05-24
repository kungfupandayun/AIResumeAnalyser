import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { JdForm } from "@/components/JdForm";
import type { JobDescription } from "@/types";

const empty: JobDescription = { title: "", description: "", required_skills: [] };

describe("<JdForm />", () => {
  it("renders title, description, and required-skills inputs", () => {
    render(<JdForm value={empty} onChange={() => {}} />);
    expect(screen.getByLabelText(/job title/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/required skills/i)).toBeInTheDocument();
  });

  it("updates title via onChange", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<JdForm value={empty} onChange={onChange} />);
    await user.type(screen.getByLabelText(/job title/i), "X");
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ title: "X" }));
  });

  it("updates description via onChange", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<JdForm value={empty} onChange={onChange} />);
    await user.type(screen.getByLabelText(/description/i), "Y");
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ description: "Y" }));
  });

  it("adds a required skill via the tag input", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<JdForm value={empty} onChange={onChange} />);
    await user.type(screen.getByLabelText(/required skills/i), "Python{Enter}");
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ required_skills: ["Python"] }));
  });

  it("renders inline field error for title", () => {
    render(<JdForm value={empty} onChange={() => {}} fieldErrors={{ title: "Required" }} />);
    expect(screen.getByText(/^required$/i)).toBeInTheDocument();
  });
});
