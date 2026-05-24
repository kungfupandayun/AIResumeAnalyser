import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResumeForm } from "@/components/ResumeForm";
import type { Resume } from "@/types";

const seed: Resume = {
  country: null,
  summary: null,
  skills: [],
  experience: [
    { title: "", company: "", start_date: null, end_date: null, descriptions: [""] },
  ],
  education: [],
  projects: [],
};

describe("<ResumeForm />", () => {
  it("does NOT render name, email, phone inputs (PII removed)", () => {
    render(<ResumeForm value={seed} onChange={() => {}} />);
    expect(screen.queryByLabelText(/name/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/phone/i)).not.toBeInTheDocument();
  });

  it("renders the PII notice", () => {
    render(<ResumeForm value={seed} onChange={() => {}} />);
    expect(screen.getByText(/don.t collect your name, email/i)).toBeInTheDocument();
  });

  it("renders country, summary, skills, and one experience row by default", () => {
    render(<ResumeForm value={seed} onChange={() => {}} />);
    expect(screen.getByLabelText(/country/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/summary/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/skills/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/job title/i)).toBeInTheDocument();
  });

  it("updates country", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ResumeForm value={seed} onChange={onChange} />);
    await user.type(screen.getByLabelText(/country/i), "C");
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ country: "C" }));
  });

  it("adds an experience row via + Add another", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ResumeForm value={seed} onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /add another experience/i }));
    const lastCall = onChange.mock.lastCall![0] as Resume;
    expect(lastCall.experience.length).toBe(2);
  });

  it("removes an experience row via delete button", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const twoExp: Resume = {
      ...seed,
      experience: [
        { title: "A", company: "X", start_date: "2020-01-01", end_date: null, descriptions: ["d"] },
        { title: "B", company: "Y", start_date: "2021-01-01", end_date: null, descriptions: ["d"] },
      ],
    };
    render(<ResumeForm value={twoExp} onChange={onChange} />);
    const removes = screen.getAllByRole("button", { name: /remove experience/i });
    await user.click(removes[0]);
    const lastCall = onChange.mock.lastCall![0] as Resume;
    expect(lastCall.experience.length).toBe(1);
    expect(lastCall.experience[0].title).toBe("B");
  });

  it("adds an education row", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ResumeForm value={seed} onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /add another education/i }));
    const lastCall = onChange.mock.lastCall![0] as Resume;
    expect(lastCall.education.length).toBe(1);
  });

  it("renders fieldErrors at the matching dotted path", () => {
    render(
      <ResumeForm
        value={seed}
        onChange={() => {}}
        fieldErrors={{ "experience[0].title": "Required field" }}
      />,
    );
    expect(screen.getByText(/required field/i)).toBeInTheDocument();
  });

  it("adds a description bullet within an experience", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ResumeForm value={seed} onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /add bullet/i }));
    const lastCall = onChange.mock.lastCall![0] as Resume;
    expect(lastCall.experience[0].descriptions.length).toBe(2);
  });

  it("removes a project contribution via delete button", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const withProject: Resume = {
      ...seed,
      projects: [
        {
          name: "P",
          tech_stack: [],
          description: "",
          contributions: ["first", "second"],
        },
      ],
    };
    render(<ResumeForm value={withProject} onChange={onChange} />);
    await user.click(
      screen.getByRole("button", { name: /remove contribution 1 from project 1/i }),
    );
    const lastCall = onChange.mock.lastCall![0] as Resume;
    expect(lastCall.projects![0].contributions.length).toBe(1);
    expect(lastCall.projects![0].contributions[0]).toBe("second");
  });
});
