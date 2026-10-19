
/**
 * The one real backend integration in this project: the handwritten
 * evaluation pipeline (image -> PaddleOCR -> segmentation -> Gemini
 * evaluation). Used by both the standalone Answer Evaluation tool
 * (`/faculty/evaluate`) and the assessment workflow
 * (`/faculty/assessments/[id]`) -- one implementation, not two, per Part 23.
 *
 * Supports both single-page and multi-page answer-sheet uploads.
 */

import type { Question } from "./domain";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface CriterionScoreResult {
  criterion_name: string;
  max_score: number;
  awarded_score: number;
  attainment_factor: number;
  reasoning: string;
  evaluator_name: string;
  evidence_used: string[];
  verified_evidence: boolean;
}

export interface SourceReference {
  source_file: string;
  document_type: string;
  excerpt: string;
  relevance_score: number;
  page?: number | null;
  section?: string | null;
  question_id?: string | null;
}

export interface EvaluationTrace {
  trace_id: string;
  timestamp: string;
  question_id: string;
  routing_reasons: Record<string, string>;
  evaluators_run: string[];
  evaluators_failed: string[];
  retrieval_sources: SourceReference[];
  criteria_breakdown: CriterionScoreResult[];
  review_flags: string[];
  execution_time_ms: number;
}

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
  criteria_breakdown?: CriterionScoreResult[];
  evaluation_trace?: EvaluationTrace;
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
    this.name = "ApiError";
    this.status = status;
  }
}

/** Maps a raw backend failure into safe, user-facing copy. */
function friendlyMessage(status: number, detail: string): string {
  if (status === 503) {
    return detail.toLowerCase().includes("ocr") ||
      detail.toLowerCase().includes("paddle")
      ? "Handwriting recognition is temporarily unavailable. Please try again shortly."
      : "AI evaluation is temporarily unavailable. Please try again shortly.";
  }

  if (status === 413) {
    return "The uploaded file exceeds the permitted size limit.";
  }

  if (status === 415 || status === 400) {
    return "Please upload a valid image (JPEG/PNG) under the supported size limit.";
  }

  if (status === 422) {
    return "Please check the question details and try again.";
  }

  return "Evaluation failed. Please try again later.";
}

export interface QuestionPayload {
  question_id: string;
  question: string;
  model_answer: string;
  rubric: Record<string, unknown>;
  assessment_id?: string;
}

/**
 * Evaluates an answer sheet containing one or multiple page images.
 *
 * Pages are appended in the order supplied. The backend must accept
 * repeated multipart fields named "images" and combine their OCR text
 * before question segmentation.
 */
export async function evaluateHandwrittenAnswerSheet(
  images: File | File[],
  questions: QuestionPayload[],
): Promise<PipelineResponse> {
  const pages = Array.isArray(images) ? images : [images];

  if (pages.length === 0) {
    throw new ApiError(400, "Please upload at least one answer-sheet page.");
  }

  if (pages.some((page) => !(page instanceof File))) {
    throw new ApiError(400, "Please upload valid answer-sheet images.");
  }

  if (
    pages.some(
      (page) =>
        !page.type.startsWith("image/") ||
        page.size === 0
    )
  ) {
    throw new ApiError(
      400,
      "Every answer-sheet page must be a non-empty image file.",
    );
  }

  if (questions.length === 0) {
    throw new ApiError(422, "Please provide at least one question to evaluate.");
  }

  const form = new FormData();

  // Repeated "images" fields preserve page order in the multipart request.
  for (const page of pages) {
    form.append("images", page, page.name);
  }

  form.append("questions", JSON.stringify(questions));

  let res: Response;

  try {
    res = await fetch(`${API_URL}/handwritten/evaluate`, {
      method: "POST",
      body: form,
    });
  } catch {
    throw new ApiError(
      0,
      "Could not reach the backend API. Is it running?",
    );
  }

  if (!res.ok) {
    let detail = "";

    try {
      const body = await res.json();
      detail =
        typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail);
    } catch {
      detail = res.statusText;
    }

    throw new ApiError(
      res.status,
      friendlyMessage(res.status, detail),
    );
  }

  return (await res.json()) as PipelineResponse;
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

function friendlyIngestionMessage(
  status: number,
  detail: string,
): string {
  if (status === 400) {
    return (
      detail ||
      "This document could not be read. Please check the file and try again."
    );
  }

  if (status === 413) {
    return "File exceeds the 15 MB upload limit.";
  }

  if (status === 422) {
    return detail || "Please check the upload details and try again.";
  }

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
    res = await fetch(`${API_URL}/materials/ingest`, {
      method: "POST",
      body: form,
    });
  } catch {
    throw new ApiError(
      0,
      "Could not reach the backend API. Is it running?",
    );
  }

  if (!res.ok) {
    let detail = "";

    try {
      const body = await res.json();
      detail =
        typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail);
    } catch {
      detail = res.statusText;
    }

    throw new ApiError(
      res.status,
      friendlyIngestionMessage(res.status, detail),
    );
  }

  return (await res.json()) as MaterialIngestionResponse;
}

export function questionToPayload(
  q: Pick<
    Question,
    "id" | "text" | "modelAnswer" | "maxScore" | "criteria"
  >,
  assessmentId?: string,
): QuestionPayload {
  return {
    question_id: q.id,
    question: q.text,
    model_answer: q.modelAnswer,
    rubric: {
      max_score: q.maxScore,
      criteria: Object.fromEntries(
        q.criteria.map((criterion) => [
          criterion.name.toLowerCase(),
          criterion.maxScore,
        ]),
      ),
    },
    assessment_id: assessmentId,
  };
}
