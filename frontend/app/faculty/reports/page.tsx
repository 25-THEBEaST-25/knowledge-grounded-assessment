"use client";

import { FileText, Loader2 } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { DemoDataBadge } from "../../components/ui/Badge";
import { ScoreBar } from "../../components/ui/ScoreBar";
import { EmptyState } from "../../components/ui/EmptyState";
import { getAssessments, getSubjectById, getSubmissionsByAssessment } from "../../lib/repository";
import { useClientData } from "../../lib/useClientData";

function loadReports() {
  return getAssessments()
    .map((assessment) => {
      const submissions = getSubmissionsByAssessment(assessment.id);
      const evaluated = submissions.filter((s) => s.status === "evaluated");
      const avg =
        evaluated.length > 0
          ? evaluated.reduce((sum, s) => sum + (s.totalScore / s.totalMaxScore) * 100, 0) / evaluated.length
          : 0;
      return {
        assessment,
        subject: getSubjectById(assessment.subjectId),
        submitted: submissions.length,
        evaluated: evaluated.length,
        needsReview: evaluated.filter((s) => s.needsReview).length,
        averagePercent: Math.round(avg * 10) / 10,
      };
    })
    .sort((a, b) => b.assessment.date.localeCompare(a.assessment.date));
}

export default function FacultyReportsPage() {
  const reports = useClientData(loadReports, []);

  return (
    <AppShell role="faculty" title="Reports" subtitle="Per-assessment evaluation summary">
      {!reports ? (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </div>
      ) : reports.length === 0 ? (
        <EmptyState icon={FileText} title="No assessments yet" />
      ) : (
        <div className="space-y-4">
          {reports.map((r) => (
            <Card key={r.assessment.id}>
              <CardHeader
                title={r.assessment.title}
                subtitle={`${r.subject?.code ?? ""} ${r.subject?.name ?? ""} · ${r.assessment.date}`}
                action={<DemoDataBadge />}
              />
              <CardBody className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Stat label="Submitted" value={r.submitted} />
                <Stat label="Evaluated" value={r.evaluated} />
                <Stat label="Needs review" value={r.needsReview} />
                <div>
                  <p className="text-xl font-semibold text-slate-900">{r.averagePercent}%</p>
                  <p className="text-xs text-slate-500">Class average</p>
                  <ScoreBar percent={r.averagePercent} className="mt-1" />
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </AppShell>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-xl font-semibold text-slate-900">{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}
