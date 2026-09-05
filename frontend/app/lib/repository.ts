/**
 * Single read layer over the demo dataset (`demoData.ts`) plus any
 * locally-created assessments (`localAssessments.ts`). Every derived number
 * shown in the UI (averages, ranks, attainment percentages, distributions)
 * is computed here from the raw seed data -- nothing is a separately
 * hand-typed "summary" number, so the dashboard, analytics and learning-gap
 * pages can never mathematically contradict each other.
 *
 * This is the "clearly isolated repository/service layer with demo data"
 * called for in Part 7 of the project brief, standing in for a future
 * PostgreSQL-backed API. Swapping the body of these functions for real
 * fetch() calls later should not require changing any page that imports
 * them.
 */

import {
  ASSESSMENTS,
  CO_DEFINITIONS,
  CO_PO_LINKS,
  FACULTY,
  PO_DEFINITIONS,
  STUDENTS,
  SUBJECTS,
  SUBMISSIONS,
} from "./demoData";
import type {
  Assessment,
  COAttainment,
  GapStatus,
  LearningGapEntry,
  POAttainment,
  Question,
  Student,
  Subject,
  Submission,
} from "./domain";
import { getLocalAssessments, getLocalSubmissions } from "./localAssessments";

/** Demo seed submissions plus any saved locally this session (e.g. a real
 * evaluation run through the assessment workflow). */
function allSubmissions(): Submission[] {
  return [...SUBMISSIONS, ...getLocalSubmissions()];
}

// ---------------------------------------------------------------------------
// Base lookups
// ---------------------------------------------------------------------------

export function getFaculty() {
  return FACULTY;
}

export function getSubjects(): Subject[] {
  return SUBJECTS;
}

export function getSubjectById(id: string): Subject | undefined {
  return SUBJECTS.find((s) => s.id === id);
}

export function getStudents(): Student[] {
  return STUDENTS;
}

export function getStudentById(id: string): Student | undefined {
  return STUDENTS.find((s) => s.id === id);
}

/** Demo seed assessments plus any created locally this session (Part 9). */
export function getAssessments(): Assessment[] {
  return [...ASSESSMENTS, ...getLocalAssessments()];
}

export function getAssessmentById(id: string): Assessment | undefined {
  return getAssessments().find((a) => a.id === id);
}

export function getAssessmentsBySubject(subjectId: string): Assessment[] {
  return getAssessments().filter((a) => a.subjectId === subjectId);
}

export function getQuestionById(assessment: Assessment, questionId: string): Question | undefined {
  return assessment.questions.find((q) => q.id === questionId);
}

export function getSubmissionsByAssessment(assessmentId: string): Submission[] {
  return allSubmissions().filter((s) => s.assessmentId === assessmentId);
}

export function getSubmissionsByStudent(studentId: string): Submission[] {
  return allSubmissions().filter((s) => s.studentId === studentId);
}

export function getSubmission(assessmentId: string, studentId: string): Submission | undefined {
  return allSubmissions().find((s) => s.assessmentId === assessmentId && s.studentId === studentId);
}

function pct(score: number, max: number): number {
  return max > 0 ? (score / max) * 100 : 0;
}

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

// ---------------------------------------------------------------------------
// Faculty dashboard
// ---------------------------------------------------------------------------

export interface FacultyOverview {
  totalStudents: number;
  totalAssessments: number;
  evaluatedSubmissions: number;
  pendingReviews: number;
  classAveragePercent: number;
  needsReviewCount: number;
}

export function getFacultyOverview(): FacultyOverview {
  const evaluated = allSubmissions().filter((s) => s.status === "evaluated");
  const pending = allSubmissions().filter((s) => s.status === "pending");
  const avg =
    evaluated.length > 0
      ? evaluated.reduce((sum, s) => sum + pct(s.totalScore, s.totalMaxScore), 0) / evaluated.length
      : 0;
  return {
    totalStudents: STUDENTS.length,
    totalAssessments: getAssessments().length,
    evaluatedSubmissions: evaluated.length,
    pendingReviews: pending.length,
    classAveragePercent: round1(avg),
    needsReviewCount: evaluated.filter((s) => s.needsReview).length,
  };
}

export interface SubjectOverview {
  subject: Subject;
  assessmentCount: number;
  averagePercent: number;
  submissionCount: number;
}

export function getSubjectOverviews(): SubjectOverview[] {
  return SUBJECTS.map((subject) => {
    const assessments = getAssessmentsBySubject(subject.id);
    const submissions = allSubmissions().filter(
      (s) => assessments.some((a) => a.id === s.assessmentId) && s.status === "evaluated",
    );
    const avg =
      submissions.length > 0
        ? submissions.reduce((sum, s) => sum + pct(s.totalScore, s.totalMaxScore), 0) / submissions.length
        : 0;
    return {
      subject,
      assessmentCount: assessments.length,
      averagePercent: round1(avg),
      submissionCount: submissions.length,
    };
  });
}

