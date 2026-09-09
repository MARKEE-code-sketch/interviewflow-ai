import { useCallback, useEffect, useRef, useState } from "react";
import { RTVIEvent, type TransportConnectionParams } from "@pipecat-ai/client-js";
import {
  usePipecatClient,
  usePipecatClientMicControl,
  usePipecatClientTransportState,
  usePipecatConversation,
  useRTVIClientEvent,
} from "@pipecat-ai/client-react";

import { getInterviewResult } from "./api";
import type { ResultResponse, TimerSnapshot } from "./types";

type StartResponse = TransportConnectionParams & { sessionId?: string; session_id?: string };

export function useInterview() {
  const client = usePipecatClient();
  const transportState = usePipecatClientTransportState();
  const { messages } = usePipecatConversation();
  const { enableMic, isMicEnabled } = usePipecatClientMicControl();
  const [sessionId, setSessionId] = useState("");
  const [timer, setTimer] = useState<TimerSnapshot | null>(null);
  const [displayedRemaining, setDisplayedRemaining] = useState(15 * 60);
  const [speaking, setSpeaking] = useState<"candidate" | "interviewer" | null>(null);
  const [result, setResult] = useState<ResultResponse | null>(null);
  const [error, setError] = useState("");
  const timerSyncedAt = useRef(0);

  useRTVIClientEvent(RTVIEvent.ServerMessage, useCallback((data: unknown) => {
    const snapshot = data as TimerSnapshot;
    if (snapshot?.type !== "interview_timer") return;
    setTimer(snapshot);
    setDisplayedRemaining(snapshot.remaining_seconds);
    timerSyncedAt.current = Date.now();
  }, []));
  useRTVIClientEvent(RTVIEvent.UserStartedSpeaking, useCallback(() => setSpeaking("candidate"), []));
  useRTVIClientEvent(RTVIEvent.UserStoppedSpeaking, useCallback(() => setSpeaking(null), []));
  useRTVIClientEvent(RTVIEvent.BotStartedSpeaking, useCallback(() => setSpeaking("interviewer"), []));
  useRTVIClientEvent(RTVIEvent.BotStoppedSpeaking, useCallback(() => setSpeaking(null), []));
  useRTVIClientEvent(RTVIEvent.Error, useCallback(() => setError("The voice session reported an error. Check the server log for the safe error code."), []));

  useEffect(() => {
    const interval = window.setInterval(() => {
      if (!timer || transportState !== "ready") return;
      const sinceSync = Math.floor((Date.now() - timerSyncedAt.current) / 1000);
      setDisplayedRemaining(Math.max(0, timer.remaining_seconds - sinceSync));
    }, 250);
    return () => window.clearInterval(interval);
  }, [timer, transportState]);

  const start = async (setupId: string) => {
    if (!client) throw new Error("The voice client is not ready.");
    setError("");
    setResult(null);
    setTimer(null);
    setDisplayedRemaining(15 * 60);
    const connection = await client.startBot({
      endpoint: "/start",
      requestData: {
        transport: "webrtc",
        enableDefaultIceServers: true,
        body: { setup_id: setupId },
      },
    }) as StartResponse;
    const id = connection.sessionId ?? connection.session_id;
    if (!id) throw new Error("The server did not return an interview session ID.");
    setSessionId(id);
    await client.connect(connection);
  };

  const loadResult = async (id = sessionId) => {
    if (!id) return;
    for (let attempt = 0; attempt < 60; attempt += 1) {
      try {
        const next = await getInterviewResult(id);
        setResult(next);
        if (next.status !== "evaluating") return;
      } catch (reason) {
        if (attempt > 2) setError(reason instanceof Error ? reason.message : "The scorecard could not be loaded.");
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
    setError("Scorecard evaluation is taking longer than expected. You can retry shortly.");
  };

  const end = async () => {
    if (!client) throw new Error("The voice client is not ready.");
    setSpeaking(null);
    await client.disconnect();
    await loadResult();
  };

  const reset = () => {
    setSessionId("");
    setTimer(null);
    setResult(null);
    setError("");
    setDisplayedRemaining(15 * 60);
  };

  return {
    transportState,
    messages,
    timer,
    displayedRemaining,
    speaking,
    result,
    error,
    sessionId,
    micEnabled: isMicEnabled,
    setError,
    start,
    end,
    loadResult,
    reset,
    toggleMic: () => enableMic(!isMicEnabled),
  };
}
