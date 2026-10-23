/* eslint-disable react-hooks/set-state-in-effect -- data is fetched after mount; state is set after awaited calls */
"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Play,
  RefreshCw,
  Upload,
} from "lucide-react";
import { AppShell } from "../../../components/AppShell";
import { ConnectionBar } from "../../../components/ConnectionBar";
import { Card, CardBody, CardHeader } from "../../../components/ui/Card";
import { Badge } from "../../../components/ui/Badge";
import {
  wf,
  type AssessmentDetail,
  type Criterion,
  type Dashboard,
  type Item,
} from "../../../lib/workflowApi";

const KINDS: [string, string][] = [
  ["question_paper", "Question paper"],
  ["model_answer", "Model answers"],
  ["rubric", "Marking scheme / rubric"],
  ["reference", "Reference notes (optional)"],
];

const ACTIVE = ["PROCESSING", "EVALUATING"];

const inputClass =
  "block w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-700 shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-700";

const fileInputClass =
  "block w-full min-w-0 cursor-pointer rounded-lg border border-slate-300 bg-white text-sm text-slate-800 file:mr-3 file:cursor-pointer file:rounded-l-lg file:border-0 file:border-r file:border-slate-300 file:bg-indigo-50 file:px-3 file:py-2 file:font-medium file:text-indigo-700 hover:file:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-60";

function ItemEditor({
  id,
  item,
  onSaved,
}: {
  id: string;
  item: Item;
  onSaved: () => void;
}) {
  const [text, setText] = useState(item.text);
  const [marks, setMarks] = useState(item.max_marks?.toString() ?? "");
  const [answer, setAnswer] = useState(item.model_answer ?? "");
  const [crit, setCrit] = useState<Criterion[]>(item.rubric ?? []);
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await wf.editItem(id, item.id, {
        text,
        model_answer: answer,
        ...(marks.trim() ? { max_marks: Number(marks) } : {}),
        ...(crit.length ? { criteria: crit } : {}),
      });
      setErr("");
      onSaved();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const setC = (i: number, patch: Partial<Criterion>) =>
    setCrit(crit.map((c, j) => (j === i ? { ...c, ...patch } : c)));

  return (
    <details className="rounded-xl border border-slate-200 bg-white p-3">
      <summary className="flex cursor-pointer flex-wrap items-center gap-2 text-sm font-medium text-slate-800">
        {item.full_id}
        <Badge variant={item.approved ? "live" : "neutral"}>
          {item.approved ? "approved" : "needs approval"}
        </Badge>
        {item.issues.map((issue) => (
          <Badge key={issue} variant="danger">
            {issue}
          </Badge>
        ))}
      </summary>

      <div className="mt-3 space-y-3">
        <label className="block text-sm font-medium text-slate-700">
          Question
          <textarea
            rows={2}
            className={inputClass}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </label>

        <label className="block text-sm font-medium text-slate-700">
          Maximum marks
          <input
            type="number"
            min="0"
            className={`${inputClass} mt-1 w-32`}
            value={marks}
            onChange={(e) => setMarks(e.target.value)}
          />
        </label>

        <label className="block text-sm font-medium text-slate-700">
          Model answer
          <textarea
            rows={3}
            className={inputClass}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
          />
        </label>

        <div>
          <p className="text-sm font-medium text-slate-700">
            Rubric criteria{" "}
            {crit.length === 0 && (
              <span className="text-rose-600">
                (none — this question cannot be auto-graded)
              </span>
            )}
          </p>

          {crit.map((c, i) => (
            <div
              key={i}
              className="mt-2 grid grid-cols-1 items-center gap-2 sm:grid-cols-[minmax(0,1fr)_90px_auto_auto]"
            >
              <input
                aria-label={`Criterion ${i + 1} description`}
                className={inputClass}
                value={c.description}
                onChange={(e) => setC(i, { description: e.target.value })}
              />
              <input
                aria-label={`Criterion ${i + 1} marks`}
                type="number"
                min="0"
                className={inputClass}
                value={c.max_marks}
                onChange={(e) =>
                  setC(i, { max_marks: Number(e.target.value) || 0 })
                }
              />
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={c.partial_credit}
                  onChange={(e) =>
                    setC(i, { partial_credit: e.target.checked })
                  }
                />
                Partial credit
              </label>
              <button
                type="button"
                className="text-sm font-medium text-rose-600 hover:text-rose-800"
                onClick={() =>
                  setCrit(crit.filter((_, j) => j !== i))
                }
              >
                Remove
              </button>
            </div>
          ))}

          <button
            type="button"
            className="mt-3 rounded-lg border border-indigo-200 px-3 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-50"
            onClick={() =>
              setCrit([
                ...crit,
                { description: "", max_marks: 1, partial_credit: false },
              ])
            }
          >
            + Add criterion
          </button>
        </div>

        {err && <p className="text-sm text-rose-600">{err}</p>}

        <button
          type="button"
          disabled={saving}
          onClick={save}
          className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save (requires re-approval)"}
        </button>
      </div>
    </details>
  );
}

