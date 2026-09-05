"use client";

import { Loader2 } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { DemoDataBadge } from "../../components/ui/Badge";
import { ScoreBar } from "../../components/ui/ScoreBar";
import {
  getCOAttainment,
  getCOPOLinks,
  getClassPerformers,
  getPOAttainment,
  getQuestionPerformance,
  getScoreDistribution,
} from "../../lib/repository";
import { useClientData } from "../../lib/useClientData";

function loadAnalytics() {
  const distribution = getScoreDistribution();
  const maxBucket = Math.max(1, ...distribution.map((b) => b.count));
  const questionPerf = getQuestionPerformance();
  const performers = getClassPerformers().filter((p) => p.evaluatedCount > 0);
  const co = getCOAttainment();
  const po = getPOAttainment();
  const links = getCOPOLinks();
  return { distribution, maxBucket, questionPerf, performers, co, po, links };
}

export default function FacultyAnalyticsPage() {
  const data = useClientData(loadAnalytics, []);

  if (!data) {
    return (
      <AppShell role="faculty" title="Analytics">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </div>
      </AppShell>
    );
  }

  const { distribution, maxBucket, questionPerf, performers, co, po, links } = data;
  const weakestQuestions = questionPerf.slice(0, 5);
  const topPerformers = performers.slice(0, 5);
  const lowPerformers = [...performers].reverse().slice(0, 5);

  return (
    <AppShell role="faculty" title="Analytics" subtitle="Class performance, question difficulty, and CO/PO attainment">
      <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        Every figure below is computed from the sample dataset (see the Demo data badges) — none of this is live
        production analytics yet, since there is no persistence layer. The computation itself (averages,
        distributions, CO/PO weighting) is real and will work unchanged once real submissions replace the demo ones.
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Score distribution" subtitle="All evaluated submissions, all subjects" action={<DemoDataBadge />} />
          <CardBody className="space-y-3">
            {distribution.map((b) => (
              <div key={b.label} className="flex items-center gap-3">
                <span className="w-20 shrink-0 text-xs text-slate-500">{b.label}</span>
                <div className="h-3 flex-1 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-indigo-500"
                    style={{ width: `${(b.count / maxBucket) * 100}%` }}
                  />
                </div>
                <span className="w-6 shrink-0 text-right text-xs font-medium text-slate-700">{b.count}</span>
              </div>
            ))}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Weakest questions" subtitle="Lowest average % across submissions" action={<DemoDataBadge />} />
          <CardBody className="space-y-3">
            {weakestQuestions.map((q) => (
              <div key={`${q.assessment.id}-${q.question.id}`}>
                <div className="flex items-baseline justify-between text-sm">
                  <span className="font-medium text-slate-800">
                    {q.assessment.title} · {q.question.id}
                  </span>
                  <span className="text-slate-500">{q.averagePercent}% avg ({q.responseCount} responses)</span>
                </div>
                <p className="mt-0.5 truncate text-xs text-slate-500">{q.question.topic}</p>
                <ScoreBar percent={q.averagePercent} className="mt-1" />
              </div>
            ))}
          </CardBody>
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Top performers" action={<DemoDataBadge />} />
          <CardBody className="space-y-2">
            {topPerformers.map((p) => (
              <div key={p.student.id} className="flex items-center justify-between text-sm">
                <span className="text-slate-700">{p.student.name}</span>
                <span className="font-semibold text-emerald-700">{p.averagePercent}%</span>
              </div>
            ))}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Low performers" action={<DemoDataBadge />} />
          <CardBody className="space-y-2">
            {lowPerformers.map((p) => (
              <div key={p.student.id} className="flex items-center justify-between text-sm">
                <span className="text-slate-700">{p.student.name}</span>
                <span className="font-semibold text-rose-700">{p.averagePercent}%</span>
              </div>
            ))}
          </CardBody>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader
          title="CO attainment"
          subtitle="Average score vs. target, by course outcome"
          action={<DemoDataBadge />}
        />
        <CardBody className="space-y-4">
          {co.map((c) => (
            <div key={c.code}>
              <div className="flex items-baseline justify-between text-sm">
                <span className="font-medium text-slate-800">
                  {c.code} — {c.description}
                </span>
                <span className="text-slate-500">
                  {c.achievedPercent}% achieved / {c.targetPercent}% target
                </span>
              </div>
              <ScoreBar percent={c.achievedPercent} className="mt-2" />
            </div>
          ))}
        </CardBody>
      </Card>

      <Card className="mt-6">
        <CardHeader
          title="PO attainment"
          subtitle="Weighted average of linked COs' achievement — a demo illustration of the OBE surface, not an accreditation-derived formula"
          action={<DemoDataBadge />}
        />
        <CardBody className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {po.map((p) => (
            <div key={p.code} className="rounded-lg border border-slate-200 p-4 text-center">
              <p className="text-2xl font-semibold text-slate-900">{p.achievedPercent}%</p>
              <p className="mt-1 text-xs font-medium text-slate-600">{p.code}</p>
              <p className="text-xs text-slate-400">{p.description}</p>
            </div>
          ))}
        </CardBody>
      </Card>

      <Card className="mt-6">
        <CardHeader
          title="CO → PO correlation matrix"
          subtitle="Illustrative weights (1 = slight, 3 = strong) — not derived from an accreditation-approved framework"
          action={<DemoDataBadge />}
        />
        <CardBody className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase text-slate-400">CO \ PO</th>
                {po.map((p) => (
                  <th key={p.code} className="px-3 py-2 text-center text-xs font-medium uppercase text-slate-400">
                    {p.code}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {co.map((c) => (
                <tr key={c.code} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-medium text-slate-800">{c.code}</td>
                  {po.map((p) => {
                    const link = links.find((l) => l.coCode === c.code && l.poCode === p.code);
                    return (
                      <td key={p.code} className="px-3 py-2 text-center">
                        {link ? (
                          <span
                            className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${
                              link.weight === 3
                                ? "bg-indigo-600 text-white"
                                : link.weight === 2
                                  ? "bg-indigo-200 text-indigo-800"
                                  : "bg-indigo-50 text-indigo-600"
                            }`}
                          >
                            {link.weight}
                          </span>
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </AppShell>
  );
}
