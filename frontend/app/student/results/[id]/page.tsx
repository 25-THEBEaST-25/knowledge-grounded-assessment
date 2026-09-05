"use client";

import { use } from "react";
import Link from "next/link";
import { ArrowLeft, Loader2, Search } from "lucide-react";
import { AppShell } from "../../../components/AppShell";
import { Card, CardBody, CardHeader } from "../../../components/ui/Card";
import { Badge, DemoDataBadge } from "../../../components/ui/Badge";
import { ScoreBar } from "../../../components/ui/ScoreBar";
import { EmptyState } from "../../../components/ui/EmptyState";
import { getAssessmentById, getQuestionById, getSubmissionById } from "../../../lib/repository";
import { useClientData } from "../../../lib/useClientData";

export default function StudentResultDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const submission = useClientData(() => getSubmissionById(id) ?? null, [id]);

  if (submission === undefined) {
    return (
      <AppShell role="student" title="Result">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </div>
      </AppShell>
    );
  }

  if (!submission) {
    return (
      <AppShell role="student" title="Result not found">
        <EmptyState
          icon={Search}
          title="This result doesn't exist"
          action={
            <Link href="/student/results" className="text-sm font-medium text-indigo-600 hover:underline">
              Back to My Results
            </Link>
          }
        />
      </AppShell>
    );
  }

  const assessment = getAssessmentById(submission.assessmentId);
  const percent = submission.totalMaxScore > 0 ? Math.round((submission.totalScore / submission.totalMaxScore) * 100) : 0;

  const strong = submission.results.filter((r) => r.maxScore > 0 && r.score / r.maxScore >= 0.75);
  const weak = submission.results.filter((r) => r.maxScore > 0 && r.score / r.maxScore < 0.5);
  const sortedByScore = [...submission.results].sort((a, b) => a.score / a.maxScore - b.score / b.maxScore);
  const lowest = sortedByScore[0];
  // Only treat the lowest-scoring question as an "improvement target" if it
  // actually fell short of full marks -- a tie at 100% is not a weak area.
  const improvementTarget = lowest && lowest.maxScore > 0 && lowest.score / lowest.maxScore < 1 ? lowest : undefined;

  return (
    <AppShell
      role="student"
      title={assessment?.title ?? submission.assessmentId}
      subtitle={submission.evaluatedAt ? `Evaluated ${submission.evaluatedAt.slice(0, 10)}` : undefined}
      action={
        <Link href="/student/results" className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700">
          <ArrowLeft size={15} /> All results
        </Link>
      }
    >
      <Card>
        <CardBody className="flex flex-wrap items-center gap-4">
          <span className="text-4xl font-bold text-slate-900">
            {submission.totalScore} / {submission.totalMaxScore}
          </span>
          <ScoreBar percent={percent} className="w-40" />
          <span className="text-sm text-slate-500">Confidence {Math.round(submission.overallConfidence * 100)}%</span>
          {submission.needsReview && <Badge variant="review">Needs review</Badge>}
          {submission.source === "real-evaluation" ? <Badge variant="live">Real evaluation</Badge> : <DemoDataBadge />}
        </CardBody>
      </Card>

      <div className="mt-6 space-y-4">
        {submission.results.map((r) => {
          const question = assessment ? getQuestionById(assessment, r.questionId) : undefined;
          const qPercent = r.maxScore > 0 ? Math.round((r.score / r.maxScore) * 100) : 0;
          return (
            <Card key={r.questionId}>
              <CardHeader
                title={
                  <span>
                    {r.questionId}
                    {question ? ` — ${question.text}` : ""}
                  </span>
                }
                action={
                  <span className="text-lg font-bold text-slate-900">
                    {r.score} / {r.maxScore}
                  </span>
                }
              />
              <CardBody className="space-y-4">
                <ScoreBar percent={qPercent} />

                {r.answerDetected ? (
                  <div>
                    <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Your answer</p>
                    <pre className="whitespace-pre-wrap rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-relaxed text-slate-800">
                      {r.studentAnswer}
                    </pre>
                  </div>
                ) : (
                  <p className="text-sm italic text-slate-400">No answer was detected for this question.</p>
                )}

                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Evaluation</p>
                  <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                    <SubScore label="Conceptual Understanding" value={r.conceptScore} />
                    <SubScore label="Accuracy" value={r.accuracyScore} />
                    <SubScore label="Precision" value={r.precisionScore} />
                    <SubScore label="Technical Terminology" value={r.technicalTerminologyScore} />
                  </div>
                </div>

                {r.strengths.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-emerald-600">Strengths</p>
                    <p className="mt-1 text-sm text-slate-700">{r.strengths.join("; ")}</p>
                  </div>
                )}
                {r.missingConcepts.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-rose-600">Missing Concepts</p>
                    <p className="mt-1 text-sm text-slate-700">{r.missingConcepts.join("; ")}</p>
                  </div>
                )}
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">AI Feedback</p>
                  <p className="mt-1 text-sm font-medium text-slate-800">{r.feedback}</p>
                </div>
              </CardBody>
            </Card>
          );
        })}
      </div>

      <Card className="mt-6">
        <CardHeader title="Summary" />
        <CardBody className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-emerald-600">Strong areas</p>
            <p className="mt-1 text-sm text-slate-700">
              {strong.length > 0 ? strong.map((r) => r.questionId).join(", ") : "None yet at this level — keep practicing."}
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-rose-600">Weak areas</p>
            <p className="mt-1 text-sm text-slate-700">
              {weak.length > 0 ? weak.map((r) => r.questionId).join(", ") : "No weak areas below 50% on this assessment."}
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">Recommended improvement</p>
            <p className="mt-1 text-sm text-slate-700">
              {improvementTarget
                ? (improvementTarget.missingConcepts[0] ??
                  `Review ${improvementTarget.questionId} — it scored lowest on this assessment.`)
                : "Full marks on every question — no specific improvement needed here."}
            </p>
          </div>
        </CardBody>
      </Card>
    </AppShell>
  );
}

function SubScore({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2 text-center">
      <p className="font-semibold text-slate-800">{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}
