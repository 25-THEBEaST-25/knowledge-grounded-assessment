"use client";

import Link from "next/link";
import { Loader2, Sparkles, Target, TrendingUp, Trophy } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { Card, CardBody, CardHeader } from "../components/ui/Card";
import { StatTile } from "../components/ui/StatTile";
import { DemoDataBadge } from "../components/ui/Badge";
import { ScoreBar } from "../components/ui/ScoreBar";
import { EmptyState } from "../components/ui/EmptyState";
import {
  getAssessmentById,
  getLearningGaps,
  getStudentOverview,
  getStudentProgressSeries,
  getStudentSubjectPerformance,
  getSubmissionsByStudent,
} from "../lib/repository";
import { useClientData } from "../lib/useClientData";
import { DEMO_STUDENT_ID } from "../lib/demoData";

function loadData() {
  const overview = getStudentOverview(DEMO_STUDENT_ID);
  const subjects = getStudentSubjectPerformance(DEMO_STUDENT_ID);
  const progress = getStudentProgressSeries(DEMO_STUDENT_ID);
  const gaps = getLearningGaps(DEMO_STUDENT_ID);
  const recentResults = getSubmissionsByStudent(DEMO_STUDENT_ID)
    .filter((s) => s.status === "evaluated")
    .sort((a, b) => (b.evaluatedAt ?? "").localeCompare(a.evaluatedAt ?? ""))
    .slice(0, 4);
  return { overview, subjects, progress, gaps, recentResults };
}

export default function StudentDashboardPage() {
  const data = useClientData(loadData, []);

  if (!data || !data.overview) {
    return (
      <AppShell role="student" title="Dashboard">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </div>
      </AppShell>
    );
  }

  const { overview, subjects, progress, gaps, recentResults } = data;
  const strongest = [...gaps].sort((a, b) => b.performancePercent - a.performancePercent).slice(0, 3);
  const weakest = gaps.slice(0, 3);

  return (
    <AppShell role="student" title={`Welcome back, ${overview.student.name.split(" ")[0]}`} subtitle="Here's how you're doing across your subjects">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Overall performance"
          value={`${overview.overallPercent}%`}
          icon={TrendingUp}
          tone="indigo"
          badge={<DemoDataBadge />}
        />
        <StatTile
          label="Class rank"
          value={`#${overview.rank} of ${overview.totalRankedStudents}`}
          icon={Trophy}
          tone="emerald"
          badge={<DemoDataBadge />}
        />
        <StatTile label="Evaluations received" value={overview.evaluatedCount} icon={Sparkles} tone="indigo" badge={<DemoDataBadge />} />
        <StatTile label="Pending review" value={overview.pendingCount} icon={Target} tone="amber" badge={<DemoDataBadge />} />
      </div>

      <Card className="mt-6">
        <CardHeader title="Subjects" action={<DemoDataBadge />} />
        <CardBody>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {subjects.map(({ subject, averagePercent, assessmentCount }) => (
              <div key={subject.id} className="rounded-lg border border-slate-200 p-4">
                <p className="text-sm font-semibold text-slate-800">{subject.name}</p>
                <p className="text-xs text-slate-500">{subject.code}</p>
                <div className="mt-3 flex items-baseline justify-between text-sm">
                  <span className="font-semibold text-slate-900">{averagePercent}%</span>
                  <span className="text-slate-500">{assessmentCount} evaluated</span>
                </div>
                <ScoreBar percent={averagePercent} className="mt-2" />
              </div>
            ))}
          </div>
        </CardBody>
      </Card>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Recent results" action={<DemoDataBadge />} />
          <CardBody className="p-0">
            {recentResults.length === 0 ? (
              <div className="p-6">
                <EmptyState icon={Sparkles} title="No results yet" description="Results will appear here once your faculty evaluates a submission." />
              </div>
            ) : (
              <table className="w-full text-sm">
                <tbody>
                  {recentResults.map((r) => {
                    const assessment = getAssessmentById(r.assessmentId);
                    const percent = r.totalMaxScore > 0 ? Math.round((r.totalScore / r.totalMaxScore) * 100) : 0;
                    return (
                      <tr key={r.id} className="border-b border-slate-50 last:border-0">
                        <td className="px-6 py-3 font-medium text-slate-800">
                          <Link href={`/student/results/${r.id}`} className="hover:text-indigo-600 hover:underline">
                            {assessment?.title ?? r.assessmentId}
                          </Link>
                        </td>
                        <td className="px-6 py-3">
                          <div className="flex items-center gap-2">
                            <span className="text-slate-700">
                              {r.totalScore}/{r.totalMaxScore}
                            </span>
                            <ScoreBar percent={percent} className="w-24" />
                          </div>
                        </td>
                        <td className="px-6 py-3 text-right">
                          <Link href={`/student/results/${r.id}`} className="text-xs font-medium text-indigo-600 hover:underline">
                            View details →
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Progress over time" action={<DemoDataBadge />} />
          <CardBody className="space-y-3">
            {progress.length === 0 ? (
              <p className="text-sm text-slate-400">No evaluated assessments yet.</p>
            ) : (
              progress.map((p) => (
                <div key={p.submission.id}>
                  <div className="flex items-baseline justify-between text-xs">
                    <span className="text-slate-600">{p.assessment.title}</span>
                    <span className="font-medium text-slate-800">{p.percent}%</span>
                  </div>
                  <ScoreBar percent={p.percent} className="mt-1" />
                </div>
              ))
            )}
          </CardBody>
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Strong concepts" action={<DemoDataBadge />} />
          <CardBody className="space-y-2">
            {strongest.map((g) => (
              <div key={g.topic} className="flex items-center justify-between text-sm">
                <span className="text-slate-700">{g.topic}</span>
                <span className="font-semibold text-emerald-700">{g.performancePercent}%</span>
              </div>
            ))}
          </CardBody>
        </Card>
        <Card>
          <CardHeader
            title="Weak concepts"
            subtitle="See Learning Gaps for full recommendations"
            action={<DemoDataBadge />}
          />
          <CardBody className="space-y-2">
            {weakest.map((g) => (
              <div key={g.topic} className="flex items-center justify-between text-sm">
                <span className="text-slate-700">{g.topic}</span>
                <span className="font-semibold text-rose-700">{g.performancePercent}%</span>
              </div>
            ))}
          </CardBody>
        </Card>
      </div>

      {overview.upcoming.length > 0 && (
        <Card className="mt-6">
          <CardHeader title="Upcoming assessments" action={<DemoDataBadge />} />
          <CardBody className="space-y-2">
            {overview.upcoming.map((a) => (
              <div key={a.id} className="flex items-center justify-between text-sm">
                <span className="text-slate-700">{a.title}</span>
                <span className="text-slate-500">{a.date}</span>
              </div>
            ))}
          </CardBody>
        </Card>
      )}
    </AppShell>
  );
}
