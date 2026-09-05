import { ShieldCheck } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { Card, CardBody } from "../../components/ui/Card";
import HandwrittenEvaluation from "../../components/HandwrittenEvaluation";

export default function EvaluatePage() {
  return (
    <AppShell
      role="faculty"
      title="Answer Evaluation"
      subtitle="Image → PaddleOCR → question-wise segmentation → Gemini evaluation"
    >
      <div className="mb-6 flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
        <ShieldCheck size={16} className="mt-0.5 shrink-0" />
        <p>
          This tool calls the real backend pipeline — not a simulation. Scores are rubric-enforced and clamped
          server-side; if the backend or the Gemini API key isn&apos;t available, you&apos;ll see an explicit error
          rather than a fabricated result.
        </p>
      </div>
      <Card>
        <CardBody>
          <HandwrittenEvaluation />
        </CardBody>
      </Card>
    </AppShell>
  );
}
