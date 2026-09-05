"use client";

import { Loader2, Users } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { DemoDataBadge } from "../../components/ui/Badge";
import { ScoreBar } from "../../components/ui/ScoreBar";
import { EmptyState } from "../../components/ui/EmptyState";
import { getClassPerformers } from "../../lib/repository";
import { useClientData } from "../../lib/useClientData";

export default function FacultyStudentsPage() {
  const performers = useClientData(getClassPerformers, []);

  return (
    <AppShell role="faculty" title="Students" subtitle="Roster and overall performance">
      {!performers ? (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </div>
      ) : performers.length === 0 ? (
        <EmptyState icon={Users} title="No students yet" />
      ) : (
        <Card>
          <CardHeader title={`${performers.length} students`} action={<DemoDataBadge />} />
          <CardBody className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-400">
                  <th className="px-6 py-3 font-medium">Student</th>
                  <th className="px-6 py-3 font-medium">Roll No.</th>
                  <th className="px-6 py-3 font-medium">Average</th>
                  <th className="px-6 py-3 font-medium">Evaluated</th>
                </tr>
              </thead>
              <tbody>
                {performers.map((p) => (
                  <tr key={p.student.id} className="border-b border-slate-50 last:border-0">
                    <td className="px-6 py-3 font-medium text-slate-800">{p.student.name}</td>
                    <td className="px-6 py-3 text-slate-500">{p.student.rollNumber}</td>
                    <td className="px-6 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-slate-700">{p.averagePercent}%</span>
                        <ScoreBar percent={p.averagePercent} className="w-24" />
                      </div>
                    </td>
                    <td className="px-6 py-3 text-slate-500">{p.evaluatedCount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardBody>
        </Card>
      )}
    </AppShell>
  );
}
