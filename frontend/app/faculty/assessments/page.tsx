"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertTriangle, FileUp, Loader2, Plus, Sparkles, Trash2, X } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { Badge, DemoDataBadge, LocalOnlyBadge } from "../../components/ui/Badge";
import { EmptyState } from "../../components/ui/EmptyState";
import { getAssessments, getSubjectById, getSubjects } from "../../lib/repository";
import { newAssessmentId, saveLocalAssessment } from "../../lib/localAssessments";
import { useClientData } from "../../lib/useClientData";
import { ApiError, ingestMaterialDocument, type IngestedQuestion } from "../../lib/api";
import type { Question, RubricCriterion } from "../../lib/domain";

interface DraftQuestion {
  text: string;
  modelAnswer: string;
  maxScore: number;
  topic: string;
  criteria: RubricCriterion[];
  /** Set only for questions that came from document ingestion (B1-B4) --
   * preserves the original extracted question_id (so it lines up with the
   * source document if re-ingested) and surfaces provenance/confidence in
   * the review UI. Absent for manually-typed questions. */
  extracted?: {
    questionId: string;
    mappingConfidence: number;
    sources: string[];
    hasQuestionText: boolean;
    hasModelAnswer: boolean;
  };
}

function defaultCriteria(maxScore: number): RubricCriterion[] {
  const c = (frac: number) => Math.round(maxScore * frac * 10) / 10;
  return [
    { name: "Concept", maxScore: c(0.4) },
    { name: "Accuracy", maxScore: c(0.3) },
    { name: "Precision", maxScore: c(0.2) },
    { name: "Terminology", maxScore: c(0.1) },
  ];
}

function emptyQuestion(): DraftQuestion {
  return { text: "", modelAnswer: "", maxScore: 10, topic: "", criteria: defaultCriteria(10) };
}

/** B3: align a question-paper ingestion with a model-answer ingestion by
 * normalized question_id -- the primary, most reliable alignment strategy
 * per the brief. A question present in only one document is kept (not
 * dropped) with the missing half left blank, and its mapping confidence
 * flagged, so faculty can complete it during review rather than the system
 * silently guessing or silently discarding it. */
function alignIngestedQuestions(
  questionPaper: IngestedQuestion[],
  modelAnswers: IngestedQuestion[],
): DraftQuestion[] {
  const byId = new Map<string, { qp?: IngestedQuestion; ma?: IngestedQuestion }>();
  for (const q of questionPaper) byId.set(q.question_id, { ...byId.get(q.question_id), qp: q });
  for (const q of modelAnswers) byId.set(q.question_id, { ...byId.get(q.question_id), ma: q });

  return Array.from(byId.entries())
    .sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }))
    .map(([questionId, { qp, ma }]) => {
      const maxScore = qp?.max_score ?? ma?.max_score ?? 10;
      const mappingConfidence = Math.min(qp?.mapping_confidence ?? 1, ma?.mapping_confidence ?? 1);
      return {
        text: qp?.question_text ?? "",
        modelAnswer: ma?.model_answer ?? "",
        maxScore,
        topic: "",
        criteria: defaultCriteria(maxScore),
        extracted: {
          questionId,
          mappingConfidence,
          sources: [qp?.source, ma?.source].filter((s): s is string => !!s),
          hasQuestionText: !!qp,
          hasModelAnswer: !!ma,
        },
      };
    });
}

