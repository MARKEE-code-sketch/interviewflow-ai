// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SetupPanel } from "./SetupPanel";

describe("SetupPanel", () => {
  it("requires every reviewed input before starting", () => {
    const onStart = vi.fn().mockResolvedValue(undefined);
    render(<SetupPanel busy={false} error="" onStart={onStart} />);
    const start = screen.getByRole("button", { name: /start interview/i });
    expect(start).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/job description/i), {
      target: { value: "Build reliable Python APIs and explain design trade-offs." },
    });
    const file = new File(["%PDF-test"], "resume.pdf", { type: "application/pdf" });
    fireEvent.change(document.querySelector('input[type="file"]')!, {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("checkbox"));

    expect(start).toBeEnabled();
    fireEvent.click(start);
    expect(onStart).toHaveBeenCalledOnce();
  });
});
