/* eslint-disable react-hooks/set-state-in-effect -- data is fetched after mount; state is set after awaited calls */
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ClipboardList, Loader2, Plus } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { ConnectionBar } from "../../components/ConnectionBar";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { Badge, LiveBadge } from "../../components/ui/Badge";
import { EmptyState } from "../../components/ui/EmptyState";
import { wf, type AssessmentRow } from "../../lib/workflowApi";

export default function WorkflowHome() {
  const [rows, setRows] = useState<AssessmentRow[] | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ subject_code: "", subject_name: "", title: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setRows(await wf.list());
      setError("");
    } catch (e) {
      setRows([]);
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function create() {
    setBusy(true);
    try {
      await wf.create(form);
      setForm({ subject_code: "", subject_name: "", title: "" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create");
    } finally {
      setBusy(false);
    }
  }

  const input = "rounded-lg border border-slate-300 px-3 py-2 text-sm";
  return (
    <AppShell role="faculty" title="Assessment workflow" subtitle="Materials → approval → submissions → AI evaluation → faculty review">
      <ConnectionBar role="faculty" onChange={load} />
      {error && <p className="mb-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
      <Card className="mb-6">
        <CardHeader title="New assessment" action={<LiveBadge />} />
        <CardBody>
          <div className="flex flex-wrap gap-3">
            <input className={input} placeholder="Subject code (CN301)" value={form.subject_code} onChange={(e) => setForm({ ...form, subject_code: e.target.value })} />
            <input className={input} placeholder="Subject name" value={form.subject_name} onChange={(e) => setForm({ ...form, subject_name: e.target.value })} />
            <input className={`${input} min-w-64 flex-1`} placeholder="Assessment title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <button disabled={busy || !form.subject_code || !form.subject_name || !form.title} onClick={create}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
              {busy ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />} Create
            </button>
          </div>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Assessments" />
        <CardBody>
          {rows === null ? <Loader2 className="animate-spin text-slate-400" /> : rows.length === 0 ? (
            <EmptyState icon={ClipboardList} title="No assessments yet" description="Create one above, then upload the question paper, model answers and rubric." />
          ) : (
            <ul className="divide-y divide-slate-100">
              {rows.map((a) => (
                <li key={a.id} className="flex items-center justify-between py-3">
                  <Link href={`/faculty/workflow/${a.id}`} className="font-medium text-indigo-700 hover:underline">{a.title}</Link>
                  <span className="flex items-center gap-2 text-sm text-slate-500">{a.subject}
                    {a.is_demo && <Badge variant="demo">Demo fixture</Badge>}
                    <Badge variant={a.status === "MATERIALS_APPROVED" ? "live" : "neutral"}>{a.status}</Badge>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </AppShell>
  );
}
