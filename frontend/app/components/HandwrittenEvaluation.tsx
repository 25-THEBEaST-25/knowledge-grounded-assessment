"use client";

import { useRef, useState } from "react";
import { AlertTriangle, FileUp, Loader2, RotateCcw, Sparkles, X } from "lucide-react";
import { ApiError, evaluateHandwrittenAnswerSheet, type PipelineResponse } from "../lib/api";
import { StepProgress, type Step } from "./ui/StepProgress";
import { ScoreBar } from "./ui/ScoreBar";

interface QuestionInput {
  question_id: string;
  question: string;
  model_answer: string;
  max_score: number;
}

const emptyQuestion = (n: number): QuestionInput => ({
  question_id: `Q${n}`,
  question: "",
  model_answer: "",
  max_score: 10,
});

type Phase = "idle" | "uploading" | "ocr" | "segmenting" | "evaluating" | "done" | "error";

function stepsFor(phase: Phase): Step[] {
  const order: { key: string; label: string }[] = [
    { key: "upload", label: "Upload" },
    { key: "ocr", label: "OCR" },
    { key: "segment", label: "Segmentation" },
    { key: "evaluate", label: "AI evaluation" },
    { key: "results", label: "Results" },
  ];
  const activeIndex = { idle: -1, uploading: 0, ocr: 1, segmenting: 2, evaluating: 3, done: 4, error: -1 }[phase];
  return order.map((s, i) => ({
    ...s,
    state: phase === "error" ? "pending" : i < activeIndex ? "done" : i === activeIndex ? "active" : "pending",
  }));
}

