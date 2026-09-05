function toneForPercent(p: number) {
  if (p >= 75) return "bg-emerald-500";
  if (p >= 50) return "bg-amber-500";
  return "bg-rose-500";
}

export function ScoreBar({ percent, className = "" }: { percent: number; className?: string }) {
  const clamped = Math.max(0, Math.min(100, percent));
  return (
    <div className={`h-1.5 w-full overflow-hidden rounded-full bg-slate-100 ${className}`}>
      <div
        className={`h-full rounded-full ${toneForPercent(clamped)}`}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
