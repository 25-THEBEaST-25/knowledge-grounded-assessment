/* eslint-disable react-hooks/set-state-in-effect -- data is fetched after mount; state is set after awaited calls */
"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Check, Loader2, RefreshCw, Send } from "lucide-react";
import { AppShell } from "../../../../../components/AppShell";
import { ConnectionBar } from "../../../../../components/ConnectionBar";
import { Card, CardBody, CardHeader } from "../../../../../components/ui/Card";
import { Badge } from "../../../../../components/ui/Badge";
import { wf, type ResponseView, type SubmissionView } from "../../../../../lib/workflowApi";

const pct = (n: number) => `${Math.round(n * 100)}%`;
const bandVariant = (b: string) => (b === "HIGH_CANDIDATE" ? "live" : b === "REVIEW_RECOMMENDED" ? "review" : "danger");
const statusVariant = (s: string) => (s === "SATISFIED" ? "live" : s === "PARTIAL" ? "review" : s === "UNCERTAIN" ? "neutral" : "danger");

function PageImage({ sid, page }: { sid: string; page: number }) {
  const [url, setUrl] = useState("");
  const [err, setErr] = useState("");
  useEffect(() => {
    let alive = true;
    let obj = "";
    wf.pageUrl(sid, page).then((u) => { obj = u; if (alive) setUrl(u); }).catch((e) => alive && setErr(e.message));
    return () => { alive = false; if (obj) URL.revokeObjectURL(obj); };
  }, [sid, page]);
  if (err) return <p className="text-xs text-rose-600">{err}</p>;
  // eslint-disable-next-line @next/next/no-img-element
  return url ? <img src={url} alt={`Answer sheet page ${page}`} className="w-full rounded-lg border border-slate-200" /> : <Loader2 className="animate-spin text-slate-400" />;
}

