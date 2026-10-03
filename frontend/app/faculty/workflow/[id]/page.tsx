/* eslint-disable react-hooks/set-state-in-effect -- data is fetched after mount; state is set after awaited calls */
"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, CheckCircle2, Loader2, Play, RefreshCw, Upload } from "lucide-react";
import { AppShell } from "../../../components/AppShell";
import { ConnectionBar } from "../../../components/ConnectionBar";
import { Card, CardBody, CardHeader } from "../../../components/ui/Card";
import { Badge } from "../../../components/ui/Badge";
import { wf, type AssessmentDetail, type Criterion, type Dashboard, type Item } from "../../../lib/workflowApi";

const KINDS: [string, string][] = [
  ["question_paper", "Question paper"],
  ["model_answer", "Model answers"],
  ["rubric", "Marking scheme / rubric"],
  ["reference", "Reference notes (optional)"],
];
const ACTIVE = ["PROCESSING", "EVALUATING"];

function ItemEditor({ id, item, onSaved }: { id: string; item: Item; onSaved: () => void }) {
  const [text, setText] = useState(item.text);
  const [marks, setMarks] = useState(item.max_marks?.toString() ?? "");
  const [answer, setAnswer] = useState(item.model_answer ?? "");
  const [crit, setCrit] = useState<Criterion[]>(item.rubric ?? []);
  const [err, setErr] = useState("");
  const input = "w-full rounded-lg border border-slate-300 px-2 py-1 text-sm";

  async function save() {
    try {
      await wf.editItem(id, item.id, {
        text, model_answer: answer, ...(marks ? { max_marks: Number(marks) } : {}),
        ...(crit.length ? { criteria: crit } : {}),
      });
      setErr("");
      onSaved();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    }
  }
  const setC = (i: number, patch: Partial<Criterion>) => setCrit(crit.map((c, j) => (j === i ? { ...c, ...patch } : c)));

  return (
    <details className="rounded-xl border border-slate-200 p-3">
      <summary className="flex cursor-pointer flex-wrap items-center gap-2 text-sm font-medium">
        {item.full_id}
        <Badge variant={item.approved ? "live" : "neutral"}>{item.approved ? "approved" : "needs approval"}</Badge>
        {item.issues.map((i) => <Badge key={i} variant="danger">{i}</Badge>)}
      </summary>
      <div className="mt-3 space-y-3">
        <label className="block text-xs text-slate-500">Question<textarea rows={2} className={input} value={text} onChange={(e) => setText(e.target.value)} /></label>
        <label className="block text-xs text-slate-500">Max marks<input className={`${input} w-24`} value={marks} onChange={(e) => setMarks(e.target.value)} /></label>
        <label className="block text-xs text-slate-500">Model answer<textarea rows={3} className={input} value={answer} onChange={(e) => setAnswer(e.target.value)} /></label>
        <div>
          <p className="text-xs text-slate-500">Rubric criteria {crit.length === 0 && <b className="text-rose-600">(none: this question cannot be auto-graded)</b>}</p>
          {crit.map((c, i) => (
            <div key={i} className="mt-1 flex gap-2">
              <input className={input} value={c.description} onChange={(e) => setC(i, { description: e.target.value })} />
              <input className={`${input} w-20`} value={c.max_marks} onChange={(e) => setC(i, { max_marks: Number(e.target.value) || 0 })} />
              <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={c.partial_credit} onChange={(e) => setC(i, { partial_credit: e.target.checked })} />partial</label>
              <button className="text-xs text-rose-600" onClick={() => setCrit(crit.filter((_, j) => j !== i))}>remove</button>
            </div>
          ))}
          <button className="mt-2 text-xs text-indigo-600" onClick={() => setCrit([...crit, { description: "", max_marks: 1, partial_credit: false }])}>+ add criterion</button>
        </div>
        {err && <p className="text-xs text-rose-600">{err}</p>}
        <button onClick={save} className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-medium text-white">Save (requires re-approval)</button>
      </div>
    </details>
  );
}

