'use client';

import { useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface QuestionInput {
  question_id: string;
  question: string;
  model_answer: string;
  max_score: number;
}

interface QuestionResult {
  question_id: string;
  student_answer: string;
  answer_detected: boolean;
  score: number;
  max_score: number;
  strengths: string[];
  missing_concepts: string[];
  feedback: string;
  confidence: number;
  ocr_confidence: number;
  combined_confidence: number;
  needs_review: boolean;
}

interface PipelineResponse {
  extracted_text: string;
  ocr_confidence: number;
  ocr_engine: string;
  results: QuestionResult[];
  total_score: number;
  total_max_score: number;
  overall_confidence: number;
  needs_review: boolean;
}

const emptyQuestion = (n: number): QuestionInput => ({
  question_id: `Q${n}`,
  question: '',
  model_answer: '',
  max_score: 10,
});

export default function HandwrittenEvaluation() {
  const [image, setImage] = useState<File | null>(null);
  const [questions, setQuestions] = useState<QuestionInput[]>([emptyQuestion(1)]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineResponse | null>(null);

  const updateQuestion = (index: number, patch: Partial<QuestionInput>) =>
    setQuestions((prev) => prev.map((q, i) => (i === index ? { ...q, ...patch } : q)));

  const submit = async () => {
    if (!image) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const form = new FormData();
      form.append('image', image);
      form.append(
        'questions',
        JSON.stringify(
          questions.map((q) => ({
            question_id: q.question_id,
            question: q.question,
            model_answer: q.model_answer,
            max_score: q.max_score,
            rubric: { max_score: q.max_score },
          }))
        )
      );
      const res = await fetch(`${API_URL}/handwritten/evaluate`, { method: 'POST', body: form });
      const body = await res.json();
      if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail));
      setResult(body as PipelineResponse);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  const pct = (v: number) => `${Math.round(v * 100)}%`;

  return (
    <div className="bg-white rounded-xl shadow-md p-8">
      <h2 className="text-2xl font-bold text-slate-900 mb-2">Evaluate Handwritten Answer Sheet</h2>
      <p className="text-slate-600 mb-6">
        Image → PaddleOCR → question-wise segmentation → AI evaluation
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Answer sheet image</span>
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setImage(e.target.files?.[0] ?? null)}
              className="mt-1 block w-full text-sm text-slate-600"
            />
          </label>

          {questions.map((q, i) => (
            <div key={i} className="border border-slate-200 rounded-lg p-4 space-y-2">
              <div className="flex gap-2">
                <input
                  value={q.question_id}
                  onChange={(e) => updateQuestion(i, { question_id: e.target.value })}
                  className="w-20 border rounded px-2 py-1 text-sm"
                  placeholder="Q1"
                />
                <input
                  type="number"
                  min={1}
                  value={q.max_score}
                  onChange={(e) => updateQuestion(i, { max_score: Number(e.target.value) || 1 })}
                  className="w-24 border rounded px-2 py-1 text-sm"
                  placeholder="Marks"
                />
                {questions.length > 1 && (
                  <button
                    type="button"
                    onClick={() => setQuestions((prev) => prev.filter((_, j) => j !== i))}
                    className="ml-auto text-red-500 text-sm"
                  >
                    Remove
                  </button>
                )}
              </div>
              <textarea
                value={q.question}
                onChange={(e) => updateQuestion(i, { question: e.target.value })}
                className="w-full border rounded px-2 py-1 text-sm"
                rows={2}
                placeholder="Question text"
              />
              <textarea
                value={q.model_answer}
                onChange={(e) => updateQuestion(i, { model_answer: e.target.value })}
                className="w-full border rounded px-2 py-1 text-sm"
                rows={3}
                placeholder="Model answer"
              />
            </div>
          ))}

          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setQuestions((prev) => [...prev, emptyQuestion(prev.length + 1)])}
              className="px-4 py-2 border border-slate-300 rounded-lg text-sm"
            >
              + Add question
            </button>
            <button
              type="button"
              disabled={!image || loading}
              onClick={submit}
              className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 text-sm font-medium"
            >
              {loading ? 'Evaluating…' : 'Evaluate'}
            </button>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>

        <div>
          {result ? (
            <div className="space-y-4">
              <div className="flex items-baseline gap-4">
                <span className="text-3xl font-bold text-slate-900">
                  {result.total_score} / {result.total_max_score}
                </span>
                <span className="text-sm text-slate-600">
                  confidence {pct(result.overall_confidence)} · OCR {pct(result.ocr_confidence)}
                </span>
                {result.needs_review && (
                  <span className="text-xs px-2 py-1 rounded bg-amber-100 text-amber-800">needs review</span>
                )}
              </div>

              <details className="border border-slate-200 rounded-lg p-3">
                <summary className="text-sm font-medium cursor-pointer">Extracted text ({result.ocr_engine})</summary>
                <pre className="mt-2 text-xs whitespace-pre-wrap text-slate-700">{result.extracted_text}</pre>
              </details>

              {result.results.map((r) => (
                <div key={r.question_id} className="border border-slate-200 rounded-lg p-4 space-y-2">
                  <div className="flex items-center gap-3">
                    <span className="font-semibold text-slate-900">{r.question_id}</span>
                    <span className="text-lg font-bold">
                      {r.score} / {r.max_score}
                    </span>
                    <span className="text-xs text-slate-500">confidence {pct(r.combined_confidence)}</span>
                    {r.needs_review && (
                      <span className="text-xs px-2 py-0.5 rounded bg-amber-100 text-amber-800">review</span>
                    )}
                    {!r.answer_detected && (
                      <span className="text-xs px-2 py-0.5 rounded bg-red-100 text-red-800">no answer found</span>
                    )}
                  </div>
                  <p className="text-sm text-slate-700">{r.feedback}</p>
                  {r.strengths.length > 0 && (
                    <div className="text-sm">
                      <span className="font-medium text-green-700">Strengths:</span>{' '}
                      {r.strengths.join('; ')}
                    </div>
                  )}
                  {r.missing_concepts.length > 0 && (
                    <div className="text-sm">
                      <span className="font-medium text-red-700">Missing concepts:</span>{' '}
                      {r.missing_concepts.join('; ')}
                    </div>
                  )}
                  {r.student_answer && (
                    <details>
                      <summary className="text-xs text-slate-500 cursor-pointer">Student answer (OCR)</summary>
                      <pre className="mt-1 text-xs whitespace-pre-wrap text-slate-600">{r.student_answer}</pre>
                    </details>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="h-full min-h-40 border-2 border-dashed border-slate-200 rounded-lg flex items-center justify-center text-sm text-slate-400">
              Results will appear here
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
