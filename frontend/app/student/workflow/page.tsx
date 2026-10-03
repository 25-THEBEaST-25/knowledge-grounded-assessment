"use client";

import { useCallback, useEffect, useState } from "react";
import { BookOpen, Loader2 } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { ConnectionBar } from "../../components/ConnectionBar";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { LiveBadge } from "../../components/ui/Badge";
import { wf, type StudentResult } from "../../lib/workflowApi";

export default function StudentLiveResults() {
  const [rows, setRows] = useState<StudentResult[] | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(async () => {
    try { setRows(await wf.myResults()); setErr(""); } catch (e) { setRows([]); setErr(e instanceof Error ? e.message : "Failed"); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return (
    <AppShell role="student" title="My results (live)" subtitle="Only marks your faculty has reviewed and published appear here.">
      <ConnectionBar role="student" onChange={load} />
      {err && <p className="mb-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{err}</p>}
      {rows === null ? <Loader2 className="animate-spin text-slate-400" /> : rows.length === 0 ? (
        <EmptyState icon={BookOpen} title="No published results yet" description="AI-proposed marks are never shown until faculty finalise them." />
      ) : rows.map((r) => (
        <Card key={r.assessment} className="mb-4">
          <CardHeader title={r.assessment} subtitle={`Final: ${r.final_total}/${r.max_total}`} action={<LiveBadge />} />
          <CardBody>
            <ul className="divide-y divide-slate-100 text-sm">{r.questions.map((q) => (
              <li key={q.subquestion} className="py-2"><b>{q.subquestion}</b> — {q.final_marks}/{q.max_marks}
                <p className="text-xs text-slate-500">{q.question_text}</p>{q.comment && <p className="text-xs text-indigo-700">Faculty comment: {q.comment}</p>}</li>))}</ul>
          </CardBody>
        </Card>))}
    </AppShell>
  );
}
