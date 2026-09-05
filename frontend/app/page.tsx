import Link from "next/link";
import { GraduationCap, ScanText, ShieldCheck, Users } from "lucide-react";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col bg-slate-50">
      <div className="flex flex-1 flex-col items-center justify-center px-6 py-20">
        <div className="mb-8 flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-600 text-lg font-bold text-white shadow-lg shadow-indigo-600/20">
          SX
        </div>
        <h1 className="max-w-xl text-center text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
          SNAPTIX
        </h1>
        <p className="mt-3 max-w-lg text-center text-base text-slate-600">
          AI-assisted academic assessment — handwritten answers evaluated by OCR and AI,
          with explainable, rubric-aware feedback for faculty and students.
        </p>

        <div className="mt-10 grid w-full max-w-2xl gap-4 sm:grid-cols-2">
          <Link
            href="/faculty"
            className="group rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm transition hover:border-indigo-300 hover:shadow-md"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
              <Users size={20} />
            </div>
            <p className="mt-4 text-base font-semibold text-slate-900">Faculty Portal</p>
            <p className="mt-1 text-sm text-slate-500">
              Create assessments, evaluate handwritten answer sheets, review results and analytics.
            </p>
            <p className="mt-4 text-sm font-medium text-indigo-600 group-hover:underline">
              Enter as faculty &rarr;
            </p>
          </Link>

          <Link
            href="/student"
            className="group rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm transition hover:border-indigo-300 hover:shadow-md"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
              <GraduationCap size={20} />
            </div>
            <p className="mt-4 text-base font-semibold text-slate-900">Student Portal</p>
            <p className="mt-1 text-sm text-slate-500">
              See your results, AI feedback, learning gaps and progress over time.
            </p>
            <p className="mt-4 text-sm font-medium text-indigo-600 group-hover:underline">
              Enter as student &rarr;
            </p>
          </Link>
        </div>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-slate-500">
          <span className="flex items-center gap-1.5">
            <ScanText size={14} /> PaddleOCR + Gemini evaluation pipeline
          </span>
          <span className="flex items-center gap-1.5">
            <ShieldCheck size={14} /> Rubric-enforced, score-clamped grading
          </span>
          <Link href="/roadmap" className="underline hover:text-slate-700">
            What&apos;s implemented vs. planned?
          </Link>
        </div>
      </div>
    </div>
  );
}
