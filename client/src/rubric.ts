import type { ApprovedRubric } from "./types";

export function createTechnicalRubric(roleTitle: string): ApprovedRubric {
  return {
    rubric_id: "technical-interview-mvp",
    role_title: roleTitle.trim() || "Software Engineer",
    version: 1,
    criteria: [
      {
        criterion_id: "reasoning",
        name: "Technical reasoning",
        definition: "Explains implementation decisions, alternatives, constraints, and trade-offs.",
        weight: 60,
        anchors: {
          "1": "No relevant reasoning",
          "2": "Major reasoning gaps",
          "3": "Explains a workable approach",
          "4": "Explains decisions and trade-offs",
          "5": "Supports decisions with alternatives, constraints, and evidence",
        },
      },
      {
        criterion_id: "evidence",
        name: "Evidence and measurement",
        definition: "Supports claims with concrete implementation details and appropriate measurements.",
        weight: 40,
        anchors: {
          "1": "No supporting evidence",
          "2": "Vague claims",
          "3": "Concrete implementation example",
          "4": "Relevant measurements or observations",
          "5": "Clear reproducible evaluation with limitations acknowledged",
        },
      },
    ],
  };
}