export default function AssessmentsPage() {
  const [creating, setCreating] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const assessments = useClientData(getAssessments, [refreshKey]);
  const sorted = assessments ? [...assessments].sort((a, b) => b.date.localeCompare(a.date)) : undefined;

  return (
    <AppShell
      role="faculty"
      title="Assessments"
      subtitle="Create assessments and track their evaluation status"
      action={
        !creating && (
          <button
            onClick={() => setCreating(true)}
            className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            <Plus size={16} /> New assessment
          </button>
        )
      }
    >
      {creating ? (
        <CreateAssessmentForm
          onCancel={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            setRefreshKey((k) => k + 1);
          }}
        />
      ) : !sorted ? (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </div>
      ) : sorted.length === 0 ? (
        <EmptyState icon={Plus} title="No assessments yet" description="Create your first assessment to get started." />
      ) : (
        <Card>
          <CardHeader title={`${sorted.length} assessment${sorted.length === 1 ? "" : "s"}`} action={<DemoDataBadge />} />
          <CardBody className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-400">
                  <th className="px-6 py-3 font-medium">Title</th>
                  <th className="px-6 py-3 font-medium">Subject</th>
                  <th className="px-6 py-3 font-medium">Date</th>
                  <th className="px-6 py-3 font-medium">Questions</th>
                  <th className="px-6 py-3 font-medium">Marks</th>
                  <th className="px-6 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((a) => {
                  const subject = getSubjectById(a.subjectId);
                  return (
                    <tr key={a.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50/60">
                      <td className="px-6 py-3 font-medium text-slate-800">
                        <Link href={`/faculty/assessments/${a.id}`} className="hover:text-indigo-600 hover:underline">
                          {a.title}
                        </Link>
                      </td>
                      <td className="px-6 py-3 text-slate-500">{subject?.code ?? "—"}</td>
                      <td className="px-6 py-3 text-slate-500">{a.date}</td>
                      <td className="px-6 py-3 text-slate-500">{a.questions.length}</td>
                      <td className="px-6 py-3 text-slate-500">{a.totalMarks}</td>
                      <td className="px-6 py-3">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                            a.status === "published" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {a.status}
                        </span>
                        {a.source === "local" && <LocalOnlyBadge className="ml-2" />}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardBody>
        </Card>
      )}
    </AppShell>
  );
}

function CreateAssessmentForm({ onCancel, onCreated }: { onCancel: () => void; onCreated: () => void }) {
  const subjects = getSubjects();
  const [mode, setMode] = useState<"manual" | "materials">("manual");
  const [title, setTitle] = useState("");
  const [subjectId, setSubjectId] = useState(subjects[0]?.id ?? "");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [questions, setQuestions] = useState<DraftQuestion[]>([emptyQuestion()]);
  const [error, setError] = useState<string | null>(null);

  const totalMarks = questions.reduce((sum, q) => sum + (Number(q.maxScore) || 0), 0);

  const updateQuestion = (idx: number, patch: Partial<DraftQuestion>) =>
    setQuestions((prev) => prev.map((q, i) => (i === idx ? { ...q, ...patch } : q)));

  const updateCriterion = (qIdx: number, cIdx: number, patch: Partial<RubricCriterion>) =>
    setQuestions((prev) =>
      prev.map((q, i) =>
        i === qIdx ? { ...q, criteria: q.criteria.map((c, j) => (j === cIdx ? { ...c, ...patch } : c)) } : q,
      ),
    );

  const submit = () => {
    setError(null);
    if (!title.trim()) return setError("Enter an assessment title.");
    if (!subjectId) return setError("Select a subject.");
    if (questions.some((q) => !q.text.trim() || !q.modelAnswer.trim())) {
      return setError("Every question needs question text and a model answer — check any extracted questions flagged incomplete below.");
    }

    const builtQuestions: Question[] = questions.map((q, i) => ({
      id: q.extracted?.questionId ?? `Q${i + 1}`,
      text: q.text.trim(),
      modelAnswer: q.modelAnswer.trim(),
      maxScore: Number(q.maxScore) || 0,
      topic: q.topic.trim() || q.text.trim().slice(0, 40),
      criteria: q.criteria,
    }));

    saveLocalAssessment({
      id: newAssessmentId(),
      title: title.trim(),
      subjectId,
      date,
      totalMarks,
      questions: builtQuestions,
      status: "draft",
      source: "local",
    });
    onCreated();
  };

  return (
    <Card>
      <CardHeader
        title="New assessment"
        subtitle="Saved to this browser only — see the Local-only note below"
        action={
          <button onClick={onCancel} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
            <X size={18} />
          </button>
        }
      />
      <CardBody className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Title</span>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. NLP — TT3"
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Subject</span>
            <select
              value={subjectId}
              onChange={(e) => setSubjectId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
            >
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} — {s.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Date</span>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
            />
          </label>
        </div>

        <div className="flex gap-2 border-b border-slate-200">
          {(["manual", "materials"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
                mode === m ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {m === "manual" ? "Manual entry" : "Create from materials"}
            </button>
          ))}
        </div>

        {mode === "materials" && (
          <MaterialsIntake onExtracted={(extracted) => setQuestions(extracted)} />
        )}

        <div className="space-y-4">
          {questions.map((q, qi) => (
            <div key={qi} className="rounded-xl border border-slate-200 p-4">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <span className="text-sm font-semibold text-slate-800">
                  {q.extracted?.questionId ?? `Question ${qi + 1}`}
                </span>
                {q.extracted && (
                  <>
                    <Badge variant={q.extracted.mappingConfidence >= 1 ? "live" : "review"}>
                      {q.extracted.mappingConfidence >= 1 ? "Confidently extracted" : "Low-confidence extraction — review"}
                    </Badge>
                    {!q.extracted.hasQuestionText && <Badge variant="danger">No question text found</Badge>}
                    {!q.extracted.hasModelAnswer && <Badge variant="danger">No model answer found</Badge>}
                    <span className="text-xs text-slate-400">Source: {q.extracted.sources.join(", ") || "—"}</span>
                  </>
                )}
                {questions.length > 1 && (
                  <button
                    onClick={() => setQuestions((prev) => prev.filter((_, i) => i !== qi))}
                    className="ml-auto flex items-center gap-1 text-xs font-medium text-rose-600 hover:underline"
                  >
                    <Trash2 size={13} /> Remove
                  </button>
                )}
              </div>
              <div className="grid gap-3">
                <textarea
                  value={q.text}
                  onChange={(e) => updateQuestion(qi, { text: e.target.value })}
                  placeholder="Question text"
                  rows={2}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400"
                />
                <textarea
                  value={q.modelAnswer}
                  onChange={(e) => updateQuestion(qi, { modelAnswer: e.target.value })}
                  placeholder="Model answer"
                  rows={3}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-900 placeholder:font-normal placeholder:text-slate-400"
                />
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <input
                    value={q.topic}
                    onChange={(e) => updateQuestion(qi, { topic: e.target.value })}
                    placeholder="Topic (for learning-gap tracking, optional)"
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400"
                  />
                </div>

                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Rubric criteria
                  </p>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {q.criteria.map((c, ci) => (
                      <div key={ci} className="flex items-center gap-2">
                        <input
                          value={c.name}
                          onChange={(e) => updateCriterion(qi, ci, { name: e.target.value })}
                          className="w-1/2 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900"
                        />
                        <input
                          type="number"
                          min={0}
                          value={c.maxScore}
                          onChange={(e) => updateCriterion(qi, ci, { maxScore: Number(e.target.value) || 0 })}
                          className="w-24 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900"
                        />
                        <span className="text-xs text-slate-400">marks</span>
                      </div>
                    ))}
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    Question max score ={" "}
                    <input
                      type="number"
                      min={0}
                      value={q.maxScore}
                      onChange={(e) => updateQuestion(qi, { maxScore: Number(e.target.value) || 0 })}
                      className="mx-1 w-20 rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-900"
                    />
                    marks (criteria are for the AI evaluator&apos;s reference; they don&apos;t need to sum exactly)
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between">
          <button
            onClick={() => setQuestions((prev) => [...prev, emptyQuestion()])}
            className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <Plus size={15} /> Add question
          </button>
          <p className="text-sm font-medium text-slate-700">Total marks: {totalMarks}</p>
        </div>

        {error && <p className="text-sm text-rose-600">{error}</p>}

        <div className="rounded-lg bg-sky-50 px-4 py-3 text-xs text-sky-800">
          This assessment is saved in your browser&apos;s local storage, not a shared server database — there is no
          persistence layer yet (see the Roadmap page). It will be visible on this device only.
        </div>

        <div className="flex justify-end gap-3">
          <button onClick={onCancel} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700">
            Cancel
          </button>
          <button onClick={submit} className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-700">
            Save assessment
          </button>
        </div>
      </CardBody>
    </Card>
  );
}

/** B1/B2/B3/B4: upload a question paper and/or model-answer document, run
 * them through the real /materials/ingest endpoint, align by question_id,
 * and hand the result to the parent for review/editing -- extraction never
 * publishes anything by itself (B4). */
function MaterialsIntake({ onExtracted }: { onExtracted: (questions: DraftQuestion[]) => void }) {
  const [questionPaperFile, setQuestionPaperFile] = useState<File | null>(null);
  const [modelAnswerFile, setModelAnswerFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<string | null>(null);

  const extract = async () => {
    if (!modelAnswerFile && !questionPaperFile) return;
    setLoading(true);
    setError(null);
    setSummary(null);
    try {
      const [qp, ma] = await Promise.all([
        questionPaperFile ? ingestMaterialDocument(questionPaperFile, "question_paper") : Promise.resolve(null),
        modelAnswerFile ? ingestMaterialDocument(modelAnswerFile, "model_answer") : Promise.resolve(null),
      ]);
      const aligned = alignIngestedQuestions(qp?.questions ?? [], ma?.questions ?? []);
      if (aligned.length === 0) {
        setError("No questions could be detected in the uploaded document(s). You can still add questions manually below.");
        return;
      }
      onExtracted(aligned);
      const lowConfidence = aligned.filter((q) => (q.extracted?.mappingConfidence ?? 1) < 1).length;
      setSummary(
        `Extracted ${aligned.length} question${aligned.length === 1 ? "" : "s"}` +
          (lowConfidence > 0 ? ` — ${lowConfidence} need review (low-confidence extraction).` : ". Review below before saving."),
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Document ingestion failed. Please try again later.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50/60 p-4">
      <p className="text-sm text-slate-600">
        Upload your question paper and/or approved model answers (PDF, DOCX or TXT). Extracted questions appear below
        for you to review and edit — nothing is saved until you click <span className="font-medium">Save assessment</span>.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <FileSlot label="Question paper (optional)" file={questionPaperFile} onChange={setQuestionPaperFile} />
        <FileSlot label="Model answers" file={modelAnswerFile} onChange={setModelAnswerFile} />
      </div>
      <button
        onClick={extract}
        disabled={loading || (!questionPaperFile && !modelAnswerFile)}
        className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
      >
        {loading ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
        {loading ? "Extracting…" : "Extract questions"}
      </button>
      {error && (
        <p className="flex items-center gap-2 text-sm text-rose-600">
          <AlertTriangle size={15} /> {error}
        </p>
      )}
      {summary && <p className="text-sm text-emerald-700">{summary}</p>}
      <p className="text-xs text-slate-500">
        This calls the real <code className="rounded bg-slate-100 px-1 py-0.5">/materials/ingest</code> endpoint
        (PaddleOCR-free text extraction + the same question-detection used by the handwritten pipeline). Marks are
        only filled in when the document states them explicitly (e.g. &quot;[10 marks]&quot;) — otherwise you set
        them below.
      </p>
    </div>
  );
}

function FileSlot({ label, file, onChange }: { label: string; file: File | null; onChange: (f: File | null) => void }) {
  return (
    <label className="flex cursor-pointer flex-col gap-1">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <span className="flex items-center gap-2 rounded-lg border-2 border-dashed border-slate-300 bg-white px-3 py-3 text-sm text-slate-600 hover:border-indigo-300 hover:bg-indigo-50/40">
        <FileUp size={16} className="shrink-0 text-indigo-500" />
        <span className="truncate">{file ? file.name : "Choose a file (.pdf, .docx, .txt)"}</span>
      </span>
      <input
        type="file"
        accept=".pdf,.docx,.txt"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onChange(f);
        }}
      />
    </label>
  );
}
