
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

const bandVariant = (b: string) =>
  b === "HIGH_CANDIDATE"
    ? "live"
    : b === "REVIEW_RECOMMENDED"
      ? "review"
      : "danger";

const statusVariant = (s: string) =>
  s === "SATISFIED"
    ? "live"
    : s === "PARTIAL"
      ? "review"
      : s === "UNCERTAIN"
        ? "neutral"
        : "danger";

const fieldClass =
  "min-w-0 rounded-lg border border-slate-400 bg-white px-3 py-2 text-sm text-slate-950 placeholder:text-slate-600 focus:border-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-200";

const primaryButton =
  "inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-white transition-colors disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-700";

function PageImage({ sid, page }: { sid: string; page: number }) {
  const [url, setUrl] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    let obj = "";

    wf.pageUrl(sid, page)
      .then((u) => {
        obj = u;
        if (alive) setUrl(u);
      })
      .catch((e) => {
        if (alive) setErr(e instanceof Error ? e.message : "Could not load answer sheet image.");
      });

    return () => {
      alive = false;
      if (obj) URL.revokeObjectURL(obj);
    };
  }, [sid, page]);

  if (err) return <p className="text-sm text-rose-700">{err}</p>;

  // eslint-disable-next-line @next/next/no-img-element
  return url ? (
    <img
      src={url}
      alt={`Answer sheet page ${page}`}
      className="w-full rounded-lg border border-slate-300"
    />
  ) : (
    <div className="flex items-center gap-2 py-4 text-sm text-slate-700">
      <Loader2 size={18} className="animate-spin" />
      Loading answer sheet…
    </div>
  );
}