function ResponsePanel({ sid, r, onDone }: { sid: string; r: ResponseView; onDone: () => void }) {
  const [marks, setMarks] = useState(String(r.final_marks ?? r.ai_marks));
  const [comment, setComment] = useState("");
  const [text, setText] = useState(r.student_text);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const page = r.region_ref.regions?.[0]?.page ?? 1;

  async function send(action: string) {
    setBusy(true);
    setErr("");
    try {
      await wf.review(r.id, { action, comment, ...(action !== "ACCEPT" ? { final_marks: Number(marks) } : {}) });
      setComment("");
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }
  async function saveText() {
    setBusy(true);
    try {
      await wf.correctText(r.id, text);
      await wf.evaluate(sid, true);
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-4">
        <Card>
          <CardHeader title={`Answer sheet · page ${page}`} subtitle="Original upload (the extracted region is on this page)." />
          <CardBody><PageImage sid={sid} page={page} /></CardBody>
        </Card>
        <Card>
          <CardHeader title="Extracted text" subtitle={r.extraction_edited ? "Corrected by faculty" : "From OCR; edit if it misreads the handwriting."}
            action={<div className="flex gap-1"><Badge variant="neutral">OCR {pct(r.ocr_confidence)}</Badge><Badge variant="neutral">Mapping {pct(r.mapping_confidence)}</Badge></div>} />
          <CardBody>
            <textarea rows={6} className="w-full rounded-lg border border-slate-300 p-2 text-sm" value={text} onChange={(e) => setText(e.target.value)} />
            <button disabled={busy || text === r.student_text} onClick={saveText} className="mt-2 inline-flex items-center gap-2 rounded-lg bg-slate-800 px-3 py-1.5 text-xs text-white disabled:opacity-40">
              <RefreshCw size={12} /> Save correction & re-evaluate
            </button>
          </CardBody>
        </Card>
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader title={`${r.subquestion} · ${r.question_text.slice(0, 90)}`}
            action={<Badge variant={bandVariant(r.confidence_band)}>{r.confidence_band.replace("_", " ")} · {pct(r.overall_confidence)}</Badge>} />
          <CardBody>
            {r.review_reasons.length > 0 && (
              <p className="mb-3 flex flex-wrap items-center gap-2 text-xs text-amber-700"><AlertTriangle size={14} />Why review: {r.review_reasons.map((x) => <Badge key={x} variant="review">{x}</Badge>)}</p>
            )}
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-slate-500"><tr><th>Criterion</th><th>Evidence</th><th className="text-right">Marks</th></tr></thead>
              <tbody>{r.criteria.map((c) => (
                <tr key={c.code} className="border-t border-slate-100 align-top">
                  <td className="py-2 pr-2"><b>{c.code}</b> {c.description}</td>
                  <td className="py-2 pr-2 text-xs">
                    {c.evidence ? (<><Badge variant={statusVariant(c.evidence.status)}>{c.evidence.status}</Badge> {pct(c.evidence.confidence)}
                      <p className="mt-1 text-slate-600">{c.evidence.text}</p>
                      {c.evidence.source_refs.length > 0 && <p className="text-slate-400">sources: {c.evidence.source_refs.join(", ")}</p>}</>) : <span className="text-slate-400">none</span>}
                    {c.flags.map((f) => <Badge key={f} variant="review" className="ml-1">{f}</Badge>)}
                  </td>
                  <td className="py-2 text-right">{c.awarded ?? "—"}/{c.max_marks}</td>
                </tr>))}</tbody>
            </table>
            <p className="mt-3 text-sm font-medium">AI-proposed: {r.ai_marks}/{r.max_marks}{r.reviewed && <> · Final: {r.final_marks}</>}</p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Retrieved approved sources" action={<Badge variant={r.retrieval?.status === "USED" ? "live" : "danger"}>{r.retrieval?.status ?? "NOT RUN"}</Badge>} />
          <CardBody>
            {r.retrieval?.status === "UNAVAILABLE" && <p className="text-xs text-rose-600">Retrieval was unavailable: this evaluation was NOT grounded in retrieved material.</p>}
            <ul className="space-y-1 text-xs text-slate-600">{r.retrieval?.sources.map((s) => <li key={s.ref}>[{s.ref}] {s.source} ({s.doc_type}, score {s.score})</li>)}</ul>
            {r.plan && <p className="mt-3 text-xs text-slate-500">Plan: {r.plan.type} · {r.plan.status} · {r.plan.tasks.map((t) => `${t.evaluator}:${t.status}${t.error ? ` (${t.error})` : ""}`).join(", ")}</p>}
            {r.plan?.tasks.filter((t) => t.status === "NOT_IMPLEMENTED").map((t) => <p key={t.evaluator} className="mt-1 text-xs text-violet-700">{t.reason}</p>)}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Faculty decision" />
          <CardBody>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <input className="w-24 rounded-lg border border-slate-300 px-2 py-1" value={marks} onChange={(e) => setMarks(e.target.value)} /> / {r.max_marks}
              <input className="min-w-48 flex-1 rounded-lg border border-slate-300 px-2 py-1" placeholder="Comment (required to modify/reject)" value={comment} onChange={(e) => setComment(e.target.value)} />
            </div>
            <div className="mt-3 flex gap-2">
              <button disabled={busy} onClick={() => send("ACCEPT")} className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm text-white"><Check size={14} />Accept AI marks</button>
              <button disabled={busy} onClick={() => send("MODIFY")} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm text-white">Modify</button>
              <button disabled={busy} onClick={() => send("REJECT")} className="rounded-lg bg-rose-600 px-3 py-1.5 text-sm text-white">Reject</button>
            </div>
            {err && <p className="mt-2 text-xs text-rose-600">{err}</p>}
            <ul className="mt-3 space-y-1 text-xs text-slate-500">{r.reviews.map((h, i) => <li key={i}>{h.reviewer}: {h.action} · AI {h.ai_marks} → {h.final_marks}{h.comment && ` · “${h.comment}”`}</li>)}</ul>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

export default function ReviewPage({ params }: { params: Promise<{ id: string; sid: string }> }) {
  const { id, sid } = use(params);
  const [sub, setSub] = useState<SubmissionView | null>(null);
  const [active, setActive] = useState(0);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    try { setSub(await wf.submission(sid)); } catch (e) { setMsg(e instanceof Error ? e.message : "Failed"); }
  }, [sid]);
  useEffect(() => { void load(); }, [load]);

  async function publish() {
    try { await wf.publish(sid); setMsg("Published: the student can now see final marks."); await load(); }
    catch (e) { setMsg(e instanceof Error ? e.message : "Failed"); }
  }
  const res = sub?.result;
  const cur = sub?.responses[active];
  return (
    <AppShell role="faculty" title={sub ? `Review · ${sub.student.roll_no} ${sub.student.name}` : "Review"}
      subtitle={res ? `AI total ${res.ai_total}/${res.max_total} · Final ${res.final_total ?? "pending review"} · ${res.status}${res.published ? " · PUBLISHED" : ""}` : ""}
      action={<div className="flex items-center gap-3"><Link href={`/faculty/workflow/${id}`} className="text-sm text-indigo-600">← Assessment</Link>
        <button disabled={res?.status !== "FINAL" || res?.published} onClick={publish} className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm text-white disabled:opacity-40"><Send size={14} />Publish final marks</button></div>}>
      <ConnectionBar role="faculty" onChange={load} />
      {msg && <p className="mb-4 rounded-lg bg-sky-50 p-3 text-sm text-sky-800">{msg}</p>}
      {sub?.status === "FAILED" && <p className="mb-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">Processing failed: {sub.error}</p>}
      <div className="mb-4 flex flex-wrap gap-2">
        {sub?.responses.map((r, i) => (
          <button key={r.id} onClick={() => setActive(i)} className={`rounded-lg border px-3 py-1.5 text-sm ${i === active ? "border-indigo-500 bg-indigo-50" : "border-slate-200 bg-white"}`}>
            {r.subquestion} {r.reviewed ? "✓" : r.needs_review ? "⚠" : ""}
          </button>))}
      </div>
      {cur ? <ResponsePanel key={cur.id + cur.student_text + (cur.reviews.length)} sid={sid} r={cur} onDone={load} /> : <Loader2 className="animate-spin text-slate-400" />}
    </AppShell>
  );
}