export function getRecentAssessments(limit = 5): Assessment[] {
  return [...getAssessments()].sort((a, b) => b.date.localeCompare(a.date)).slice(0, limit);
}

export interface PerformerEntry {
  student: Student;
  averagePercent: number;
  evaluatedCount: number;
}

/** Every student ranked by their average % across all evaluated submissions. */
export function getClassPerformers(): PerformerEntry[] {
  return STUDENTS.map((student) => {
    const submissions = getSubmissionsByStudent(student.id).filter((s) => s.status === "evaluated");
    const avg =
      submissions.length > 0
        ? submissions.reduce((sum, s) => sum + pct(s.totalScore, s.totalMaxScore), 0) / submissions.length
        : 0;
    return { student, averagePercent: round1(avg), evaluatedCount: submissions.length };
  }).sort((a, b) => b.averagePercent - a.averagePercent);
}

// ---------------------------------------------------------------------------
// Student dashboard
// ---------------------------------------------------------------------------

export interface StudentOverview {
  student: Student;
  overallPercent: number;
  rank: number;
  totalRankedStudents: number;
  evaluatedCount: number;
  pendingCount: number;
  upcoming: Assessment[];
}

export function getStudentOverview(studentId: string): StudentOverview | undefined {
  const student = getStudentById(studentId);
  if (!student) return undefined;

  const performers = getClassPerformers().filter((p) => p.evaluatedCount > 0);
  const rankIndex = performers.findIndex((p) => p.student.id === studentId);
  const mine = performers.find((p) => p.student.id === studentId);

  const submissions = getSubmissionsByStudent(studentId);
  const pendingCount = submissions.filter((s) => s.status === "pending").length;

  const upcoming = getAssessments().filter(
    (a) => a.status === "draft" && a.subjectId && student.subjectIds.includes(a.subjectId),
  );

  return {
    student,
    overallPercent: mine?.averagePercent ?? 0,
    rank: rankIndex >= 0 ? rankIndex + 1 : performers.length + 1,
    totalRankedStudents: performers.length,
    evaluatedCount: mine?.evaluatedCount ?? 0,
    pendingCount,
    upcoming,
  };
}

export interface SubjectPerformance {
  subject: Subject;
  averagePercent: number;
  assessmentCount: number;
}

export function getStudentSubjectPerformance(studentId: string): SubjectPerformance[] {
  return SUBJECTS.map((subject) => {
    const assessments = getAssessmentsBySubject(subject.id);
    const submissions = assessments
      .map((a) => getSubmission(a.id, studentId))
      .filter((s): s is Submission => !!s && s.status === "evaluated");
    const avg =
      submissions.length > 0
        ? submissions.reduce((sum, s) => sum + pct(s.totalScore, s.totalMaxScore), 0) / submissions.length
        : 0;
    return { subject, averagePercent: round1(avg), assessmentCount: submissions.length };
  }).filter((s) => s.assessmentCount > 0);
}

/** Chronological score history (as %) for a "progress over time" chart. */
export function getStudentProgressSeries(studentId: string) {
  return getSubmissionsByStudent(studentId)
    .filter((s) => s.status === "evaluated")
    .map((s) => ({
      submission: s,
      assessment: getAssessmentById(s.assessmentId)!,
      percent: round1(pct(s.totalScore, s.totalMaxScore)),
    }))
    .sort((a, b) => a.assessment.date.localeCompare(b.assessment.date));
}

// ---------------------------------------------------------------------------
// Learning gaps (Part 13) -- derived per-topic from real question results
// ---------------------------------------------------------------------------

const GAP_THRESHOLDS: { min: number; status: GapStatus }[] = [
  { min: 85, status: "Strong" },
  { min: 70, status: "Moderate" },
  { min: 50, status: "Needs Improvement" },
  { min: 0, status: "Weak" },
];

function statusForPercent(p: number): GapStatus {
  return GAP_THRESHOLDS.find((t) => p >= t.min)!.status;
}

const RECOMMENDATIONS: Record<GapStatus, string> = {
  Strong: "Keep reinforcing with advanced practice problems.",
  Moderate: "Review lecture examples and attempt one extra practice set.",
  "Needs Improvement": "Revisit core definitions and worked examples before the next assessment.",
  Weak: "Schedule a doubt-clearing session with faculty on this topic.",
};

