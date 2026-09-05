"use client";

import Link from "next/link";
import {
  BookOpen,
  ClipboardCheck,
  ClipboardList,
  Loader2,
  ScanText,
  TrendingUp,
  Users,
} from "lucide-react";
import { AppShell } from "../components/AppShell";
import { Card, CardBody, CardHeader } from "../components/ui/Card";
import { StatTile } from "../components/ui/StatTile";
import { DemoDataBadge, LocalOnlyBadge } from "../components/ui/Badge";
import { ScoreBar } from "../components/ui/ScoreBar";
import { BackendStatus } from "../components/BackendStatus";
import {
  getAssessments,
  getCOAttainment,
  getClassPerformers,
  getFacultyOverview,
  getRecentAssessments,
  getSubjectOverviews,
} from "../lib/repository";
import { useClientData } from "../lib/useClientData";

function loadDashboardData() {
  const performers = getClassPerformers().filter((p) => p.evaluatedCount > 0);
  return {
    overview: getFacultyOverview(),
    subjectOverviews: getSubjectOverviews(),
    topPerformers: performers.slice(0, 3),
    needsAttention: [...performers].reverse().slice(0, 3),
    recentAssessments: getRecentAssessments(5),
    coAttainment: getCOAttainment(),
    localAssessmentCount: getAssessments().filter((a) => a.source === "local").length,
  };
}

export default function FacultyDashboardPage() {
  const data = useClientData(loadDashboardData, []);

  if (!data) {
    return (
      <AppShell role="faculty" title="Faculty Dashboard" subtitle="Teaching overview and assessment activity">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading dashboard…
        </div>
      </AppShell>
    );
  }

  const {
    overview,
    subjectOverviews,
    topPerformers,
    needsAttention,
    recentAssessments,
    coAttainment,
    localAssessmentCount,
  } = data;

  return (
    <AppShell
      role="faculty"
      title="Faculty Dashboard"
      subtitle="Teaching overview and assessment activity"
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatTile label="Total students" value={overview.totalStudents} icon={Users} tone="indigo" />
        <StatTile
          label="Assessments"
          value={overview.totalAssessments}
          icon={ClipboardList}
          tone="indigo"
          hint={localAssessmentCount > 0 ? `${localAssessmentCount} created this session` : undefined}
        />
        <StatTile
          label="Class average"
          value={`${overview.classAveragePercent}%`}
          icon={TrendingUp}
          tone="emerald"
          badge={<DemoDataBadge />}
        />
        <StatTile
          label="Evaluations completed"
          value={overview.evaluatedSubmissions}
          icon={ClipboardCheck}
          tone="emerald"
          badge={<DemoDataBadge />}
        />
        <StatTile
          label="Pending reviews"
          value={overview.pendingReviews}
          icon={BookOpen}
          tone="amber"
          badge={<DemoDataBadge />}
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Subject overview"
            subtitle="Average score and assessment count per subject"
            action={<DemoDataBadge />}
          />
          <CardBody className="space-y-4">
            {subjectOverviews.map(({ subject, averagePercent, assessmentCount, submissionCount }) => (
              <div key={subject.id}>
                <div className="flex items-baseline justify-between text-sm">
                  <span className="font-medium text-slate-800">
                    {subject.code} · {subject.name}
                  </span>
                  <span className="text-slate-500">
                    {submissionCount > 0 ? `${averagePercent}% avg` : "No evaluations yet"} ·{" "}
                    {assessmentCount} assessment{assessmentCount === 1 ? "" : "s"}
                  </span>
                </div>
                <ScoreBar percent={averagePercent} className="mt-2" />
              </div>
            ))}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="System status" subtitle="What's actually live right now" />
          <CardBody className="space-y-4">
            <BackendStatus />
            <div className="space-y-2 text-sm text-slate-600">
              <p className="flex items-center gap-2">
                <ScanText size={14} className="text-indigo-500" />
                Handwritten evaluation pipeline (OCR → segmentation → Gemini) is real.
              </p>
              <p className="text-xs text-slate-500">
                AI evaluation additionally requires <code className="rounded bg-slate-100 px-1 py-0.5">GEMINI_API_KEY</code> to
                be configured on the backend.
              </p>
            </div>
            <Link
              href="/faculty/evaluate"
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Open Answer Evaluation
            </Link>
            <Link href="/roadmap" className="block text-center text-xs text-slate-500 underline">
              See full implemented vs. planned status
            </Link>
          </CardBody>
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Recent assessments" action={<DemoDataBadge />} />
          <CardBody className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-400">
                  <th className="px-6 py-3 font-medium">Title</th>
                  <th className="px-6 py-3 font-medium">Date</th>
                  <th className="px-6 py-3 font-medium">Marks</th>
                  <th className="px-6 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {recentAssessments.map((a) => (
                  <tr key={a.id} className="border-b border-slate-50 last:border-0">
                    <td className="px-6 py-3 font-medium text-slate-800">
                      <Link href={`/faculty/assessments/${a.id}`} className="hover:text-indigo-600 hover:underline">
                        {a.title}
                      </Link>
                    </td>
                    <td className="px-6 py-3 text-slate-500">{a.date}</td>
                    <td className="px-6 py-3 text-slate-500">{a.totalMarks}</td>
                    <td className="px-6 py-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          a.status === "published"
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {a.status}
                      </span>
                      {a.source === "local" && <LocalOnlyBadge className="ml-2" />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Student performance" action={<DemoDataBadge />} />
          <CardBody className="space-y-5">
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-emerald-600">
                Top performers
              </p>
              <ul className="space-y-2">
                {topPerformers.map((p) => (
                  <li key={p.student.id} className="flex items-center justify-between text-sm">
                    <span className="text-slate-700">{p.student.name}</span>
                    <span className="font-semibold text-slate-900">{p.averagePercent}%</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-rose-600">
                Needs attention
              </p>
              <ul className="space-y-2">
                {needsAttention.map((p) => (
                  <li key={p.student.id} className="flex items-center justify-between text-sm">
                    <span className="text-slate-700">{p.student.name}</span>
                    <span className="font-semibold text-slate-900">{p.averagePercent}%</span>
                  </li>
                ))}
              </ul>
            </div>
          </CardBody>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader
          title="CO attainment"
          subtitle="Average score vs. target, per course outcome"
          action={
            <div className="flex items-center gap-2">
              <DemoDataBadge />
              <Link href="/faculty/analytics" className="text-xs font-medium text-indigo-600 hover:underline">
                Full CO/PO view →
              </Link>
            </div>
          }
        />
        <CardBody>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {coAttainment.map((co) => (
              <div key={co.code}>
                <div className="flex items-baseline justify-between text-sm">
                  <span className="font-semibold text-slate-800">{co.code}</span>
                  <span className="text-slate-500">
                    {co.achievedPercent}% / {co.targetPercent}%
                  </span>
                </div>
                <ScoreBar percent={co.achievedPercent} className="mt-2" />
              </div>
            ))}
          </div>
        </CardBody>
      </Card>
    </AppShell>
  );
}
