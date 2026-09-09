import { CheckIcon, ShieldIcon, SparkIcon } from "../icons";
import type { ApprovedRubric, ResultResponse } from "../types";

type Props = { result: ResultResponse | null; rubric: ApprovedRubric; error: string; onRestart: () => void };

export function ScorecardView({ result, rubric, error, onRestart }: Props) {
  if (!result || result.status === "evaluating") {
    return <main className="result-loading"><div className="score-loader"><SparkIcon size={30} /></div><h1>Building your scorecard</h1><p>The evaluator is matching your answers to exact transcript evidence. This can take a moment.</p>{error && <div className="error-banner">{error}</div>}</main>;
  }
  if (result.status === "unavailable" || !result.scorecard) {
    return <main className="result-loading"><div className="score-loader warning">!</div><h1>Scorecard unavailable</h1><p>{result.message || error}</p><button className="primary-button compact" onClick={onRestart}>Start a new interview</button></main>;
  }
  const scorecard = result.scorecard;
  return <main className="scorecard-page">
    <section className="score-hero">
      <div><div className="eyebrow"><span /> Interview complete</div><h1>Your evidence-led scorecard</h1><p>Scores are calculated only from applicable rubric criteria with exact candidate evidence.</p></div>
      <div className="overall-score"><span>{scorecard.overall_score ?? "—"}</span><small>out of 100</small></div>
    </section>
    {scorecard.needs_human_review && <div className="review-banner"><ShieldIcon /><div><strong>Human review recommended</strong><p>{scorecard.review_reason}</p></div></div>}
    <div className="score-grid">
      <section className="criteria-panel"><div className="panel-heading"><h2>Rubric breakdown</h2><span>{scorecard.coverage_percent}% coverage</span></div>
        {scorecard.criteria.map((criterion) => {
          const definition = rubric.criteria.find((item) => item.criterion_id === criterion.criterion_id);
          return <article className="criterion-result" key={criterion.criterion_id}>
            <div className="criterion-title"><div><span className="result-check"><CheckIcon size={15} /></span><div><h3>{definition?.name ?? criterion.criterion_id}</h3><p>{criterion.reason}</p></div></div><strong>{criterion.score ?? "N/A"}<small>/ 5</small></strong></div>
            {criterion.score && <div className="score-track"><span style={{ width: `${criterion.score * 20}%` }} /></div>}
            {criterion.evidence.length > 0 && <blockquote>“{criterion.evidence[0].quote}”<cite>{criterion.evidence[0].turn_id}</cite></blockquote>}
            {criterion.improvement && <div className="improvement"><span>Next step</span>{criterion.improvement}</div>}
          </article>;
        })}
      </section>
      <aside className="result-sidebar"><section><div className="aside-label">Evaluation facts</div><dl><div><dt>Coverage</dt><dd>{scorecard.coverage_percent}%</dd></div><div><dt>Model</dt><dd>{scorecard.evaluator_model}</dd></div><div><dt>Rubric</dt><dd>v{rubric.version}</dd></div></dl></section><button className="primary-button" onClick={onRestart}>Practice again</button></aside>
    </div>
  </main>;
}
