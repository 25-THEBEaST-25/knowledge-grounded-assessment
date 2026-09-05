"use client";

import { Loader2 } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { DemoDataBadge } from "../../components/ui/Badge";
import { getStudentById, getStudentOverview, getSubjects } from "../../lib/repository";
import { useClientData } from "../../lib/useClientData";
import { DEMO_STUDENT_ID } from "../../lib/demoData";

export default function StudentProfilePage() {
  const data = useClientData(
    () => ({ student: getStudentById(DEMO_STUDENT_ID), overview: getStudentOverview(DEMO_STUDENT_ID) }),
    [],
  );

  if (!data?.student) {
    return (
      <AppShell role="student" title="Profile">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </div>
      </AppShell>
    );
  }

  const { student, overview } = data;
  const subjects = getSubjects().filter((s) => student.subjectIds.includes(s.id));

  return (
    <AppShell role="student" title="Profile">
      <Card>
        <CardBody className="flex items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-indigo-100 text-xl font-semibold text-indigo-700">
            {student.name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
          </div>
          <div>
            <p className="text-lg font-semibold text-slate-900">{student.name}</p>
            <p className="text-sm text-slate-500">Roll No. {student.rollNumber}</p>
          </div>
        </CardBody>
      </Card>

      <Card className="mt-6">
        <CardHeader title="Enrolled subjects" action={<DemoDataBadge />} />
        <CardBody>
          <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {subjects.map((s) => (
              <li key={s.id} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">
                <span className="font-medium text-slate-800">{s.code}</span>{" "}
                <span className="text-slate-500">{s.name}</span>
              </li>
            ))}
          </ul>
        </CardBody>
      </Card>

      {overview && (
        <Card className="mt-6">
          <CardHeader title="Summary" action={<DemoDataBadge />} />
          <CardBody className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Overall %" value={`${overview.overallPercent}%`} />
            <Stat label="Class rank" value={`#${overview.rank}`} />
            <Stat label="Evaluated" value={overview.evaluatedCount} />
            <Stat label="Pending" value={overview.pendingCount} />
          </CardBody>
        </Card>
      )}

      <div className="mt-6 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-xs text-sky-800">
        There is no login system yet — this is a fixed demo student identity. Account management is on the Roadmap.
      </div>
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
