import { useMemo, useRef, useState } from "react";

import { ArrowIcon, CheckIcon, FileIcon, ShieldIcon } from "../icons";
import { createTechnicalRubric } from "../rubric";
import type { SetupForm } from "../types";

type Props = {
  busy: boolean;
  error: string;
  onStart: (form: SetupForm) => Promise<void>;
};

export function SetupPanel({ busy, error, onStart }: Props) {
  const [role, setRole] = useState("Software Engineer");
  const [jobDescription, setJobDescription] = useState("");
  const [resume, setResume] = useState<File | null>(null);
  const [approved, setApproved] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const rubric = useMemo(() => createTechnicalRubric(role), [role]);
  const ready = resume && jobDescription.trim().length >= 20 && role.trim() && approved;

  return (
    <main className="setup-layout">
      <section className="setup-intro">
        <div className="eyebrow"><span /> Grounded voice interviews</div>
        <h1>Practice the interview that is actually meant for you.</h1>
        <p className="hero-copy">
          Your interviewer reads the resume and role you provide, asks evidence-led
          follow-ups, and returns a rubric-based scorecard after the call.
        </p>
        <div className="trust-row">
          <div><ShieldIcon /><span><strong>Private by design</strong>Raw resume PDF and audio are not stored</span></div>
          <div><CheckIcon /><span><strong>Grounded</strong>Questions cite your inputs</span></div>
        </div>
      </section>

      <section className="setup-card" aria-labelledby="setup-title">
        <div className="step-label">Interview setup <span>01 / 01</span></div>
        <h2 id="setup-title">Prepare your session</h2>
        <p className="muted">About 15 minutes · English · audio only</p>

        <label className="field-label" htmlFor="role">Target role</label>
        <input id="role" value={role} onChange={(event) => setRole(event.target.value)} placeholder="e.g. Backend Engineer" />

        <label className="field-label" htmlFor="job-description">Job description</label>
        <textarea id="job-description" value={jobDescription} onChange={(event) => setJobDescription(event.target.value)} placeholder="Paste the responsibilities and skills from the job posting…" rows={5} />
        <div className="character-count">{jobDescription.length.toLocaleString()} / 20,000</div>

        <label className="field-label">Resume PDF</label>
        <button type="button" className={`dropzone ${resume ? "has-file" : ""}`} onClick={() => inputRef.current?.click()}>
          <span className="file-icon"><FileIcon size={23} /></span>
          <span>
            <strong>{resume ? resume.name : "Choose your resume"}</strong>
            <small>{resume ? `${(resume.size / 1024).toFixed(0)} KB · click to replace` : "PDF · maximum 5 MB and 10 pages"}</small>
          </span>
          {resume && <span className="file-check"><CheckIcon size={16} /></span>}
        </button>
        <input ref={inputRef} className="visually-hidden" type="file" accept="application/pdf,.pdf" onChange={(event) => setResume(event.target.files?.[0] ?? null)} />

        <div className="rubric-box">
          <div className="rubric-heading"><span>Evaluation rubric</span><span>100% total</span></div>
          {rubric.criteria.map((criterion) => (
            <div className="rubric-row" key={criterion.criterion_id}>
              <span>{criterion.name}</span><strong>{criterion.weight}%</strong>
            </div>
          ))}
          <label className="approval-row">
            <input type="checkbox" checked={approved} onChange={(event) => setApproved(event.target.checked)} />
            <span>I reviewed and approve this rubric for the interview.</span>
          </label>
          <p className="retention-note">
            Extracted setup text is deleted when the call starts. Your scorecard is retained
            for seven days so you can retrieve it after the interview.
          </p>
        </div>

        {error && <div className="error-banner" role="alert">{error}</div>}
        <button className="primary-button" disabled={!ready || busy} onClick={() => resume && onStart({ resume, jobDescription, rubric })}>
          {busy ? "Preparing interview…" : "Start interview"}<ArrowIcon size={18} />
        </button>
      </section>
    </main>
  );
}