export default function AssessmentHub({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
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
      setMsg(e instanceof Error ? e.message : "Failed to load assessment");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const processing = dash?.submissions.some((s) =>
    ACTIVE.includes(s.status)
  );

  useEffect(() => {
    if (!processing) return;

    const timer = setInterval(() => void load(), 3000);
    return () => clearInterval(timer);
  }, [processing, load]);

  async function act(label: string, fn: () => Promise<unknown>) {
    setBusy(label);
    setMsg("");

    try {
      await fn();
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setBusy("");
    }
  }

  const approved = detail?.status === "MATERIALS_APPROVED";

  return (
    <AppShell
      role="faculty"
      title={detail?.title ?? "Assessment"}
      subtitle={detail ? `${detail.subject} · ${detail.status}` : ""}
      action={
        <Link
          href="/faculty/workflow"
          className="text-sm font-medium text-indigo-700 hover:underline"
        >
          ← All assessments
        </Link>
      }
    >
      <ConnectionBar role="faculty" onChange={load} />

      {msg && (
        <p
          role="status"
          className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700"
        >
          {msg}
        </p>
      )}

      {/* 1. Assessment materials */}
      <Card className="mb-6">
        <CardHeader
          title="1 · Materials"
          subtitle="Upload a question paper, model answers and rubric. Text PDFs/DOCX/TXT are supported; scanned PDFs may use OCR."
        />

        <CardBody>
          <div className="grid gap-4 md:grid-cols-2">
            {KINDS.map(([kind, label]) => (
              <div
                key={kind}
                className="min-w-0 rounded-xl border border-slate-200 bg-slate-50 p-4"
              >
                <label
                  htmlFor={`file-${kind}`}
                  className="mb-2 block text-sm font-semibold text-slate-800"
                >
                  {label}
                </label>

                <input
                  id={`file-${kind}`}
                  type="file"
                  accept=".pdf,.docx,.txt"
                  disabled={!!busy}
                  className={fileInputClass}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      void act(`up-${kind}`, async () => {
                        const result = await wf.upload(id, kind, file);
                        setMsg(
                          result.duplicate
                            ? "Duplicate file ignored."
                            : `Parsed ${result.items} item(s) from ${file.name}.`
                        );
                      });
                    }
                    e.target.value = "";
                  }}
                />
              </div>
            ))}
          </div>

          <div className="mt-4 rounded-lg bg-slate-50 p-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-700">
              Uploaded materials
            </p>
            {!detail?.documents.length ? (
              <p className="text-sm text-slate-700">
                No materials uploaded yet.
              </p>
            ) : (
              <ul className="space-y-2 text-sm text-slate-700">
                {detail.documents.map((doc) => (
                  <li
                    key={`${doc.kind}-${doc.filename}-${doc.version}`}
                    className="break-words rounded-lg border border-slate-200 bg-white p-3"
                  >
                    <span className="font-medium">{doc.kind}</span>
                    {" · "}
                    {doc.filename} · v{doc.version}
                    {" · "}
                    {doc.approved ? "Approved" : "Pending approval"}
                    {" · "}
                    RAG: {doc.index_status}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </CardBody>
      </Card>

      {/* 2. Review and approve materials */}
      <Card className="mb-6">
        <CardHeader
          title="2 · Review & approve extracted questions"
          subtitle="Check the extracted questions, model answers and rubric. Correct errors before approval."
          action={
            <button
              type="button"
              disabled={!!busy || !detail?.items.length}
              onClick={() =>
                act("approve", async () => {
                  const result = await wf.approve(id);
                  setMsg(
                    `Approved ${result.approved_items} item(s). RAG: ${result.rag.status}${result.rag.detail ? ` (${result.rag.detail})` : ""
                    }.${result.issues.length
                      ? ` Attention: ${result.issues
                        .map(
                          (item) =>
                            `${item.full_id}: ${item.issues.join(", ")}`
                        )
                        .join("; ")}`
                      : ""
                    }`
                  );
                })
              }
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy === "approve" ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <CheckCircle2 size={16} />
              )}
              Approve materials
            </button>
          }
        />

        <CardBody>
          <div className="space-y-3">
            {detail?.items.map((item) => (
              <ItemEditor
                key={`${item.id}-${item.text}-${item.approved}`}
                id={id}
                item={item}
                onSaved={load}
              />
            ))}

            {detail && detail.items.length === 0 && (
              <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-700">
                Upload a question paper and model answers to begin.
              </p>
            )}
          </div>
        </CardBody>
      </Card>

      {/* 3. Student answer-sheet submissions */}
      <Card className="mb-6">
        <CardHeader
          title="3 · Student submissions"
          subtitle={
            approved
              ? "Upload a student's PDF, PNG or JPG answer sheet."
              : "Approve the assessment materials before uploading submissions."
          }
        />

        <CardBody>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_auto]">
            <label className="block text-sm font-medium text-slate-700">
              Student roll number
              <input
                placeholder="e.g. 23CS001"
                aria-label="Student roll number"
                className={`${inputClass} mt-1`}
                value={roll}
                onChange={(e) => setRoll(e.target.value)}
              />
            </label>

            <label className="block text-sm font-medium text-slate-700">
              Student name
              <input
                placeholder="e.g. Student Name"
                aria-label="Student name"
                className={`${inputClass} mt-1`}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>

            <div className="flex items-end">
              <label
                className={`inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-lg border border-indigo-700 bg-indigo-600 px-4 py-2 text-sm font-semibold text-white ${approved && roll.trim() && !busy
                  ? "cursor-pointer hover:bg-indigo-700"
                  : "cursor-not-allowed opacity-50"
                  }`}
              >
                {busy === "submit" ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Upload size={16} />
                )}
                Choose answer sheet
                <input
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg"
                  className="sr-only"
                  disabled={!approved || !roll.trim() || !!busy}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      void act("submit", async () => {
                        const submission = await wf.submit(id, roll, name, file);
                        if (!submission.duplicate) {
                          await wf.process(submission.submission_id);
                        } else {
                          setMsg("The same file has already been uploaded for this student.");
                        }
                      });
                    }
                    e.target.value = "";
                  }}
                />
              </label>
            </div>
          </div>

          <p className="mt-3 text-xs text-slate-700">
            First review the extracted text. AI evaluation should only proceed
            after faculty confirms the OCR results.
          </p>

          <ul className="mt-4 divide-y divide-slate-200 text-sm">
            {dash?.submissions.map((submission) => (
              <li
                key={submission.id}
                className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="font-medium text-slate-800">
                    {submission.roll_no} · {submission.name}
                  </p>
                  <p className="break-words text-xs text-slate-700">
                    {submission.filename}
                  </p>
                  {submission.error && (
                    <p className="mt-1 text-xs text-rose-600">
                      {submission.error}
                    </p>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {ACTIVE.includes(submission.status) && (
                    <Loader2
                      size={15}
                      className="animate-spin text-slate-700"
                    />
                  )}

                  <Badge
                    variant={
                      submission.status === "FAILED"
                        ? "danger"
                        : submission.status === "FINAL"
                          ? "live"
                          : submission.status === "NEEDS_REVIEW"
                            ? "review"
                            : "neutral"
                    }
                  >
                    {submission.status}
                  </Badge>

                  {(submission.status === "FAILED" ||
                    submission.status === "UPLOADED") && (
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-50"
                        onClick={() =>
                          act("retry", () => wf.process(submission.id, true))
                        }
                      >
                        <RefreshCw size={12} />
                        Retry
                      </button>
                    )}

                  {submission.status === "NEEDS_REVIEW" && (
                    <button
                      type="button"
                      disabled={!!busy}
                      className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
                      onClick={() =>
                        act("confirm-ocr", async () => {
                          await wf.confirmOcrReview(submission.id);
                          await wf.evaluate(submission.id);
                        })
                      }
                    >
                      <Play size={13} />
                      Confirm OCR & evaluate
                    </button>
                  )}

                  {!["UPLOADED", "PROCESSING", "FAILED"].includes(
                    submission.status
                  ) && (
                      <Link
                        className="rounded-md border border-slate-300 px-3 py-2 text-xs font-medium text-indigo-700 hover:bg-indigo-50"
                        href={`/faculty/workflow/${id}/review/${submission.id}`}
                      >
                        Open review
                      </Link>
                    )}
                </div>
              </li>
            ))}
          </ul>

          {dash && dash.submissions.length === 0 && (
            <p className="mt-3 rounded-lg bg-slate-50 p-4 text-sm text-slate-700">
              No student submissions yet.
            </p>
          )}
        </CardBody>
      </Card>

      {/* Progress and marks */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Question-wise progress" />
          <CardBody>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-slate-00">
                  <tr>
                    <th className="py-2 pr-3">Question</th>
                    <th className="py-2 pr-3">Answers</th>
                    <th className="py-2 pr-3">Evaluated</th>
                    <th className="py-2">Reviewed</th>
                  </tr>
                </thead>
                <tbody>
                  {dash &&
                    Object.entries(dash.question_progress)
                      .sort()
                      .map(([question, progress]) => (
                        <tr
                          key={question}
                          className="border-t border-slate-100"
                        >
                          <td className="py-2 pr-3">{question}</td>
                          <td className="py-2 pr-3">{progress.responses}</td>
                          <td className="py-2 pr-3">{progress.evaluated}</td>
                          <td className="py-2">{progress.reviewed}</td>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="AI-proposed vs faculty-approved marks" />
          <CardBody>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-slate-600">
                  <tr>
                    <th className="py-2 pr-3">Student</th>
                    <th className="py-2 pr-3">AI marks</th>
                    <th className="py-2 pr-3">Final marks</th>
                    <th className="py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {dash?.results.map((result) => (
                    <tr
                      key={result.submission_id}
                      className="border-t border-slate-100"
                    >
                      <td className="py-2 pr-3">{result.roll_no}</td>
                      <td className="py-2 pr-3">
                        {result.ai_total}/{result.max_total}
                      </td>
                      <td className="py-2 pr-3">
                        {result.final_total ?? "—"}
                      </td>
                      <td className="py-2">
                        <Badge
                          variant={
                            result.published
                              ? "live"
                              : result.status === "FINAL"
                                ? "local"
                                : "review"
                          }
                        >
                          {result.published ? "PUBLISHED" : result.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {dash && dash.review_queue.length > 0 && (
              <p className="mt-3 flex items-center gap-2 text-xs text-amber-700">
                <AlertTriangle size={14} />
                {dash.review_queue.length} answer(s) awaiting faculty review
              </p>
            )}

            {dash && dash.results.length === 0 && (
              <p className="mt-3 text-sm text-slate-700">
                No evaluation results yet.
              </p>
            )}
          </CardBody>
        </Card>
      </div>
    </AppShell>
  );
}
