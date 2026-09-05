import type { LucideIcon } from "lucide-react";
import { Card } from "./Card";

export function StatTile({
  label,
  value,
  icon: Icon,
  hint,
  tone = "indigo",
  badge,
}: {
  label: string;
  value: React.ReactNode;
  icon: LucideIcon;
  hint?: React.ReactNode;
  tone?: "indigo" | "emerald" | "amber" | "rose" | "slate";
  badge?: React.ReactNode;
}) {
  const toneClasses: Record<string, string> = {
    indigo: "bg-indigo-50 text-indigo-600",
    emerald: "bg-emerald-50 text-emerald-600",
    amber: "bg-amber-50 text-amber-600",
    rose: "bg-rose-50 text-rose-600",
    slate: "bg-slate-100 text-slate-600",
  };

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${toneClasses[tone]}`}>
          <Icon size={20} strokeWidth={2} />
        </div>
        {badge}
      </div>
      <p className="mt-4 text-sm font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </Card>
  );
}
