"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, FileUp, Loader2, Search } from "lucide-react";
import { AppShell } from "../../../components/AppShell";
import { Card, CardBody, CardHeader } from "../../../components/ui/Card";
import { DemoDataBadge, LocalOnlyBadge } from "../../../components/ui/Badge";
import { ScoreBar } from "../../../components/ui/ScoreBar";
import { EmptyState } from "../../../components/ui/EmptyState";
import {
  getAssessmentById,
  getStudentById,
  getStudents,
  getSubjectById,
  getSubmissionsByAssessment,
} from "../../../lib/repository";
import { saveLocalAssessment, saveLocalSubmission } from "../../../lib/localAssessments";
import { useClientData } from "../../../lib/useClientData";
import { ApiError, evaluateHandwrittenAnswerSheet, questionToPayload } from "../../../lib/api";
import type { Assessment, QuestionResult, Submission } from "../../../lib/domain";

export function AssessmentDetailClient({ assessmentId }: { assessmentId: string }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const assessment = useClientData(() => getAssessmentById(assessmentId) ?? null, [assessmentId, refreshKey]);

  if (assessment === undefined) {
    return (
      <AppShell role="faculty" title="Assessment">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </div>
      </AppShell>
    );
  }

  if (!assessment) {
    return (
      <AppShell role="faculty" title="Assessment not found">
        <EmptyState
          icon={Search}
          title="This assessment doesn't exist"
          description="It may have been created on a different device (local assessments aren't shared across browsers yet)."
          action={
            <Link href="/faculty/assessments" className="text-sm font-medium text-indigo-600 hover:underline">
              Back to assessments
            </Link>
          }
        />
      </AppShell>
    );
  }

  const subject = getSubjectById(assessment.subjectId);
  const submissions = getSubmissionsByAssessment(assessment.id);

  const publish = () => {
    if (assessment.source !== "local") return;
    saveLocalAssessment({ ...assessment, status: "published" });
    setRefreshKey((k) => k + 1);
  };

  return (
    <AppShell
      role="faculty"
      title={assessment.title}
      subtitle={`${subject?.code ?? ""} ${subject?.name ?? ""} · ${assessment.date} · ${assessment.totalMarks} marks`}
      action={
        <Link href="/faculty/assessments" className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700">
          <ArrowLeft size={15} /> All assessments
        </Link>
      }
    >
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-medium ${
            assessment.status === "published" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"
          }`}
        >
          {assessment.status === "published" ? "Published to students" : "Draft — not visible to students"}
        </span>
        {assessment.source === "local" ? <LocalOnlyBadge /> : <DemoDataBadge />}
        {assessment.source === "local" && assessment.status === "draft" && (
          <button
            onClick={publish}
            className="ml-auto flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700"
          >
            <CheckCircle2 size={14} /> Publish to students
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Questions & rubric" />
          <CardBody className="space-y-4">
            {assessment.questions.map((q) => (
              <div key={q.id} className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-baseline justify-between">
                  <span className="text-sm font-semibold text-slate-800">{q.id}</span>
                  <span className="text-xs text-slate-500">{q.maxScore} marks</span>
                </div>
                <p className="mt-1 text-sm text-slate-700">{q.text}</p>
                <p className="mt-2 text-xs text-slate-500">
                  <span className="font-medium">Model answer:</span> {q.modelAnswer}
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {q.criteria.map((c) => (
                    <span key={c.name} className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
                      {c.name}: {c.maxScore}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </CardBody>
        </Card>

        <EvaluatePanel
          assessment={assessment}
          onEvaluated={() => setRefreshKey((k) => k + 1)}
        />
      </div>

      <Card className="mt-6">
        <CardHeader title="Submissions" subtitle={`${submissions.length} of ${getStudents().length} students`} />
        <CardBody className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-400">
                <th className="px-6 py-3 font-medium">Student</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium">Score</th>
                <th className="px-6 py-3 font-medium">Confidence</th>
                <th className="px-6 py-3 font-medium">Review</th>
                <th className="px-6 py-3 font-medium">Source</th>
              </tr>
            </thead>
            <tbody>
              {submissions.map((s) => {
                const student = getStudentById(s.studentId);
                const percent = s.totalMaxScore > 0 ? Math.round((s.totalScore / s.totalMaxScore) * 100) : 0;
                return (
                  <tr key={s.id} className="border-b border-slate-50 last:border-0">
                    <td className="px-6 py-3 font-medium text-slate-800">{student?.name ?? s.studentId}</td>
                    <td className="px-6 py-3 text-slate-500">{s.status}</td>
                    <td className="px-6 py-3">
                      {s.status === "evaluated" ? (
                        <div className="flex items-center gap-2">
                          <span className="text-slate-700">
                            {s.totalScore}/{s.totalMaxScore}
                          </span>
                          <ScoreBar percent={percent} className="w-20" />
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-6 py-3 text-slate-500">
                      {s.status === "evaluated" ? `${Math.round(s.overallConfidence * 100)}%` : "—"}
                    </td>
                    <td className="px-6 py-3">
                      {s.needsReview && (
                        <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800">
                          needs review
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-3">
                      {s.source === "real-evaluation" ? (
                        <span className="text-xs font-medium text-emerald-700">Real evaluation</span>
                      ) : s.source === "local" ? (
                        <LocalOnlyBadge />
                      ) : (
                        <DemoDataBadge />
                      )}
                    </td>
                  </tr>
                );
              })}
              {submissions.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-sm text-slate-400">
                    No submissions yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </AppShell>
  );
}

function EvaluatePanel({ assessment, onEvaluated }: { assessment: Assessment; onEvaluated: () => void }) {
  const students = getStudents();
  const [studentId, setStudentId] = useState(students[0]?.id ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<Submission | null>(null);

  const run = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const payload = assessment.questions.map((q) => questionToPayload(q));
      const res = await evaluateHandwrittenAnswerSheet(file, payload);

      const results: QuestionResult[] = res.results.map((r) => ({
        questionId: r.question_id,
        score: r.score,
        maxScore: r.max_score,
        conceptScore: r.concept_score,
        accuracyScore: r.accuracy_score,
        precisionScore: r.precision_score,
        technicalTerminologyScore: r.technical_terminology_score,
        strengths: r.strengths,
        missingConcepts: r.missing_concepts,
        feedback: r.feedback,
        confidence: r.confidence,
        ocrConfidence: r.ocr_confidence,
        combinedConfidence: r.combined_confidence,
        needsReview: r.needs_review,
        answerDetected: r.answer_detected,
        studentAnswer: r.student_answer,
      }));

      const submission: Submission = {
        id: `real-${Date.now()}`,
        assessmentId: assessment.id,
        studentId,
        status: "evaluated",
        results,
        totalScore: res.total_score,
        totalMaxScore: res.total_max_score,
        overallConfidence: res.overall_confidence,
        needsReview: res.needs_review,
        evaluatedAt: new Date().toISOString(),
        source: "real-evaluation",
      };
      saveLocalSubmission(submission);
      setLastResult(submission);
      setFile(null);
      onEvaluated();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Evaluation failed. Please try again later.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader
        title="Upload & evaluate answer sheet"
        subtitle="Real backend call: PaddleOCR → segmentation → Gemini evaluation"
      />
      <CardBody className="space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">Student</span>
          <select
            value={studentId}
            onChange={(e) => setStudentId(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            {students.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.rollNumber})
              </option>
            ))}
          </select>
        </label>

        <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border-2 border-dashed border-slate-300 px-4 py-6 text-sm text-slate-600 hover:border-indigo-300 hover:bg-indigo-50/40">
          <FileUp size={16} />
          {file ? file.name : "+ Add Answer Sheet Image"}
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>

        <button
          disabled={!file || loading}
          onClick={run}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : null}
          {loading ? "Evaluating…" : "Evaluate"}
        </button>

        {error && <p className="text-sm text-rose-600">{error}</p>}

        {lastResult && (
          <div className="rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            Evaluated: {lastResult.totalScore}/{lastResult.totalMaxScore} for{" "}
            {getStudentById(lastResult.studentId)?.name}. See the submissions table below, or the student&apos;s
            Result Detail page.
          </div>
        )}

        <p className="text-xs text-slate-500">
          This calls the real <code className="rounded bg-slate-100 px-1 py-0.5">/handwritten/evaluate</code> backend
          endpoint. It requires the backend to be running and a valid <code>GEMINI_API_KEY</code> configured
          server-side — if either is missing you&apos;ll see an error here, not a fabricated result.
        </p>
      </CardBody>
    </Card>
  );
}
