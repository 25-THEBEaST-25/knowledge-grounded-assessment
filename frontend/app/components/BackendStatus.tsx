"use client";

import { useEffect, useState } from "react";
import { CircleAlert, CircleCheck, LoaderCircle } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Status = "checking" | "online" | "offline";

/**
 * Real (not simulated) liveness check against the FastAPI backend's /health
 * endpoint. Runs client-side only, on mount -- never during SSR/build, so it
 * can never fail a production build just because the backend isn't running
 * at build time, and never causes a hydration mismatch (server and first
 * client render both show "checking").
 */
export function BackendStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/health`, { cache: "no-store" })
      .then((r) => {
        if (!cancelled) setStatus(r.ok ? "online" : "offline");
      })
      .catch(() => {
        if (!cancelled) setStatus("offline");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const config = {
    checking: { icon: LoaderCircle, text: "Checking backend…", cls: "text-slate-500", spin: true },
    online: { icon: CircleCheck, text: "Backend API reachable", cls: "text-emerald-600", spin: false },
    offline: { icon: CircleAlert, text: "Backend API unreachable", cls: "text-rose-600", spin: false },
  }[status];

  const Icon = config.icon;

  return (
    <div className={`flex items-center gap-2 text-sm font-medium ${config.cls}`}>
      <Icon size={16} className={config.spin ? "animate-spin" : ""} />
      {config.text}
    </div>
  );
}
