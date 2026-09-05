"use client";

import Link from "next/link";
import { ClipboardList, Loader2 } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { DemoDataBadge } from "../../components/ui/Badge";
import { ScoreBar } from "../../components/ui/ScoreBar";
import { EmptyState } from "../../components/ui/EmptyState";
import {
  getAssessmentById,
  getStudentOverview,
  getSubjectById,
  getSubmissionsByStudent,
} from "../../lib/repository";
import { useClientData } from "../../lib/useClientData";
import { DEMO_STUDENT_ID } from "../../lib/demoData";

function loadData() {
  const overview = getStudentOverview(DEMO_STUDENT_ID);
  const submissions = getSubmissionsByStudent(DEMO_STUDENT_ID);
  return { overview, submissions };
}

export default function StudentAssessmentsPage() {
  const data = useClientData(loadData, []);

  if (!data || !data.overview) {
    return (
      <AppShell role="student" title="My Assessments">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </div>
      </AppShell>
    );
  }

  const { overview, submissions } = data;

  return (
    <AppShell role="student" title="My Assessments" subtitle="Upcoming, pending and evaluated assessments">
      <Card>
        <CardHeader title="Upcoming" subtitle="Not yet published by faculty" action={<DemoDataBadge />} />
        <CardBody>
          {overview.upcoming.length === 0 ? (
            <p className="text-sm text-slate-400">Nothing scheduled right now.</p>
          ) : (
            <ul className="space-y-2">
              {overview.upcoming.map((a) => (
                <li key={a.id} className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-800">{a.title}</span>
                  <span className="text-slate-500">{a.date}</span>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      <Card className="mt-6">
        <CardHeader title="All assessments" action={<DemoDataBadge />} />
        <CardBody className="p-0">
          {submissions.length === 0 ? (
            <div className="p-6">
              <EmptyState icon={ClipboardList} title="No assessments yet" />
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-400">
                  <th className="px-6 py-3 font-medium">Assessment</th>
                  <th className="px-6 py-3 font-medium">Subject</th>
                  <th className="px-6 py-3 font-medium">Status</th>
                  <th className="px-6 py-3 font-medium">Score</th>
                </tr>
              </thead>
              <tbody>
                {submissions.map((s) => {
                  const assessment = getAssessmentById(s.assessmentId);
                  const subject = assessment ? getSubjectById(assessment.subjectId) : undefined;
                  const percent = s.totalMaxScore > 0 ? Math.round((s.totalScore / s.totalMaxScore) * 100) : 0;
                  return (
                    <tr key={s.id} className="border-b border-slate-50 last:border-0">
                      <td className="px-6 py-3 font-medium text-slate-800">
                        {s.status === "evaluated" ? (
                          <Link href={`/student/results/${s.id}`} className="hover:text-indigo-600 hover:underline">
                            {assessment?.title ?? s.assessmentId}
                          </Link>
                        ) : (
                          assessment?.title ?? s.assessmentId
                        )}
                      </td>
                      <td className="px-6 py-3 text-slate-500">{subject?.code ?? "—"}</td>
                      <td className="px-6 py-3">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                            s.status === "evaluated" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {s.status === "evaluated" ? "Evaluated" : "Pending evaluation"}
                        </span>
                      </td>
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
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>
    </AppShell>
  );
}