export default function HandwrittenEvaluation() {
  const [image, setImage] = useState<File | null>(null);
  const [questions, setQuestions] = useState<QuestionInput[]>([emptyQuestion(1)]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineResponse | null>(null);
  // Synchronous guard against duplicate/overlapping requests: the `busy`
  // state-derived `disabled` prop on the buttons has a render-timing race
  // (a fast double-click can fire twice before React re-renders with the
  // "uploading" phase), so this is checked and set immediately, before any
  // state update or await.
  const submittingRef = useRef(false);

  const updateQuestion = (index: number, patch: Partial<QuestionInput>) =>
    setQuestions((prev) => prev.map((q, i) => (i === index ? { ...q, ...patch } : q)));

  const submit = async () => {
    if (!image || submittingRef.current) return;
    submittingRef.current = true;
    setError(null);
    setResult(null);
    setPhase("uploading");

    // The backend runs OCR -> segmentation -> evaluation as one call; these
    // intermediate phases are a UI-only pacing of the same real request
    // (not separate backend round-trips) so the flow named in Part 10 is
    // visible instead of one opaque spinner.
    const ocrTimer = setTimeout(() => setPhase("ocr"), 300);
    const segTimer = setTimeout(() => setPhase("segmenting"), 900);
    const evalTimer = setTimeout(() => setPhase("evaluating"), 1500);

    try {
      const payload = questions.map((q) => ({
        question_id: q.question_id,
        question: q.question,
        model_answer: q.model_answer,
        rubric: { max_score: q.max_score },
      }));
      const body = await evaluateHandwrittenAnswerSheet(image, payload);
      setResult(body);
      setPhase("done");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Evaluation failed. Please try again later.");
      setPhase("error");
    } finally {
      clearTimeout(ocrTimer);
      clearTimeout(segTimer);
      clearTimeout(evalTimer);
      submittingRef.current = false;
    }
  };

  const pct = (v: number) => `${Math.round(v * 100)}%`;
  const busy = phase !== "idle" && phase !== "done" && phase !== "error";

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-4">
        {image ? (
          <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
            <div className="flex items-center gap-2 text-sm text-slate-700">
              <FileUp size={16} className="text-indigo-500" />
              <span className="font-medium">{image.name}</span>
              <span className="text-xs text-slate-400">({(image.size / 1024).toFixed(0)} KB)</span>
            </div>
            <div className="flex items-center gap-3">
              <label className="cursor-pointer text-xs font-medium text-indigo-600 hover:underline">
                Replace
                <input type="file" accept="image/*" className="hidden" onChange={(e) => {
                  // Only replace the current selection with an actual new
                  // file. If the picker was cancelled, `files` is empty --
                  // the existing image (and its results) must stay intact,
                  // not be silently cleared.
                  const file = e.target.files?.[0];
                  if (file) setImage(file);
                }} />
              </label>
              <button onClick={() => setImage(null)} className="text-slate-400 hover:text-slate-600">
                <X size={15} />
              </button>
            </div>
          </div>
        ) : (
          <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border-2 border-dashed border-slate-300 px-4 py-8 text-sm font-medium text-slate-600 hover:border-indigo-300 hover:bg-indigo-50/40">
            <FileUp size={18} />+ Add Answer Sheet Image
            <input type="file" accept="image/*" className="hidden" onChange={(e) => {
                  // Only replace the current selection with an actual new
                  // file. If the picker was cancelled, `files` is empty --
                  // the existing image (and its results) must stay intact,
                  // not be silently cleared.
                  const file = e.target.files?.[0];
                  if (file) setImage(file);
                }} />
          </label>
        )}

        {questions.map((q, i) => (
          <div key={i} className="rounded-lg border border-slate-200 p-4 space-y-2">
            <div className="flex gap-2">
              <input
                value={q.question_id}
                onChange={(e) => updateQuestion(i, { question_id: e.target.value })}
                className="w-20 rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 placeholder:text-slate-400"
                placeholder="Q1"
              />
              <input
                type="number"
                min={1}
                value={q.max_score}
                onChange={(e) => updateQuestion(i, { max_score: Number(e.target.value) || 1 })}
                className="w-24 rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 placeholder:text-slate-400"
                placeholder="Marks"
              />
              {questions.length > 1 && (
                <button
                  type="button"
                  onClick={() => setQuestions((prev) => prev.filter((_, j) => j !== i))}
                  className="ml-auto text-sm text-rose-500 hover:underline"
                >
                  Remove
                </button>
              )}
            </div>
            <textarea
              value={q.question}
              onChange={(e) => updateQuestion(i, { question: e.target.value })}
              className="w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-sm leading-relaxed text-slate-900 placeholder:text-slate-400"
              rows={2}
              placeholder="Question text"
            />
            <textarea
              value={q.model_answer}
              onChange={(e) => updateQuestion(i, { model_answer: e.target.value })}
              className="w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-sm font-medium leading-relaxed text-slate-900 placeholder:font-normal placeholder:text-slate-400"
              rows={3}
              placeholder="Model answer"
            />
          </div>
        ))}

        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => setQuestions((prev) => [...prev, emptyQuestion(prev.length + 1)])}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            + Add question
          </button>
          <button
            type="button"
            disabled={!image || busy}
            onClick={submit}
            className="flex items-center gap-2 rounded-lg bg-indigo-600 px-6 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            <Sparkles size={15} />
            {busy ? "Evaluating…" : "Evaluate"}
          </button>
        </div>

        {(busy || phase === "done" || phase === "error") && (
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
            <StepProgress steps={stepsFor(phase)} />
          </div>
        )}

        {error && (
          <div className="flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3">
            <AlertTriangle size={16} className="mt-0.5 shrink-0 text-rose-500" />
            <div className="flex-1">
              <p className="text-sm font-medium text-rose-800">{error}</p>
              <p className="mt-0.5 text-xs text-rose-600">
                Your uploaded image and question details are unchanged — retrying will re-run the same evaluation,
                no need to upload again.
              </p>
            </div>
            <button
              type="button"
              onClick={submit}
              disabled={busy}
              className="flex shrink-0 items-center gap-1.5 rounded-lg border border-rose-300 bg-white px-3 py-1.5 text-xs font-medium text-rose-700 hover:bg-rose-100 disabled:opacity-50"
            >
              {busy ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />}
              {busy ? "Retrying…" : "Retry Evaluation"}
            </button>
          </div>
        )}
      </div>

      <div>
        {result ? (
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
                <span className="text-3xl font-bold text-slate-900">
                  {result.total_score} / {result.total_max_score}
                </span>
                <span className="text-sm text-slate-500">
                  Confidence {pct(result.overall_confidence)} · OCR {pct(result.ocr_confidence)}
                </span>
                {result.needs_review && (
                  <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-medium text-amber-800">
                    Needs review
                  </span>
                )}
              </div>
              <ScoreBar
                percent={result.total_max_score > 0 ? (result.total_score / result.total_max_score) * 100 : 0}
                className="mt-3"
              />
            </div>

            <details className="rounded-xl border border-slate-200 bg-slate-50">
              <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-slate-800">
                Extracted OCR text ({result.ocr_engine})
              </summary>
              <pre className="whitespace-pre-wrap border-t border-slate-200 bg-white px-4 py-3 text-sm leading-relaxed text-slate-800">
                {result.extracted_text || "(no text extracted)"}
              </pre>
            </details>

            {result.results.map((r) => {
              const p = r.max_score > 0 ? (r.score / r.max_score) * 100 : 0;
              return (
                <div key={r.question_id} className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-slate-900">{r.question_id}</span>
                    <span className="text-lg font-bold text-slate-900">
                      {r.score} / {r.max_score}
                    </span>
                    <ScoreBar percent={p} className="w-24" />
                    <span className="text-xs text-slate-500">
                      OCR {pct(r.ocr_confidence)} · eval {pct(r.confidence)} · combined {pct(r.combined_confidence)}
                    </span>
                    {r.needs_review && (
                      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">review</span>
                    )}
                    {r.ocr_uncertain && (
                      <span
                        className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800"
                        title="Low OCR confidence, an uncertain question mapping, or a suspiciously short answer -- not penalized, flagged for a human look."
                      >
                        OCR uncertain
                      </span>
                    )}
                    {r.visual_fallback_used && (
                      <span
                        className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-800"
                        title="OCR confidence was low, so the answer-region image (not just OCR text) was also sent to the evaluator."
                      >
                        image-assisted
                      </span>
                    )}
                    {!r.answer_detected && (
                      <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-800">no answer found</span>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                    <SubScore label="Concept" value={r.concept_score} />
                    <SubScore label="Accuracy" value={r.accuracy_score} />
                    <SubScore label="Precision" value={r.precision_score} />
                    <SubScore label="Terminology" value={r.technical_terminology_score} />
                  </div>

                  <p className="text-sm font-medium text-slate-800">{r.feedback}</p>
                  {r.strengths.length > 0 && (
                    <p className="text-sm text-slate-700">
                      <span className="font-semibold text-emerald-700">Strengths: </span>
                      {r.strengths.join("; ")}
                    </p>
                  )}
                  {r.missing_concepts.length > 0 && (
                    <p className="text-sm text-slate-700">
                      <span className="font-semibold text-rose-700">Missing concepts: </span>
                      {r.missing_concepts.join("; ")}
                    </p>
                  )}
                  {r.student_answer && (
                    <details>
                      <summary className="cursor-pointer text-xs font-semibold text-slate-600">
                        Student answer (OCR)
                      </summary>
                      <pre className="mt-1 whitespace-pre-wrap rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-relaxed text-slate-800">
                        {r.student_answer}
                      </pre>
                    </details>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="flex h-full min-h-[16rem] items-center justify-center rounded-xl border-2 border-dashed border-slate-200 text-sm text-slate-400">
            Results will appear here
          </div>
        )}
      </div>
    </div>
  );
}

function SubScore({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-slate-50 px-2 py-1.5 text-center">
      <p className="font-semibold text-slate-800">{value}</p>
      <p className="text-slate-500">{label}</p>
    </div>
  );
}
