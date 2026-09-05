/**
 * SNAPTIX domain model.
 *
 * This is a conceptual data model, not a database schema -- there is no
 * persistence layer in the backend yet (see backend/app/models, which is
 * empty). These types describe the shape any future PostgreSQL-backed API
 * should return, so the UI can be built against a stable contract now and
 * re-wired to real endpoints later without a redesign.
 *
 * Every value that flows through these types in the running app currently
 * comes from one of two places, and every screen must say which:
 *  - `demoData.ts` — a fabricated but internally-consistent sample dataset
 *    (labelled "Demo data" in the UI wherever it appears).
 *  - the real `/handwritten/evaluate` backend call — genuine OCR + Gemini
 *    output, tagged `source: "real-evaluation"` below.
 */

export type DataSource = "demo" | "local" | "real-evaluation";

export interface Faculty {
  id: string;
  name: string;
  title: string;
  subjectIds: string[];
}

export interface Student {
  id: string;
  name: string;
  rollNumber: string;
  subjectIds: string[];
}

export interface Subject {
  id: string;
  code: string;
  name: string;
  facultyId: string;
  /** Primary Course Outcome this subject rolls up to, for the CO/PO demo surface. */
  coCode: string;
}

export interface RubricCriterion {
  name: string;
  maxScore: number;
}

export interface Question {
  id: string; // "Q1", "Q2", ...
  text: string;
  modelAnswer: string;
  maxScore: number;
  criteria: RubricCriterion[];
  /** Topic tag used only by the Learning Gaps demo surface (Part 13). */
  topic: string;
}

export type AssessmentStatus = "draft" | "published";

export interface Assessment {
  id: string;
  title: string;
  subjectId: string;
  date: string; // ISO date
  totalMarks: number;
  questions: Question[];
  status: AssessmentStatus;
  source: DataSource;
}

export interface QuestionResult {
  questionId: string;
  score: number;
  maxScore: number;
  conceptScore: number;
  accuracyScore: number;
  precisionScore: number;
  technicalTerminologyScore: number;
  strengths: string[];
  missingConcepts: string[];
  feedback: string;
  confidence: number;
  ocrConfidence: number;
  combinedConfidence: number;
  needsReview: boolean;
  answerDetected: boolean;
  studentAnswer: string;
}

export type SubmissionStatus = "pending" | "evaluated";

export interface Submission {
  id: string;
  assessmentId: string;
  studentId: string;
  status: SubmissionStatus;
  results: QuestionResult[];
  totalScore: number;
  totalMaxScore: number;
  overallConfidence: number;
  needsReview: boolean;
  evaluatedAt: string | null;
  source: DataSource;
}

export type GapStatus = "Strong" | "Moderate" | "Needs Improvement" | "Weak";

export interface LearningGapEntry {
  topic: string;
  subjectId: string;
  performancePercent: number;
  status: GapStatus;
  recommendation: string;
}

export interface COAttainment {
  code: string;
  description: string;
  targetPercent: number;
  achievedPercent: number;
  subjectId: string;
}

export interface POAttainment {
  code: string;
  description: string;
}

/** Illustrative CO→PO correlation strength, 1 (slight) to 3 (strong). This is
 * a demo mapping, not one derived from an accreditation-approved OBE
 * framework -- see the caption shown alongside it in the UI. */
export interface COPOLink {
  coCode: string;
  poCode: string;
  weight: 1 | 2 | 3;
}
