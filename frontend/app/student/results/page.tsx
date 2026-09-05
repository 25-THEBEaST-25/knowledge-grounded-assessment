"use client";

import Link from "next/link";
import { Loader2 } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { DemoDataBadge, Badge } from "../../components/ui/Badge";
import { ScoreBar } from "../../components/ui/ScoreBar";
import { EmptyState } from "../../components/ui/EmptyState";
import { getAssessmentById, getSubjectById, getSubmissionsByStudent } from "../../lib/repository";
import { useClientData } from "../../lib/useClientData";
import { DEMO_STUDENT_ID } from "../../lib/demoData";
import { BookOpen } from "lucide-react";

export default function StudentResultsPage() {
  const submissions = useClientData(
    () =>
      getSubmissionsByStudent(DEMO_STUDENT_ID)
        .filter((s) => s.status === "evaluated")
        .sort((a, b) => (b.evaluatedAt ?? "").localeCompare(a.evaluatedAt ?? "")),
    [],
  );

  return (
    <AppShell role="student" title="My Results" subtitle="Every evaluated assessment, with a link to the full breakdown">
      {!submissions ? (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </div>
      ) : submissions.length === 0 ? (
        <EmptyState icon={BookOpen} title="No results yet" description="Your evaluated assessments will appear here." />
      ) : (
        <Card>
          <CardHeader title={`${submissions.length} result${submissions.length === 1 ? "" : "s"}`} action={<DemoDataBadge />} />
          <CardBody className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-400">
                  <th className="px-6 py-3 font-medium">Assessment</th>
                  <th className="px-6 py-3 font-medium">Subject</th>
                  <th className="px-6 py-3 font-medium">Score</th>
                  <th className="px-6 py-3 font-medium">Confidence</th>
                  <th className="px-6 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {submissions.map((s) => {
                  const assessment = getAssessmentById(s.assessmentId);
                  const subject = assessment ? getSubjectById(assessment.subjectId) : undefined;
                  const percent = s.totalMaxScore > 0 ? Math.round((s.totalScore / s.totalMaxScore) * 100) : 0;
                  return (
                    <tr key={s.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50/60">
                      <td className="px-6 py-3 font-medium text-slate-800">
                        <Link href={`/student/results/${s.id}`} className="hover:text-indigo-600 hover:underline">
                          {assessment?.title ?? s.assessmentId}
                        </Link>
                      </td>
                      <td className="px-6 py-3 text-slate-500">{subject?.code ?? "—"}</td>
                      <td className="px-6 py-3">
                        <div className="flex items-center gap-2">
                          <span className="text-slate-700">
                            {s.totalScore}/{s.totalMaxScore}
                          </span>
                          <ScoreBar percent={percent} className="w-20" />
                        </div>
                      </td>
                      <td className="px-6 py-3 text-slate-500">{Math.round(s.overallConfidence * 100)}%</td>
                      <td className="px-6 py-3">
                        {s.source === "real-evaluation" ? (
                          <Badge variant="live">Real evaluation</Badge>
                        ) : (
                          <DemoDataBadge />
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardBody>
        </Card>
      )}
    </AppShell>
  );
}
