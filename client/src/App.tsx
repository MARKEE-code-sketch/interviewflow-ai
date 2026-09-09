import { useEffect, useState } from "react";

import { prepareInterview } from "./api";
import { LiveInterview } from "./components/LiveInterview";
import { ScorecardView } from "./components/ScorecardView";
import { SetupPanel } from "./components/SetupPanel";
import { SparkIcon } from "./icons";
import type { SetupForm } from "./types";
import { useInterview } from "./useInterview";

type Screen = "setup" | "live" | "scorecard";

export default function App() {
  const interview = useInterview();
  const [screen, setScreen] = useState<Screen>("setup");
  const [busy, setBusy] = useState(false);
  const [setup, setSetup] = useState<SetupForm | null>(null);
  const [pageCount, setPageCount] = useState(0);
  const [wasReady, setWasReady] = useState(false);

  useEffect(() => {
    if (screen !== "live") return;
    if (interview.transportState === "ready") setWasReady(true);
    if (wasReady && interview.transportState === "disconnected") {
      setScreen("scorecard");
      void interview.loadResult();
    }
  }, [screen, wasReady, interview.transportState]);

  const start = async (form: SetupForm) => {
    setBusy(true);
    interview.setError("");
    try {
      const prepared = await prepareInterview(form);
      setSetup(form);
      setPageCount(prepared.page_count);
      setWasReady(false);
      setScreen("live");
      await interview.start(prepared.setup_id);
    } catch (reason) {
      setScreen("setup");
      interview.setError(reason instanceof Error ? reason.message : "The interview could not start.");
    } finally {
      setBusy(false);
    }
  };

  const end = async () => {
    setScreen("scorecard");
    await interview.end();
  };

  const restart = () => {
    interview.reset();
    setWasReady(false);
    setSetup(null);
    setScreen("setup");
  };

  return <div className="app-shell">
    <header className="app-header">
      <a className="brand" href="/" onClick={(event) => { event.preventDefault(); if (screen === "setup") restart(); }}><span><SparkIcon size={19} /></span>InterviewFlow <em>AI</em></a>
      <div className="header-meta"><span className="privacy-dot" />Audio is not recorded</div>
    </header>
    {screen === "setup" && <SetupPanel busy={busy} error={interview.error} onStart={start} />}
    {screen === "live" && setup && <LiveInterview messages={interview.messages} roleTitle={setup.rubric.role_title} pageCount={pageCount} transportState={interview.transportState} timer={interview.timer} displayedRemaining={interview.displayedRemaining} speaking={interview.speaking} micEnabled={interview.micEnabled} error={interview.error} onToggleMic={interview.toggleMic} onEnd={end} />}
    {screen === "scorecard" && setup && <ScorecardView result={interview.result} rubric={setup.rubric} error={interview.error} onRestart={restart} />}
  </div>;
}
