import type { ConversationMessage } from "@pipecat-ai/client-react";

import { ClockIcon, MicIcon, MutedIcon, SparkIcon } from "../icons";
import type { TimerSnapshot } from "../types";

type Props = {
  messages: ConversationMessage[];
  roleTitle: string;
  pageCount: number;
  transportState: string;
  timer: TimerSnapshot | null;
  displayedRemaining: number;
  speaking: "candidate" | "interviewer" | null;
  micEnabled: boolean;
  error: string;
  onToggleMic: () => void;
  onEnd: () => Promise<void>;
};

function messageText(message: ConversationMessage) {
  return (message.parts ?? []).map((part) => {
    if (typeof part.text === "string") return part.text;
    if (part.text && typeof part.text === "object" && "spoken" in part.text) {
      return String(part.text.spoken) + String(part.text.unspoken);
    }
    return "";
  }).join("");
}

function formatTime(seconds: number) {
  return `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${(seconds % 60).toString().padStart(2, "0")}`;
}

function phaseName(phase?: string) {
  return ({ opening: "Opening", main_interview: "Main interview", candidate_questions: "Your questions", closing: "Closing" } as Record<string, string>)[phase ?? ""] ?? "Getting ready";
}

export function LiveInterview(props: Props) {
  const progress = props.timer ? 1 - props.displayedRemaining / props.timer.duration_seconds : 0;
  const connected = props.transportState === "ready";
  return (
    <main className="live-layout">
      <section className="conversation-card">
        <div className="live-topline">
          <div><span className={`status-dot ${connected ? "online" : ""}`} />{connected ? "Live interview" : "Connecting"}</div>
          <div className="phase-pill">{phaseName(props.timer?.phase)}</div>
        </div>

        <div className={`voice-stage ${props.speaking ? "is-speaking" : ""}`}>
          <div className="voice-orbit"><div className="voice-core"><SparkIcon size={28} /></div></div>
          <h1>{props.speaking === "interviewer" ? "Interviewer is speaking" : props.speaking === "candidate" ? "Listening to you" : connected ? "Ready when you are" : "Opening the audio room"}</h1>
          <p>{connected ? "Speak naturally. You can interrupt or ask for a question to be repeated." : "Please allow microphone access when your browser asks."}</p>
          <div className="wave" aria-hidden="true">{[12,20,30,18,38,26,16,34,22,12].map((height, index) => <i key={index} style={{ height }} />)}</div>
        </div>

        <div className="transcript-head"><span>Live transcript</span><span>{props.messages.length} turns</span></div>
        <div className="transcript" aria-live="polite">
          {props.messages.length === 0 && <div className="empty-transcript">The conversation will appear here once the interview begins.</div>}
          {props.messages.map((message, index) => {
            const text = messageText(message);
            if (!text) return null;
            const candidate = message.role === "user";
            return <article className={`message ${candidate ? "candidate" : "interviewer"}`} key={`${message.createdAt}-${index}`}>
              <div className="message-avatar">{candidate ? "You" : "AI"}</div>
              <div><span>{candidate ? "You" : "Interviewer"}</span><p>{text}</p></div>
            </article>;
          })}
        </div>
      </section>

      <aside className="session-sidebar">
        <section className="timer-card">
          <div className="aside-label"><ClockIcon size={17} /> Time remaining</div>
          <div className="timer-value">{formatTime(props.displayedRemaining)}</div>
          <div className="progress-track"><span style={{ width: `${Math.max(0, Math.min(100, progress * 100))}%` }} /></div>
          <div className="timer-caption"><span>{phaseName(props.timer?.phase)}</span><span>15 min</span></div>
        </section>

        <section className="context-card">
          <div className="aside-label">Session context</div>
          <dl><div><dt>Role</dt><dd>{props.roleTitle}</dd></div><div><dt>Resume</dt><dd>{props.pageCount} {props.pageCount === 1 ? "page" : "pages"}</dd></div><div><dt>Language</dt><dd>English</dd></div><div><dt>Format</dt><dd>Voice interview</dd></div></dl>
          <div className="grounded-note"><span><SparkIcon size={16} /></span><p><strong>Grounding is active</strong>Questions use your resume, job description, and approved rubric.</p></div>
        </section>

        {props.error && <div className="error-banner" role="alert">{props.error}</div>}
        <div className="call-controls">
          <button className={`mic-button ${props.micEnabled ? "" : "muted"}`} onClick={props.onToggleMic} aria-label={props.micEnabled ? "Mute microphone" : "Unmute microphone"}>{props.micEnabled ? <MicIcon /> : <MutedIcon />}</button>
          <button className="end-button" onClick={props.onEnd}>End interview</button>
        </div>
        <p className="control-help">Ending the call starts scorecard evaluation.</p>
      </aside>
    </main>
  );
}
