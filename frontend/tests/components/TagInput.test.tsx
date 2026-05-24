import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TagInput } from "@/components/TagInput";

describe("<TagInput />", () => {
  it("renders existing tags", () => {
    render(<TagInput value={["Python", "AWS"]} onChange={() => {}} label="Skills" />);
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("AWS")).toBeInTheDocument();
  });

  it("adds a tag on Enter", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} label="Skills" />);
    const input = screen.getByLabelText("Skills");
    await user.type(input, "Python{Enter}");
    expect(onChange).toHaveBeenCalledWith(["Python"]);
  });

  it("adds a tag on comma", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} label="Skills" />);
    await user.type(screen.getByLabelText("Skills"), "Python,");
    expect(onChange).toHaveBeenCalledWith(["Python"]);
  });

  it("trims whitespace and ignores empty additions", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} label="Skills" />);
    await user.type(screen.getByLabelText("Skills"), "  {Enter}");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("does not add duplicates (case-insensitive)", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TagInput value={["Python"]} onChange={onChange} label="Skills" />);
    await user.type(screen.getByLabelText("Skills"), "python{Enter}");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("removes a tag when its remove button is clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TagInput value={["Python", "AWS"]} onChange={onChange} label="Skills" />);
    await user.click(screen.getByRole("button", { name: /remove python/i }));
    expect(onChange).toHaveBeenCalledWith(["AWS"]);
  });

  it("renders the error message when error prop is set", () => {
    render(<TagInput value={[]} onChange={() => {}} label="Skills" error="At least 1 required" />);
    expect(screen.getByText(/at least 1 required/i)).toBeInTheDocument();
  });
});
