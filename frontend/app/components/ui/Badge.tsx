const VARIANTS = {
  demo: "bg-amber-50 text-amber-800 border-amber-200",
  live: "bg-emerald-50 text-emerald-700 border-emerald-200",
  local: "bg-sky-50 text-sky-700 border-sky-200",
  review: "bg-amber-50 text-amber-800 border-amber-200",
  neutral: "bg-slate-100 text-slate-600 border-slate-200",
  danger: "bg-rose-50 text-rose-700 border-rose-200",
  roadmap: "bg-violet-50 text-violet-700 border-violet-200",
} as const;

export type BadgeVariant = keyof typeof VARIANTS;

export function Badge({
  children,
  variant = "neutral",
  className = "",
}: {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${VARIANTS[variant]} ${className}`}
    >
      {children}
    </span>
  );
}

/** Use on every widget/number backed by the fabricated demo dataset, never
 * on output of the real /handwritten/evaluate call. */
export function DemoDataBadge({ className = "" }: { className?: string }) {
  return (
    <Badge variant="demo" className={className}>
      Demo data
    </Badge>
  );
}

/** Use only on data that came from a real backend call this session. */
export function LiveBadge({ className = "" }: { className?: string }) {
  return (
    <Badge variant="live" className={className}>
      Live
    </Badge>
  );
}

/** Use on faculty-created content saved via localStorage, not a server DB. */
export function LocalOnlyBadge({ className = "" }: { className?: string }) {
  return (
    <Badge variant="local" className={className}>
      Saved on this device
    </Badge>
  );
}
