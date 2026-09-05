"use client";

import Link from "next/link";
import { Loader2, Sparkles } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { Badge, DemoDataBadge } from "../../components/ui/Badge";
import { EmptyState } from "../../components/ui/EmptyState";
import { getAssessmentById, getSubmissionsByStudent } from "../../lib/repository";
import { useClientData } from "../../lib/useClientData";
import { DEMO_STUDENT_ID } from "../../lib/demoData";

function loadFeedbackFeed() {
  const submissions = getSubmissionsByStudent(DEMO_STUDENT_ID)
    .filter((s) => s.status === "evaluated")
    .sort((a, b) => (b.evaluatedAt ?? "").localeCompare(a.evaluatedAt ?? ""));

  return submissions.flatMap((s) => {
    const assessment = getAssessmentById(s.assessmentId);
    return s.results
      .filter((r) => r.answerDetected)
      .map((r) => ({
        submissionId: s.id,
        source: s.source,
        assessmentTitle: assessment?.title ?? s.assessmentId,
        questionId: r.questionId,
        feedback: r.feedback,
        strengths: r.strengths,
        missingConcepts: r.missingConcepts,
        score: r.score,
        maxScore: r.maxScore,
      }));
  });
}

export default function AIFeedbackPage() {
  const feed = useClientData(loadFeedbackFeed, []);

  return (
    <AppShell role="student" title="AI Feedback" subtitle="Written feedback from every evaluated question, most recent first">
      {!feed ? (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </div>
      ) : feed.length === 0 ? (
        <EmptyState icon={Sparkles} title="No feedback yet" description="Feedback appears here once your submissions are evaluated." />
      ) : (
        <div className="space-y-4">
          {feed.map((f, i) => (
            <Card key={`${f.submissionId}-${f.questionId}-${i}`}>
              <CardHeader
                title={
                  <Link href={`/student/results/${f.submissionId}`} className="hover:text-indigo-600 hover:underline">
                    {f.assessmentTitle} · {f.questionId}
                  </Link>
                }
                action={
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-slate-800">
                      {f.score}/{f.maxScore}
                    </span>
                    {f.source === "real-evaluation" ? <Badge variant="live">Real evaluation</Badge> : <DemoDataBadge />}
                  </div>
                }
              />
              <CardBody className="space-y-2">
                <p className="text-sm font-medium text-slate-800">{f.feedback}</p>
                {f.strengths.length > 0 && (
                  <p className="text-sm text-slate-700">
                    <span className="font-semibold text-emerald-700">Strengths: </span>
                    {f.strengths.join("; ")}
                  </p>
                )}
                {f.missingConcepts.length > 0 && (
                  <p className="text-sm text-slate-700">
                    <span className="font-semibold text-rose-700">Missing concepts: </span>
                    {f.missingConcepts.join("; ")}
                  </p>
                )}
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </AppShell>
  );
}
