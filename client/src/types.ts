export type RubricCriterion = {
  criterion_id: string;
  name: string;
  definition: string;
  weight: number;
  anchors: Record<"1" | "2" | "3" | "4" | "5", string>;
};

export type ApprovedRubric = {
  rubric_id: string;
  role_title: string;
  version: number;
  criteria: RubricCriterion[];
};

export type SetupForm = {
  resume: File;
  jobDescription: string;
  rubric: ApprovedRubric;
};

export type TimerSnapshot = {
  type: "interview_timer";
  phase: string;
  duration_seconds: number;
  elapsed_seconds: number;
  remaining_seconds: number;
};

export type Evidence = { turn_id: string; quote: string };

export type CriterionScore = {
  criterion_id: string;
  applicable: boolean;
  score: number | null;
  confidence: "high" | "medium" | "low";
  evidence: Evidence[];
  reason: string;
  improvement: string;
};

export type Scorecard = {
  overall_score: number | null;
  coverage_percent: number;
  needs_human_review: boolean;
  review_reason: string | null;
  criteria: CriterionScore[];
  evaluator_model: string;
};

export type ResultResponse = {
  status: "evaluating" | "complete" | "unavailable";
  scorecard?: Scorecard;
  message?: string;
};
