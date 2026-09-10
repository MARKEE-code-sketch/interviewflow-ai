import { describe, expect, it } from "vitest";

import { parseVoiceTransport } from "./deployment";

describe("voice transport configuration", () => {
  it("uses SmallWebRTC by default for local development", () => {
    expect(parseVoiceTransport()).toBe("webrtc");
  });

  it("accepts LiveKit for hosted interviews", () => {
    expect(parseVoiceTransport("livekit")).toBe("livekit");
  });

  it("rejects an unsupported transport", () => {
    expect(() => parseVoiceTransport("daily")).toThrow(
      "VITE_VOICE_TRANSPORT must be either 'webrtc' or 'livekit'.",
    );
  });
});