export default function AssessmentHub({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [detail, setDetail] = useState<AssessmentDetail | null>(null);
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");
  const [roll, setRoll] = useState("");
  const [name, setName] = useState("");

  const load = useCallback(async () => {
    try {
      const [d, b] = await Promise.all([wf.get(id), wf.dashboard(id)]);
      setDetail(d);
      setDash(b);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed to load");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const processing = dash?.submissions.some((s) => ACTIVE.includes(s.status));
  useEffect(() => {
    if (!processing) return;
    const t = setInterval(() => void load(), 3000);
    return () => clearInterval(t);
  }, [processing, load]);

  async function act(label: string, fn: () => Promise<unknown>) {
    setBusy(label);
    setMsg("");
    try {
      await fn();
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy("");
    }
  }

  const approved = detail?.status === "MATERIALS_APPROVED";
  return (
    <AppShell role="faculty" title={detail?.title ?? "Assessment"} subtitle={detail ? `${detail.subject} · ${detail.status}` : ""}
      action={<Link href="/faculty/workflow" className="text-sm text-indigo-600">← All assessments</Link>}>
      <ConnectionBar role="faculty" onChange={load} />
      {msg && <p className="mb-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{msg}</p>}

      <Card className="mb-6">
        <CardHeader title="1 · Materials" subtitle="Text PDF/DOCX/TXT; scanned PDFs fall back to OCR." />
        <CardBody>
          <div className="grid gap-3 md:grid-cols-2">
            {KINDS.map(([kind, label]) => (
              <label key={kind} className="flex items-center justify-between gap-3 rounded-xl border border-dashed border-slate-300 p-3 text-sm">
                {label}
                <input type="file" accept=".pdf,.docx,.txt" disabled={!!busy} className="max-w-52 text-xs"
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) void act(`up-${kind}`, async () => {
                    const r = await wf.upload(id, kind, f);
                    setMsg(r.duplicate ? "Duplicate file ignored." : `Parsed ${r.items} item(s) from ${f.name}.`);
                  }); e.target.value = ""; }} />
              </label>
            ))}
          </div>
          <ul className="mt-3 space-y-1 text-xs text-slate-500">
            {detail?.documents.map((d) => (
              <li key={`${d.kind}${d.filename}${d.version}`}>{d.kind} · {d.filename} v{d.version} · {d.approved ? "approved" : "pending"} · RAG: {d.index_status}</li>
            ))}
          </ul>
        </CardBody>
      </Card>

      <Card className="mb-6">
        <CardHeader title="2 · Review & approve extracted questions" subtitle="Edit anything wrong, then approve. Missing rubrics are flagged, never invented."
          action={<button disabled={!!busy || !detail?.items.length} onClick={() => act("approve", async () => {
            const r = await wf.approve(id);
            setMsg(`Approved ${r.approved_items} item(s). RAG: ${r.rag.status}${r.rag.detail ? ` (${r.rag.detail})` : ""}.` +
              (r.issues.length ? ` Attention: ${r.issues.map((i) => `${i.full_id}: ${i.issues.join(", ")}`).join("; ")}` : ""));
          })} className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
            {busy === "approve" ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />} Approve materials</button>} />
        <CardBody>
          <div className="space-y-2">
            {detail?.items.map((it) => <ItemEditor key={it.id + it.text + it.approved} id={id} item={it} onSaved={load} />)}
            {detail && detail.items.length === 0 && <p className="text-sm text-slate-500">Upload a question paper and model answers to begin.</p>}
          </div>
        </CardBody>
      </Card>

      <Card className="mb-6">
        <CardHeader title="3 · Student submissions" subtitle={approved ? "PDF / PNG / JPG answer sheets." : "Approve materials first."} />
        <CardBody>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <input placeholder="Roll no" className="rounded-lg border border-slate-300 px-3 py-1.5" value={roll} onChange={(e) => setRoll(e.target.value)} />
            <input placeholder="Student name" className="rounded-lg border border-slate-300 px-3 py-1.5" value={name} onChange={(e) => setName(e.target.value)} />
            <label className={`inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-1.5 text-white ${approved && roll ? "cursor-pointer" : "opacity-50"}`}>
              <Upload size={14} /> Upload & process
              <input type="file" accept=".pdf,.png,.jpg,.jpeg" className="hidden" disabled={!approved || !roll || !!busy}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) void act("submit", async () => {
                  const s = await wf.submit(id, roll, name, f);
                  if (!s.duplicate) await wf.process(s.submission_id); else setMsg("Same file already uploaded for this student.");
                }); e.target.value = ""; }} />
            </label>
          </div>
          <ul className="mt-4 divide-y divide-slate-100 text-sm">
            {dash?.submissions.map((s) => (
              <li key={s.id} className="flex items-center justify-between gap-3 py-2">
                <span>{s.roll_no} · {s.name} <span className="text-xs text-slate-400">{s.filename}</span></span>
                <span className="flex items-center gap-2">
                  {ACTIVE.includes(s.status) && <Loader2 size={14} className="animate-spin text-slate-400" />}
                  <Badge variant={s.status === "FAILED" ? "danger" : s.status === "FINAL" ? "live" : s.status === "NEEDS_REVIEW" ? "review" : "neutral"}>{s.status}</Badge>
                  {s.error && <span className="text-xs text-rose-600">{s.error}</span>}
                  {(s.status === "FAILED" || s.status === "UPLOADED") && (
                    <button className="text-xs text-indigo-600" onClick={() => act("retry", () => wf.process(s.id, true))}><RefreshCw size={12} className="inline" /> retry</button>
                  )}
                  {s.status === "EXTRACTED" && <button className="text-xs text-indigo-600" onClick={() => act("eval", () => wf.evaluate(s.id))}><Play size={12} className="inline" /> evaluate</button>}
                  {!["UPLOADED", "PROCESSING", "FAILED"].includes(s.status) && (
                    <Link className="text-xs font-medium text-indigo-700 underline" href={`/faculty/workflow/${id}/review/${s.id}`}>open review</Link>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </CardBody>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Question-wise progress" />
          <CardBody>
            <table className="w-full text-sm"><thead className="text-left text-xs text-slate-500"><tr><th>Q</th><th>Answers</th><th>Evaluated</th><th>Reviewed</th></tr></thead>
              <tbody>{dash && Object.entries(dash.question_progress).sort().map(([q, p]) => (
                <tr key={q}><td>{q}</td><td>{p.responses}</td><td>{p.evaluated}</td><td>{p.reviewed}</td></tr>))}</tbody></table>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="AI-proposed vs faculty-approved marks" />
          <CardBody>
            <table className="w-full text-sm"><thead className="text-left text-xs text-slate-500"><tr><th>Student</th><th>AI</th><th>Final</th><th>Status</th></tr></thead>
              <tbody>{dash?.results.map((r) => (
                <tr key={r.submission_id}><td>{r.roll_no}</td><td>{r.ai_total}/{r.max_total}</td>
                  <td>{r.final_total ?? "—"}</td><td><Badge variant={r.published ? "live" : r.status === "FINAL" ? "local" : "review"}>{r.published ? "PUBLISHED" : r.status}</Badge></td></tr>))}</tbody></table>
            {dash && dash.review_queue.length > 0 && (
              <p className="mt-3 flex items-center gap-2 text-xs text-amber-700"><AlertTriangle size={14} />{dash.review_queue.length} answer(s) awaiting faculty review</p>
            )}
          </CardBody>
        </Card>
      </div>
    </AppShell>
  );
}