function ResponsePanel({
  sid,
  r,
  onDone,
}: {
  sid: string;
  r: ResponseView;
  onDone: () => void;
}) {
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
      await wf.review(r.id, {
        action,
        comment,
        ...(action !== "ACCEPT" ? { final_marks: Number(marks) } : {}),
      });
      setComment("");
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Review action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function saveText() {
    setBusy(true);
    setErr("");

    try {
      await wf.correctText(r.id, text);
      await wf.evaluate(sid, true);
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Saving the correction failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-4">
        <Card>
          <CardHeader
            title={`Answer sheet · page ${page}`}
            subtitle="Original upload. The extracted answer region is on this page."
          />
          <CardBody>
            <PageImage sid={sid} page={page} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Extracted text"
            subtitle={
              r.extraction_edited
                ? "Corrected by faculty"
                : "Review the OCR output and correct any handwriting recognition errors."
            }
            action={
              <div className="flex flex-wrap gap-2">
                <Badge variant="neutral">OCR {pct(r.ocr_confidence)}</Badge>
                <Badge variant="neutral">
                  Mapping {pct(r.mapping_confidence)}
                </Badge>
              </div>
            }
          />
          <CardBody>
            <label
              htmlFor={`ocr-text-${r.id}`}
              className="mb-2 block text-sm font-semibold text-slate-950"
            >
              Student answer text
            </label>
            <textarea
              id={`ocr-text-${r.id}`}
              rows={6}
              className={`${fieldClass} w-full leading-6`}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <button
              type="button"
              disabled={busy || text === r.student_text}
              onClick={saveText}
              className={`${primaryButton} mt-3 bg-slate-800 hover:bg-slate-700`}
            >
              <RefreshCw size={14} />
              {busy ? "Saving…" : "Save correction & re-evaluate"}
            </button>
          </CardBody>
        </Card>
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader
            title={`${r.subquestion} · ${r.question_text.slice(0, 90)}`}
            action={
              <Badge variant={bandVariant(r.confidence_band)}>
                {r.confidence_band.replace("_", " ")} ·{" "}
                {pct(r.overall_confidence)}
              </Badge>
            }
          />
          <CardBody>
            {r.review_reasons.length > 0 && (
              <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-3">
                <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-amber-950">
                  <AlertTriangle size={16} />
                  Why review is recommended
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {r.review_reasons.map((reason) => (
                    <Badge key={reason} variant="review">
                      {reason}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-sm font-semibold text-slate-950">
                  <tr className="border-b-2 border-slate-300">
                    <th className="py-3 pr-3">Criterion</th>
                    <th className="py-3 pr-3">Evidence</th>
                    <th className="py-3 text-right">Marks</th>
                  </tr>
                </thead>
                <tbody>
                  {r.criteria.map((c) => (
                    <tr
                      key={c.code}
                      className="border-b border-slate-200 align-top"
                    >
                      <td className="py-3 pr-3 text-sm leading-6 text-slate-950">
                        <strong>{c.code}</strong>{" "}
                        <span>{c.description}</span>
                      </td>
                      <td className="py-3 pr-3 text-sm leading-6 text-slate-900">
                        {c.evidence ? (
                          <>
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge variant={statusVariant(c.evidence.status)}>
                                {c.evidence.status}
                              </Badge>
                              <span className="font-medium text-slate-800">
                                {pct(c.evidence.confidence)} confidence
                              </span>
                            </div>
                            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-950">
                              {c.evidence.text}
                            </p>
                            {c.evidence.source_refs.length > 0 && (
                              <p className="mt-2 break-words text-xs leading-5 text-slate-800">
                                <strong>Sources:</strong>{" "}
                                {c.evidence.source_refs.join(", ")}
                              </p>
                            )}
                          </>
                        ) : (
                          <span className="font-medium text-slate-800">
                            No evidence available
                          </span>
                        )}

                        {c.flags.map((flag) => (
                          <span key={flag} className="mt-2 mr-1 inline-block">
                            <Badge variant="review">{flag}</Badge>
                          </span>
                        ))}
                      </td>
                      <td className="whitespace-nowrap py-3 text-right font-semibold text-slate-950">
                        {c.awarded ?? "—"}/{c.max_marks}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-4 rounded-lg border border-slate-300 bg-slate-50 p-3">
              <p className="text-base font-semibold text-slate-950">
                AI-proposed marks: {r.ai_marks}/{r.max_marks}
              </p>
              {r.reviewed && (
                <p className="mt-1 text-sm font-semibold text-emerald-900">
                  Faculty-reviewed final marks: {r.final_marks}/{r.max_marks}
                </p>
              )}
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Retrieved approved sources"
            action={
              <Badge
                variant={r.retrieval?.status === "USED" ? "live" : "danger"}
              >
                {r.retrieval?.status ?? "NOT RUN"}
              </Badge>
            }
          />
          <CardBody>
            {r.retrieval?.status === "UNAVAILABLE" && (
              <p
                role="alert"
                className="rounded-lg border border-rose-300 bg-rose-50 p-3 text-sm leading-6 text-rose-900"
              >
                Retrieval was unavailable. This evaluation was not grounded in
                retrieved material.
              </p>
            )}

            {r.retrieval?.sources.length ? (
              <ul className="mt-3 space-y-3 text-sm leading-6 text-slate-950">
                {r.retrieval.sources.map((source) => (
                  <li
                    key={source.ref}
                    className="break-words rounded-lg border border-slate-200 bg-white p-3"
                  >
                    <p className="font-semibold text-slate-950">
                      [{source.ref}] {source.source}
                    </p>
                    <p className="mt-1 text-slate-800">
                      Type: {source.doc_type} · Score: {source.score}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm leading-6 text-slate-800">
                No retrieved source details are available for this evaluation.
              </p>
            )}

            {r.plan && (
              <div className="mt-4 rounded-lg border border-slate-300 bg-slate-50 p-3">
                <p className="text-sm font-semibold text-slate-950">
                  Evaluation plan
                </p>
                <p className="mt-1 break-words text-sm leading-6 text-slate-900">
                  {r.plan.type} · {r.plan.status} ·{" "}
                  {r.plan.tasks
                    .map(
                      (task) =>
                        `${task.evaluator}: ${task.status}${task.error ? ` (${task.error})` : ""
                        }`,
                    )
                    .join(", ")}
                </p>
                {r.plan.tasks
                  .filter((task) => task.status === "NOT_IMPLEMENTED")
                  .map((task) => (
                    <p
                      key={task.evaluator}
                      className="mt-2 rounded-lg bg-violet-50 p-3 text-sm leading-6 text-violet-950"
                    >
                      {task.reason}
                    </p>
                  ))}
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Faculty decision" />
          <CardBody>
            <div className="grid gap-3 sm:grid-cols-[100px_minmax(0,1fr)]">
              <label className="block text-sm font-semibold text-slate-950">
                Final marks
                <input
                  type="number"
                  min="0"
                  max={r.max_marks}
                  step="0.5"
                  aria-label="Final marks"
                  className={`${fieldClass} mt-1 w-full`}
                  value={marks}
                  onChange={(e) => setMarks(e.target.value)}
                />
              </label>

              <label className="block text-sm font-semibold text-slate-950">
                Review comment
                <input
                  className={`${fieldClass} mt-1 w-full`}
                  placeholder="Required when modifying or rejecting"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                />
              </label>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => send("ACCEPT")}
                className={`${primaryButton} bg-emerald-700 hover:bg-emerald-800`}
              >
                <Check size={15} />
                Accept AI marks
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => send("MODIFY")}
                className={`${primaryButton} bg-indigo-700 hover:bg-indigo-800`}
              >
                Modify
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => send("REJECT")}
                className={`${primaryButton} bg-rose-700 hover:bg-rose-800`}
              >
                Reject
              </button>
            </div>

            {err && (
              <p
                role="alert"
                className="mt-3 rounded-lg border border-rose-300 bg-rose-50 p-3 text-sm leading-6 text-rose-900"
              >
                {err}
              </p>
            )}

            {r.reviews.length > 0 && (
              <div className="mt-4 border-t border-slate-300 pt-3">
                <h3 className="text-sm font-semibold text-slate-950">
                  Review history
                </h3>
                <ul className="mt-2 space-y-3 text-sm leading-6 text-slate-900">
                  {r.reviews.map((history, i) => (
                    <li
                      key={`${history.reviewer}-${history.action}-${i}`}
                      className="rounded-lg border border-slate-200 bg-slate-50 p-3"
                    >
                      <p>
                        <strong>{history.reviewer}</strong>: {history.action}
                      </p>
                      <p>
                        AI {history.ai_marks} → Final {history.final_marks}
                      </p>
                      {history.comment && (
                        <p className="mt-1 break-words text-slate-800">
                          Comment: {history.comment}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

export default function ReviewPage({
  params,
}: {
  params: Promise<{ id: string; sid: string }>;
}) {
  const { id, sid } = use(params);
  const [sub, setSub] = useState<SubmissionView | null>(null);
  const [active, setActive] = useState(0);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    try {
      setSub(await wf.submission(sid));
      setMsg("");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed to load submission.");
    }
  }, [sid]);

  useEffect(() => {
    void load();
  }, [load]);

  async function publish() {
    try {
      await wf.publish(sid);
      setMsg("Published: the student can now see final marks.");
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Publishing failed.");
    }
  }

  const res = sub?.result;
  const cur = sub?.responses[active];

  return (
    <AppShell
      role="faculty"
      title={
        sub
          ? `Review · ${sub.student.roll_no} ${sub.student.name}`
          : "Review submission"
      }
      subtitle={
        res
          ? `AI total ${res.ai_total}/${res.max_total} · Final ${res.final_total ?? "pending review"
          } · ${res.status}${res.published ? " · PUBLISHED" : ""}`
          : "Review extracted answers, evidence, and proposed marks."
      }
      action={
        <div className="flex flex-wrap items-center gap-3">
          <Link
            href={`/faculty/workflow/${id}`}
            className="rounded-lg px-2 py-2 text-sm font-semibold text-indigo-800 underline decoration-indigo-300 underline-offset-4 hover:bg-indigo-50"
          >
            ← Assessment
          </Link>
          <button
            type="button"
            disabled={res?.status !== "FINAL" || res?.published}
            onClick={publish}
            className={`${primaryButton} bg-emerald-700 hover:bg-emerald-800`}
          >
            <Send size={14} />
            Publish final marks
          </button>
        </div>
      }
    >
      <ConnectionBar role="faculty" onChange={load} />

      {msg && (
        <p
          role="status"
          className="mb-4 rounded-lg border border-sky-300 bg-sky-50 p-3 text-sm font-medium leading-6 text-sky-950"
        >
          {msg}
        </p>
      )}

      {sub?.status === "FAILED" && (
        <p
          role="alert"
          className="mb-4 rounded-lg border border-rose-300 bg-rose-50 p-3 text-sm leading-6 text-rose-900"
        >
          Processing failed: {sub.error}
        </p>
      )}

      <div className="mb-5 flex flex-wrap gap-2">
        {sub?.responses.map((response, i) => (
          <button
            type="button"
            key={response.id}
            aria-pressed={i === active}
            onClick={() => setActive(i)}
            className={`rounded-lg border px-4 py-2 text-sm font-semibold transition-colors ${i === active
                ? "border-indigo-700 bg-indigo-100 text-indigo-950"
                : "border-slate-300 bg-white text-slate-900 hover:bg-slate-100"
              }`}
          >
            {response.subquestion}{" "}
            {response.reviewed ? "✓" : response.needs_review ? "⚠" : ""}
          </button>
        ))}
      </div>

      {cur ? (
        <ResponsePanel
          key={cur.id + cur.student_text + cur.reviews.length}
          sid={sid}
          r={cur}
          onDone={load}
        />
      ) : sub ? (
        <div className="rounded-xl border border-slate-300 bg-white p-6 text-sm text-slate-800">
          No answer responses are available for this submission yet.
        </div>
      ) : (
        <div className="flex items-center gap-3 py-8 text-sm font-medium text-slate-800">
          <Loader2 size={20} className="animate-spin" />
          Loading submission…
        </div>
      )}
    </AppShell>
  );
}