export function getLearningGaps(studentId: string): LearningGapEntry[] {
  const byTopic = new Map<string, { subjectId: string; total: number; max: number }>();

  for (const submission of getSubmissionsByStudent(studentId)) {
    if (submission.status !== "evaluated") continue;
    const assessment = getAssessmentById(submission.assessmentId);
    if (!assessment) continue;
    for (const r of submission.results) {
      const question = getQuestionById(assessment, r.questionId);
      if (!question) continue;
      const entry = byTopic.get(question.topic) ?? { subjectId: assessment.subjectId, total: 0, max: 0 };
      entry.total += r.score;
      entry.max += r.maxScore;
      byTopic.set(question.topic, entry);
    }
  }

  return Array.from(byTopic.entries())
    .map(([topic, { subjectId, total, max }]) => {
      const percent = round1(pct(total, max));
      const status = statusForPercent(percent);
      return { topic, subjectId, performancePercent: percent, status, recommendation: RECOMMENDATIONS[status] };
    })
    .sort((a, b) => a.performancePercent - b.performancePercent);
}

// ---------------------------------------------------------------------------
// CO / PO attainment (Part 15) -- demo illustration, formula is transparent
// ---------------------------------------------------------------------------

export function getCOAttainment(): COAttainment[] {
  return CO_DEFINITIONS.map((def) => {
    const assessments = getAssessmentsBySubject(def.subjectId);
    const submissions = allSubmissions().filter(
      (s) => assessments.some((a) => a.id === s.assessmentId) && s.status === "evaluated",
    );
    const achieved =
      submissions.length > 0
        ? submissions.reduce((sum, s) => sum + pct(s.totalScore, s.totalMaxScore), 0) / submissions.length
        : 0;
    return { ...def, achievedPercent: round1(achieved) };
  });
}

export interface POAttainmentComputed extends POAttainment {
  achievedPercent: number;
}

/** PO% = weighted average of linked COs' achieved%, weighted by correlation strength. */
export function getPOAttainment(): POAttainmentComputed[] {
  const coAttainment = getCOAttainment();
  return PO_DEFINITIONS.map((po) => {
    const links = CO_PO_LINKS.filter((l) => l.poCode === po.code);
    let weightedSum = 0;
    let weightTotal = 0;
    for (const link of links) {
      const co = coAttainment.find((c) => c.code === link.coCode);
      if (!co) continue;
      weightedSum += co.achievedPercent * link.weight;
      weightTotal += link.weight;
    }
    return { ...po, achievedPercent: weightTotal > 0 ? round1(weightedSum / weightTotal) : 0 };
  });
}

export function getCOPOLinks() {
  return CO_PO_LINKS;
}

// ---------------------------------------------------------------------------
// Analytics (Part 14)
// ---------------------------------------------------------------------------

export interface ScoreDistributionBucket {
  label: string;
  count: number;
}

export function getScoreDistribution(subjectId?: string): ScoreDistributionBucket[] {
  const assessments = subjectId ? getAssessmentsBySubject(subjectId) : getAssessments();
  const submissions = allSubmissions().filter(
    (s) => assessments.some((a) => a.id === s.assessmentId) && s.status === "evaluated",
  );
  const buckets = [
    { label: "0–40%", min: 0, max: 40, count: 0 },
    { label: "40–60%", min: 40, max: 60, count: 0 },
    { label: "60–75%", min: 60, max: 75, count: 0 },
    { label: "75–90%", min: 75, max: 90, count: 0 },
    { label: "90–100%", min: 90, max: 101, count: 0 },
  ];
  for (const s of submissions) {
    const p = pct(s.totalScore, s.totalMaxScore);
    const bucket = buckets.find((b) => p >= b.min && p < b.max);
    if (bucket) bucket.count += 1;
  }
  return buckets.map(({ label, count }) => ({ label, count }));
}

export interface QuestionPerformance {
  assessment: Assessment;
  question: Question;
  averagePercent: number;
  responseCount: number;
}

export function getQuestionPerformance(subjectId?: string): QuestionPerformance[] {
  const assessments = subjectId ? getAssessmentsBySubject(subjectId) : getAssessments();
  const rows: QuestionPerformance[] = [];
  for (const assessment of assessments) {
    for (const question of assessment.questions) {
      const scores = getSubmissionsByAssessment(assessment.id)
        .filter((s) => s.status === "evaluated")
        .map((s) => s.results.find((r) => r.questionId === question.id))
        .filter((r): r is NonNullable<typeof r> => !!r);
      if (scores.length === 0) continue;
      const avg = scores.reduce((sum, r) => sum + pct(r.score, r.maxScore), 0) / scores.length;
      rows.push({ assessment, question, averagePercent: round1(avg), responseCount: scores.length });
    }
  }
  return rows.sort((a, b) => a.averagePercent - b.averagePercent);
}
