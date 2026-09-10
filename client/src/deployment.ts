const explicitBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
const renderApiHost = import.meta.env.VITE_API_HOST?.trim();

export const apiBaseUrl = (
  explicitBaseUrl || (renderApiHost ? `https://${renderApiHost}` : "")
).replace(/\/$/, "");

export type VoiceTransport = "webrtc" | "livekit";

export function parseVoiceTransport(value?: string): VoiceTransport {
  const configured = (value || "webrtc").toLowerCase();
  if (configured !== "webrtc" && configured !== "livekit") {
    throw new Error("VITE_VOICE_TRANSPORT must be either 'webrtc' or 'livekit'.");
  }
  return configured;
}

export const voiceTransport = parseVoiceTransport(import.meta.env.VITE_VOICE_TRANSPORT);

export function backendUrl(path: string): string {
  return `${apiBaseUrl}${path}`;
}
