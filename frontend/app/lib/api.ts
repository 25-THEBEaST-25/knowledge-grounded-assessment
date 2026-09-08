/**
 * The one real backend integration in this project: the handwritten
 * evaluation pipeline (image -> PaddleOCR -> segmentation -> Gemini
 * evaluation). Used by both the standalone Answer Evaluation tool
 * (`/faculty/evaluate`) and the assessment workflow
 * (`/faculty/assessments/[id]`) -- one implementation, not two, per Part 23.
 */

import type { Question } from "./domain";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface PipelineQuestionResult {
  question_id: string;
  student_answer: string;
  answer_detected: boolean;
  score: number;
  max_score: number;
  concept_score: number;
  accuracy_score: number;
  precision_score: number;
  technical_terminology_score: number;
  strengths: string[];
  missing_concepts: string[];
  feedback: string;
  confidence: number;
  ocr_confidence: number;
  combined_confidence: number;
  needs_review: boolean;
  mapping_confidence: number;
  ocr_uncertain: boolean;
  visual_fallback_used: boolean;
}

export interface PipelineResponse {
  extracted_text: string;
  ocr_confidence: number;
  ocr_engine: string;
  results: PipelineQuestionResult[];
  total_score: number;
  total_max_score: number;
  overall_confidence: number;
  needs_review: boolean;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** Maps a raw backend failure into the safe, user-facing copy required by
 * Part 24 -- never a stack trace, provider name, or filesystem path. */
function friendlyMessage(status: number, detail: string): string {
  if (status === 503) {
    return detail.toLowerCase().includes("ocr") || detail.toLowerCase().includes("paddle")
      ? "Handwriting recognition is temporarily unavailable. Please try again shortly."
      : "AI evaluation is temporarily unavailable. Please try again shortly.";
  }
  if (status === 413) return "Image exceeds the 15 MB upload limit.";
  if (status === 415 || status === 400) return "Please upload a valid image (JPEG/PNG) under the supported size limit.";
  if (status === 422) return "Please check the question details and try again.";
  return "Evaluation failed. Please try again later.";
}

export interface QuestionPayload {
  question_id: string;
  question: string;
  model_answer: string;
  rubric: Record<string, unknown>;
}

export async function evaluateHandwrittenAnswerSheet(
  image: File,
  questions: QuestionPayload[],
): Promise<PipelineResponse> {
  const form = new FormData();
  form.append("image", image);
  form.append("questions", JSON.stringify(questions));

  let res: Response;
  try {
    res = await fetch(`${API_URL}/handwritten/evaluate`, { method: "POST", body: form });
  } catch {
    throw new ApiError(0, "Could not reach the backend API. Is it running?");
  }

  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, friendlyMessage(res.status, detail));
  }

  return res.json();
}

// ---------------------------------------------------------------------------
// Faculty material ingestion (B1/B2) -- the other real backend integration.
// ---------------------------------------------------------------------------

export interface IngestedQuestion {
  question_id: string;
  question_text: string;
  model_answer: string;
  max_score: number | null;
  source: string;
  mapping_confidence: number;
  detected: boolean;
}

export interface MaterialIngestionResponse {
  questions: IngestedQuestion[];
  raw_text_preview: string;
  extraction_engine: string;
}

function friendlyIngestionMessage(status: number, detail: string): string {
  if (status === 400) return detail || "This document could not be read. Please check the file and try again.";
  if (status === 413) return "File exceeds the 15 MB upload limit.";
  if (status === 422) return detail || "Please check the upload details and try again.";
  return "Document ingestion failed. Please try again later.";
}

export async function ingestMaterialDocument(
  file: File,
  kind: "question_paper" | "model_answer",
): Promise<MaterialIngestionResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("kind", kind);

  let res: Response;
  try {
    res = await fetch(`${API_URL}/materials/ingest`, { method: "POST", body: form });
  } catch {
    throw new ApiError(0, "Could not reach the backend API. Is it running?");
  }

  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, friendlyIngestionMessage(res.status, detail));
  }

  return res.json();
}

export function questionToPayload(q: Pick<Question, "id" | "text" | "modelAnswer" | "maxScore" | "criteria">) {
  return {
    question_id: q.id,
    question: q.text,
    model_answer: q.modelAnswer,
    rubric: {
      max_score: q.maxScore,
      criteria: Object.fromEntries(q.criteria.map((c) => [c.name.toLowerCase(), c.maxScore])),
    },
  };
}
