const explicitBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
const renderApiHost = import.meta.env.VITE_API_HOST?.trim();

export const apiBaseUrl = (
  explicitBaseUrl || (renderApiHost ? `https://${renderApiHost}` : "")
).replace(/\/$/, "");

const configuredTransport = (import.meta.env.VITE_VOICE_TRANSPORT || "webrtc").toLowerCase();

if (configuredTransport !== "webrtc" && configuredTransport !== "daily") {
  throw new Error("VITE_VOICE_TRANSPORT must be either 'webrtc' or 'daily'.");
}

export const voiceTransport = configuredTransport as "webrtc" | "daily";

export function backendUrl(path: string): string {
  return `${apiBaseUrl}${path}`;
}
