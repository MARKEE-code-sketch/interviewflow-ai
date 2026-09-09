// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { getInterviewResult } from "./api";

describe("client API errors", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("explains how to recover when the Python backend is offline", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(getInterviewResult("test-session")).rejects.toThrow(
      "Start the Python server",
    );
  });
});
