import { Check, Loader2 } from "lucide-react";

export type StepState = "pending" | "active" | "done" | "error";

export interface Step {
  key: string;
  label: string;
  state: StepState;
}

export function StepProgress({ steps }: { steps: Step[] }) {
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-3">
      {steps.map((step, i) => (
        <li key={step.key} className="flex items-center gap-2">
          <div
            className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
              step.state === "done"
                ? "bg-emerald-500 text-white"
                : step.state === "active"
                  ? "bg-indigo-600 text-white"
                  : step.state === "error"
                    ? "bg-rose-500 text-white"
                    : "bg-slate-100 text-slate-400"
            }`}
          >
            {step.state === "done" ? (
              <Check size={14} strokeWidth={3} />
            ) : step.state === "active" ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              i + 1
            )}
          </div>
          <span
            className={`text-sm ${
              step.state === "pending" ? "text-slate-400" : "text-slate-700 font-medium"
            }`}
          >
            {step.label}
          </span>
          {i < steps.length - 1 && <span className="mx-1 h-px w-6 bg-slate-200" />}
        </li>
      ))}
    </ol>
  );
}
