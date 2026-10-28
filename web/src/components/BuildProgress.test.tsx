import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BuildProgress } from "./BuildProgress";

describe("BuildProgress", () => {
  it("shows the server's current step and completed steps", () => {
    render(<BuildProgress progress={{ done: 3, total: 8, label: "Read the May 2026 earnings call (2 of 4)" }} waking={false} />);
    expect(screen.getByText("Read the May 2026 earnings call (2 of 4)")).toBeTruthy();
    expect(screen.getByText("3 of 8 steps")).toBeTruthy();
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("3");
  });

  it("says the server is waking before any step is reported", () => {
    render(<BuildProgress progress={null} waking={true} />);
    expect(screen.getByText(/Waking the research server/)).toBeTruthy();
  });
});
