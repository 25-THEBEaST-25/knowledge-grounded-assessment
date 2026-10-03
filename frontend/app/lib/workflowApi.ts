/**
 * Client for the REAL assessment-workflow backend (/assessments, /submissions, /responses).
 * Auth is a per-role API key + a self-declared reviewer name / roll number, stored in this
 * browser's localStorage (demo-grade; see backend/app/api/auth.py). Nothing here is demo data.
 */
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const KEY = "snaptix.conn.v1";

export interface Conn {
  facultyKey: string;
  reviewer: string;
  studentKey: string;
  roll: string;
}

export function loadConn(): Conn {
  const empty: Conn = { facultyKey: "", reviewer: "Faculty", studentKey: "", roll: "" };
  if (typeof window === "undefined") return empty;
  try {
    return { ...empty, ...JSON.parse(window.localStorage.getItem(KEY) ?? "{}") };
  } catch {
    return empty;
  }
}

export function saveConn(c: Conn): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(c));
  } catch {
    /* storage unavailable: the session just won't be remembered */
  }
}

export class WorkflowError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type Role = "faculty" | "student";

function headers(role: Role): Record<string, string> {
  const c = loadConn();
  return role === "faculty"
    ? { Authorization: `Bearer ${c.facultyKey}`, "X-Reviewer": c.reviewer || "Faculty" }
    : { Authorization: `Bearer ${c.studentKey}`, "X-Student-Roll": c.roll };
}

async function call<T>(role: Role, path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers: { ...headers(role), ...(init.headers ?? {}) } });
  } catch {
    throw new WorkflowError(0, "Cannot reach the backend. Is it running and is NEXT_PUBLIC_API_URL correct?");
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    const msg =
      res.status === 401 ? "Not authorised: check your API key in the connection bar."
      : res.status === 503 ? detail || "Service unavailable."
      : detail || `Request failed (${res.status}).`;
    throw new WorkflowError(res.status, msg);
  }
  return (await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export interface Criterion { code?: string; description: string; max_marks: number; partial_credit: boolean }
export interface Item {
  id: string; full_id: string; text: string; max_marks: number | null; approved: boolean; issues: string[];
  model_answer: string | null; rubric: Criterion[] | null;
}
export interface DocRow { id?: string; kind: string; filename: string; approved: boolean; version: number; index_status: string }
export interface AssessmentDetail { id: string; title: string; status: string; subject: string; items: Item[]; documents: DocRow[] }
export interface AssessmentRow { id: string; title: string; status: string; subject: string; is_demo: boolean }
export interface Dashboard {
  assessment: { id: string; title: string; status: string; subject: string; is_demo: boolean };
  documents: DocRow[];
  submissions: { id: string; roll_no: string; name: string; filename: string; status: string; error: string | null }[];
  submissions_by_status: Record<string, number>;
  question_progress: Record<string, { responses: number; evaluated: number; reviewed: number; needs_review: number }>;
  review_queue: { response_id: string; submission_id: string; roll_no: string; subquestion: string; reasons: string[] }[];
  results: { submission_id: string; roll_no: string; name: string; ai_total: number; final_total: number | null; max_total: number; status: string; published: boolean }[];
}
export interface CriterionView {
  code: string; description: string; max_marks: number; awarded: number | null; flags: string[];
  evidence: { status: string; text: string; confidence: number; source_refs: string[] } | null;
}
export interface ResponseView {
  id: string; subquestion: string; question_text: string; model_answer: string | null; student_text: string;
  detected: boolean; extraction_edited: boolean; needs_review: boolean; review_reasons: string[];
  region_ref: { regions?: { page: number; bbox: number[] }[] };
  ocr_confidence: number; mapping_confidence: number; evaluator_confidence: number; overall_confidence: number;
  confidence_band: string; ai_marks: number; max_marks: number; final_marks: number | null; reviewed: boolean;
  criteria: CriterionView[];
  plan: { id: string; type: string; status: string; tasks: { evaluator: string; status: string; reason: string; attempts: number; error: string | null }[] } | null;
  retrieval: { status: string; sources: { ref: string; source: string; doc_type: string; scope: string; score: number }[] } | null;
  reviews: { reviewer: string; action: string; ai_marks: number; final_marks: number; comment: string; at: string }[];
}
export interface SubmissionView {
  id: string; assessment_id: string; student: { roll_no: string; name: string }; filename: string; status: string; error: string | null;
  ocr_confidence: number | null;
  result: { ai_total: number; final_total: number | null; max_total: number; status: string; overall_confidence: number; review_required: boolean; flags: string[]; published: boolean } | null;
  responses: ResponseView[];
}
export interface StudentResult {
  assessment: string; final_total: number; max_total: number;
  questions: { subquestion: string; question_text: string; final_marks: number; max_marks: number; comment: string; criteria: { description: string; max_marks: number }[] }[];
}

export const wf = {
  list: () => call<AssessmentRow[]>("faculty", "/assessments"),
  create: (b: { subject_code: string; subject_name: string; title: string }) => call<{ id: string }>("faculty", "/assessments", json(b)),
  get: (id: string) => call<AssessmentDetail>("faculty", `/assessments/${id}`),
  upload: (id: string, kind: string, file: File) => {
    const f = new FormData(); f.append("kind", kind); f.append("file", file);
    return call<{ duplicate: boolean; items: number }>("faculty", `/assessments/${id}/documents`, { method: "POST", body: f });
  },
  editItem: (id: string, sq: string, b: { text?: string; max_marks?: number; model_answer?: string; criteria?: Criterion[] }) =>
    call("faculty", `/assessments/${id}/subquestions/${sq}`, { ...json(b), method: "PATCH" }),
  approve: (id: string) => call<{ approved_items: number; issues: { full_id: string; issues: string[]; note?: string }[]; rag: { status: string; chunks: number; detail?: string } }>("faculty", `/assessments/${id}/approve`, { method: "POST" }),
  submit: (id: string, roll: string, name: string, file: File) => {
    const f = new FormData(); f.append("roll_no", roll); f.append("student_name", name); f.append("file", file);
    return call<{ submission_id: string; duplicate: boolean }>("faculty", `/assessments/${id}/submissions`, { method: "POST", body: f });
  },
  process: (sid: string, force = false) => call("faculty", `/submissions/${sid}/process?force=${force}`, { method: "POST" }),
  evaluate: (sid: string, force = false) => call("faculty", `/submissions/${sid}/evaluate?force=${force}`, { method: "POST" }),
  dashboard: (id: string) => call<Dashboard>("faculty", `/assessments/${id}/dashboard`),
  submission: (sid: string) => call<SubmissionView>("faculty", `/submissions/${sid}`),
  review: (rid: string, b: { action: string; final_marks?: number; comment?: string }) => call<ResponseView>("faculty", `/responses/${rid}/review`, json(b)),
  correctText: (rid: string, text: string) => call("faculty", `/responses/${rid}/text`, { ...json({ text }), method: "PATCH" }),
  publish: (sid: string) => call("faculty", `/submissions/${sid}/publish`, { method: "POST" }),
  pageUrl: async (sid: string, page: number): Promise<string> => {
    const res = await fetch(`${API_URL}/submissions/${sid}/page/${page}`, { headers: headers("faculty") });
    if (!res.ok) throw new WorkflowError(res.status, "Could not load the answer-sheet page.");
    return URL.createObjectURL(await res.blob());
  },
  myResults: () => call<StudentResult[]>("student", "/students/me/results"),
};
