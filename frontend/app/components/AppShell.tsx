import Link from "next/link";
import { ArrowLeftRight } from "lucide-react";
import { AppSidebar } from "./AppSidebar";

export function AppShell({
  role,
  title,
  subtitle,
  action,
  children,
}: {
  role: "faculty" | "student";
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  const otherPortal = role === "faculty" ? { href: "/student", label: "Student portal" } : { href: "/faculty", label: "Faculty portal" };

  return (
    <div className="flex min-h-screen bg-slate-50">
      <AppSidebar role={role} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-slate-200 bg-white px-8 py-5">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
            {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
          </div>
          <div className="flex items-center gap-3">
            {action}
            <Link
              href={otherPortal.href}
              className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
            >
              <ArrowLeftRight size={14} />
              {otherPortal.label}
            </Link>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto px-8 py-8">{children}</main>
      </div>
    </div>
  );
}
