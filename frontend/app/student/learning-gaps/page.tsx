"use client";

import { Loader2, Target } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { DemoDataBadge } from "../../components/ui/Badge";
import { ScoreBar } from "../../components/ui/ScoreBar";
import { EmptyState } from "../../components/ui/EmptyState";
import { getLearningGaps, getSubjectById } from "../../lib/repository";
import { useClientData } from "../../lib/useClientData";
import { DEMO_STUDENT_ID } from "../../lib/demoData";
import type { GapStatus } from "../../lib/domain";

const STATUS_STYLES: Record<GapStatus, string> = {
  Strong: "bg-emerald-50 text-emerald-700",
  Moderate: "bg-sky-50 text-sky-700",
  "Needs Improvement": "bg-amber-50 text-amber-800",
  Weak: "bg-rose-50 text-rose-700",
};

export default function LearningGapsPage() {
  const gaps = useClientData(() => getLearningGaps(DEMO_STUDENT_ID), []);

  return (
    <AppShell
      role="student"
      title="Learning Gaps"
      subtitle="Topic-level performance, computed from your evaluated question results"
    >
      <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        This view is derived from the sample dataset for this demo (see the Demo data badges below), not a live
        automated concept-tagging system. The underlying data model — per-question topic tags, scored results — is
        real; automatic topic inference from a live curriculum is on the Roadmap.
      </div>

      {!gaps ? (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </div>
      ) : gaps.length === 0 ? (
        <EmptyState icon={Target} title="No data yet" description="Learning gaps appear once you have evaluated results." />
      ) : (
        <Card>
          <CardHeader title="Topic performance" action={<DemoDataBadge />} />
          <CardBody className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-400">
                  <th className="px-6 py-3 font-medium">Topic</th>
                  <th className="px-6 py-3 font-medium">Subject</th>
                  <th className="px-6 py-3 font-medium">Performance</th>
                  <th className="px-6 py-3 font-medium">Status</th>
                  <th className="px-6 py-3 font-medium">Recommendation</th>
                </tr>
              </thead>
              <tbody>
                {gaps.map((g) => (
                  <tr key={g.topic} className="border-b border-slate-50 last:border-0">
                    <td className="px-6 py-3 font-medium text-slate-800">{g.topic}</td>
                    <td className="px-6 py-3 text-slate-500">{getSubjectById(g.subjectId)?.code ?? "—"}</td>
                    <td className="px-6 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-slate-700">{g.performancePercent}%</span>
                        <ScoreBar percent={g.performancePercent} className="w-24" />
                      </div>
                    </td>
                    <td className="px-6 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[g.status]}`}>
                        {g.status}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-slate-600">{g.recommendation}</td>
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
