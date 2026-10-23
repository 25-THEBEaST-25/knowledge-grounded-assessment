
/* eslint-disable react-hooks/set-state-in-effect -- data is fetched after mount; state is set after awaited calls */
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ClipboardList, Loader2, Plus } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { ConnectionBar } from "../../components/ConnectionBar";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { Badge, LiveBadge } from "../../components/ui/Badge";
import { EmptyState } from "../../components/ui/EmptyState";
import { wf, type AssessmentRow } from "../../lib/workflowApi";

export default function WorkflowHome() {
  const [rows, setRows] = useState<AssessmentRow[] | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    subject_code: "",
    subject_name: "",
    title: "",
  });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setRows(await wf.list());
      setError("");
    } catch (e) {
      setRows([]);
      setError(e instanceof Error ? e.message : "Failed to load assessments");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function create() {
    if (
      !form.subject_code.trim() ||
      !form.subject_name.trim() ||
      !form.title.trim()
    ) {
      setError("Please fill in the subject code, subject name, and assessment title.");
      return;
    }

    setBusy(true);
    setError("");

    try {
      await wf.create({
        subject_code: form.subject_code.trim(),
        subject_name: form.subject_name.trim(),
        title: form.title.trim(),
      });

      setForm({ subject_code: "", subject_name: "", title: "" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create assessment");
    } finally {
      setBusy(false);
    }
  }

  const input =
    "w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-700 shadow-sm outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-100 disabled:text-slate-700";
  const canCreate =
    !busy &&
    !!form.subject_code.trim() &&
    !!form.subject_name.trim() &&
    !!form.title.trim();

  return (
    <AppShell
      role="faculty"
      title="Assessment workflow"
      subtitle="Materials → approval → submissions → AI evaluation → faculty review"
    >
      <ConnectionBar role="faculty" onChange={load} />

      {error && (
        <div
          role="alert"
          className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700"
        >
          {error}
        </div>
      )}

      <Card className="mb-6">
        <CardHeader
          title="New assessment"
          action={<LiveBadge />}
        />

        <CardBody>
          <form
            className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-[180px_220px_minmax(240px,1fr)_auto]"
            onSubmit={(e) => {
              e.preventDefault();
              void create();
            }}
          >
            <input
              className={input}
              placeholder="Subject code (e.g. CN301)"
              aria-label="Subject code"
              autoComplete="off"
              value={form.subject_code}
              onChange={(e) =>
                setForm({ ...form, subject_code: e.target.value })
              }
              disabled={busy}
              required
            />

            <input
              className={input}
              placeholder="Subject name"
              aria-label="Subject name"
              autoComplete="off"
              value={form.subject_name}
              onChange={(e) =>
                setForm({ ...form, subject_name: e.target.value })
              }
              disabled={busy}
              required
            />

            <input
              className={input}
              placeholder="Assessment title"
              aria-label="Assessment title"
              autoComplete="off"
              value={form.title}
              onChange={(e) =>
                setForm({ ...form, title: e.target.value })
              }
              disabled={busy}
              required
            />

            <button
              type="submit"
              disabled={!canCreate}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Plus size={16} />
              )}
              {busy ? "Creating…" : "Create"}
            </button>
          </form>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Assessments" />

        <CardBody>
          {rows === null ? (
            <div className="flex items-center gap-2 py-6 text-sm text-slate-500">
              <Loader2 size={16} className="animate-spin" />
              Loading assessments…
            </div>
          ) : rows.length === 0 ? (
            <EmptyState
              icon={ClipboardList}
              title="No assessments yet"
              description="Create an assessment above, then upload the question paper, model answers, and rubric."
            />
          ) : (
            <ul className="divide-y divide-slate-100">
              {rows.map((a) => (
                <li
                  key={a.id}
                  className="flex flex-col gap-2 py-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <Link
                    href={`/faculty/workflow/${a.id}`}
                    className="font-medium text-indigo-700 hover:underline"
                  >
                    {a.title}
                  </Link>

                  <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
                    <span>{a.subject}</span>

                    {a.is_demo && (
                      <Badge variant="demo">Demo fixture</Badge>
                    )}

                    <Badge
                      variant={
                        a.status === "MATERIALS_APPROVED"
                          ? "live"
                          : "neutral"
                      }
                    >
                      {a.status}
                    </Badge>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </AppShell>
  );
}
