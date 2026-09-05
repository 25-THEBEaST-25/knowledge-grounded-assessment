"use client";

import { useState } from "react";
import Link from "next/link";
import { Loader2, Plus, Trash2, X } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { DemoDataBadge, LocalOnlyBadge } from "../../components/ui/Badge";
import { EmptyState } from "../../components/ui/EmptyState";
import { getAssessments, getSubjectById, getSubjects } from "../../lib/repository";
import { newAssessmentId, saveLocalAssessment } from "../../lib/localAssessments";
import { useClientData } from "../../lib/useClientData";
import type { Question, RubricCriterion } from "../../lib/domain";

interface DraftQuestion {
  text: string;
  modelAnswer: string;
  maxScore: number;
  topic: string;
  criteria: RubricCriterion[];
}

function emptyQuestion(): DraftQuestion {
  return {
    text: "",
    modelAnswer: "",
    maxScore: 10,
    topic: "",
    criteria: [
      { name: "Concept", maxScore: 4 },
      { name: "Accuracy", maxScore: 3 },
      { name: "Precision", maxScore: 2 },
      { name: "Terminology", maxScore: 1 },
    ],
  };
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
      return setError("Every question needs question text and a model answer.");
    }

    const builtQuestions: Question[] = questions.map((q, i) => ({
      id: `Q${i + 1}`,
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
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Subject</span>
            <select
              value={subjectId}
              onChange={(e) => setSubjectId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
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
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
        </div>

        <div className="space-y-4">
          {questions.map((q, qi) => (
            <div key={qi} className="rounded-xl border border-slate-200 p-4">
              <div className="mb-3 flex items-center justify-between">
                <span className="text-sm font-semibold text-slate-800">Question {qi + 1}</span>
                {questions.length > 1 && (
                  <button
                    onClick={() => setQuestions((prev) => prev.filter((_, i) => i !== qi))}
                    className="flex items-center gap-1 text-xs font-medium text-rose-600 hover:underline"
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
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
                <textarea
                  value={q.modelAnswer}
                  onChange={(e) => updateQuestion(qi, { modelAnswer: e.target.value })}
                  placeholder="Model answer"
                  rows={3}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <input
                    value={q.topic}
                    onChange={(e) => updateQuestion(qi, { topic: e.target.value })}
                    placeholder="Topic (for learning-gap tracking, optional)"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
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
                          className="w-1/2 rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        />
                        <input
                          type="number"
                          min={0}
                          value={c.maxScore}
                          onChange={(e) => updateCriterion(qi, ci, { maxScore: Number(e.target.value) || 0 })}
                          className="w-24 rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
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
                      className="mx-1 w-20 rounded border border-slate-300 px-2 py-1 text-xs"
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
