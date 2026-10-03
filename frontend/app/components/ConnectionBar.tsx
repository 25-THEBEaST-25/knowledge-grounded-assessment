"use client";

import { useEffect, useState } from "react";
import { KeyRound } from "lucide-react";
import { Card, CardBody } from "./ui/Card";
import { loadConn, saveConn, wf, type Conn } from "../lib/workflowApi";

/** API-key connection for the real assessment backend. Stored only in this browser. */
export function ConnectionBar({ role, onChange }: { role: "faculty" | "student"; onChange?: () => void }) {
  const [conn, setConn] = useState<Conn | null>(null);
  const [status, setStatus] = useState("");

  useEffect(() => {
    setConn(loadConn());
  }, []);

  if (!conn) return null;
  const set = (patch: Partial<Conn>) => setConn({ ...conn, ...patch });
  const input = "w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm";

  async function save() {
    if (!conn) return;
    saveConn(conn);
    setStatus("Checking…");
    try {
      if (role === "faculty") await wf.list();
      else await wf.myResults();
      setStatus("Connected ✓");
      onChange?.();
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Failed");
    }
  }

  return (
    <Card className="mb-6">
      <CardBody>
        <div className="flex flex-wrap items-end gap-3">
          <KeyRound size={18} className="mb-2 text-slate-500" />
          {role === "faculty" ? (
            <>
              <label className="min-w-48 flex-1 text-xs text-slate-500">Faculty API key
                <input type="password" className={input} value={conn.facultyKey} onChange={(e) => set({ facultyKey: e.target.value })} />
              </label>
              <label className="min-w-40 text-xs text-slate-500">Reviewer name (audit trail)
                <input className={input} value={conn.reviewer} onChange={(e) => set({ reviewer: e.target.value })} />
              </label>
            </>
          ) : (
            <>
              <label className="min-w-48 flex-1 text-xs text-slate-500">Student API key
                <input type="password" className={input} value={conn.studentKey} onChange={(e) => set({ studentKey: e.target.value })} />
              </label>
              <label className="min-w-40 text-xs text-slate-500">Roll number
                <input className={input} value={conn.roll} onChange={(e) => set({ roll: e.target.value })} />
              </label>
            </>
          )}
          <button onClick={save} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
            Connect
          </button>
          {status && <span className="pb-2 text-xs text-slate-600">{status}</span>}
        </div>
        <p className="mt-2 text-xs text-slate-400">
          Demo-grade auth: the key is kept in this browser only and sent as a Bearer token to your backend.
        </p>
      </CardBody>
    </Card>
  );
}
