import Link from "next/link";
import { ArrowLeft, CheckCircle2, Circle } from "lucide-react";
import { Card, CardBody, CardHeader } from "../components/ui/Card";

const IMPLEMENTED = [
  {
    title: "Handwritten OCR",
    detail: "PaddleOCR 3.x, with reading-order line sorting and configurable preprocessing (upscale, autocontrast) for small/low-contrast scans.",
  },
  {
    title: "Question-wise segmentation",
    detail: "Deterministic regex-based detection of Q1/Q.1/Question 1/Ans 1/1)/Q1(a) markers and common OCR misreads, with duplicate-question merging and unmarked-answer handling.",
  },
  {
    title: "AI evaluation (single-call rubric grading)",
    detail: "One Gemini call per question, scoring conceptual understanding, accuracy, precision and terminology against the faculty's model answer and rubric.",
  },
  {
    title: "Score integrity & prompt-injection defenses",
    detail: "Server-side hard clamping to the rubric's authoritative max score, explicit untrusted-data delimiting in the prompt — the model cannot award marks outside the rubric even if the student answer tries to instruct it to.",
  },
  {
    title: "Confidence & needs-review flagging",
    detail: "OCR confidence and evaluator confidence are combined into a single score; low-confidence results are flagged for manual review rather than silently trusted.",
  },
  {
    title: "Provider-failure handling",
    detail: "Gemini rate limits, provider errors, and network failures return a clear 503, not a crash or a fabricated result.",
  },
  {
    title: "Faculty assessment workflow",
    detail: "Create an assessment with questions and rubric criteria, upload a real answer sheet, run the real pipeline, publish results — persisted in the browser (not yet a shared server database).",
  },
  {
    title: "Faculty & Student dashboards",
    detail: "Real computed aggregates (averages, rank, distributions, CO/PO attainment) over a sample dataset, clearly labelled as demo data throughout.",
  },
];

const ROADMAP = [
  {
    title: "Real persistence (PostgreSQL)",
    detail: "Everything faculty-created today lives in browser localStorage. A shared database is the prerequisite for multi-device, multi-user use.",
  },
  {
    title: "Authentication & roles",
    detail: "There is no login yet. The Faculty/Student split today is a navigation choice, not an access-controlled account system.",
  },
  {
    title: "Knowledge-grounded retrieval (RAG)",
    detail: "No Qdrant, LlamaIndex, or embedding pipeline exists. Evaluation currently grades against the rubric and model answer directly, not a retrieved knowledge base.",
  },
  {
    title: "Multi-agent evaluation",
    detail: "No LangGraph or multi-agent orchestration exists. Evaluation is one Gemini call per question, not separate Concept/Accuracy/Diagram/Code/Consensus agents.",
  },
  {
    title: "Diagram evaluation",
    detail: "No service exists for evaluating diagrams or flowcharts.",
  },
  {
    title: "Code evaluation",
    detail: "No service exists for evaluating programming answers.",
  },
  {
    title: "Full OBE automation",
    detail: "The CO/PO attainment and CO→PO matrix shown in Analytics are a demo illustration of the intended surface with a transparent formula, not an accreditation-derived automated pipeline.",
  },
  {
    title: "CI/CD",
    detail: "Tests run locally (49 backend tests, frontend lint/build) but nothing runs them automatically on push yet.",
  },
];

export default function RoadmapPage() {
  return (
    <div className="min-h-screen bg-slate-50 px-6 py-10">
      <div className="mx-auto max-w-4xl">
        <Link href="/" className="mb-6 flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700">
          <ArrowLeft size={15} /> Back to SNAPTIX
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Implemented vs. Planned</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">
          SNAPTIX&apos;s long-term design includes RAG, multi-agent evaluation, diagram/code grading, and full OBE
          automation. This page exists so that distinction is never blurred in a demo: what follows is graded
          honestly against what actually runs today.
        </p>

        <Card className="mt-8">
          <CardHeader
            title={
              <span className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 size={18} /> Implemented
              </span>
            }
          />
          <CardBody className="space-y-4">
            {IMPLEMENTED.map((item) => (
              <div key={item.title}>
                <p className="text-sm font-semibold text-slate-800">{item.title}</p>
                <p className="text-sm text-slate-600">{item.detail}</p>
              </div>
            ))}
          </CardBody>
        </Card>

        <Card className="mt-6">
          <CardHeader
            title={
              <span className="flex items-center gap-2 text-violet-700">
                <Circle size={18} /> Next phase / roadmap
              </span>
            }
          />
          <CardBody className="space-y-4">
            {ROADMAP.map((item) => (
              <div key={item.title}>
                <p className="text-sm font-semibold text-slate-800">{item.title}</p>
                <p className="text-sm text-slate-600">{item.detail}</p>
              </div>
            ))}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
