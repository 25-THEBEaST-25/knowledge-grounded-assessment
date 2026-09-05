"use client";

import { Loader2 } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { DemoDataBadge } from "../../components/ui/Badge";
import { BackendStatus } from "../../components/BackendStatus";
import { getFaculty, getSubjects } from "../../lib/repository";
import { useClientData } from "../../lib/useClientData";

export default function FacultySettingsPage() {
  const data = useClientData(() => ({ faculty: getFaculty(), subjects: getSubjects() }), []);

  if (!data) {
    return (
      <AppShell role="faculty" title="Settings">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </div>
      </AppShell>
    );
  }

  const { faculty, subjects } = data;

  return (
    <AppShell role="faculty" title="Settings">
      <Card>
        <CardHeader title="Profile" action={<DemoDataBadge />} />
        <CardBody className="space-y-2 text-sm">
          <p>
            <span className="font-medium text-slate-700">Name:</span> {faculty.name}
          </p>
          <p>
            <span className="font-medium text-slate-700">Title:</span> {faculty.title}
          </p>
          <p>
            <span className="font-medium text-slate-700">Subjects:</span>{" "}
            {subjects.map((s) => s.code).join(", ")}
          </p>
        </CardBody>
      </Card>

      <Card className="mt-6">
        <CardHeader title="Backend connection" />
        <CardBody className="space-y-2">
          <BackendStatus />
          <p className="text-xs text-slate-500">
            API URL: <code className="rounded bg-slate-100 px-1 py-0.5">{process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}</code>
          </p>
        </CardBody>
      </Card>

      <div className="mt-6 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
        Account management, notification preferences, and rubric templates are on the Roadmap — there is no user
        account system yet (see the <a href="/roadmap" className="underline">Roadmap &amp; Status</a> page).
      </div>
    </AppShell>
  );
}
