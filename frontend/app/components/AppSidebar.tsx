"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  BookOpen,
  ClipboardList,
  FileText,
  LayoutDashboard,
  Map,
  ScanText,
  Settings,
  Sparkles,
  Target,
  User,
  Users,
} from "lucide-react";
import { getFaculty, getStudentById } from "../lib/repository";
import { DEMO_STUDENT_ID } from "../lib/demoData";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ size?: number; strokeWidth?: number }>;
}

const FACULTY_NAV: NavItem[] = [
  { label: "Dashboard", href: "/faculty", icon: LayoutDashboard },
  { label: "Assessments", href: "/faculty/assessments", icon: ClipboardList },
  { label: "Answer Evaluation", href: "/faculty/evaluate", icon: ScanText },
  { label: "Students", href: "/faculty/students", icon: Users },
  { label: "Analytics", href: "/faculty/analytics", icon: BarChart3 },
  { label: "Reports", href: "/faculty/reports", icon: FileText },
  { label: "Settings", href: "/faculty/settings", icon: Settings },
];

const STUDENT_NAV: NavItem[] = [
  { label: "Dashboard", href: "/student", icon: LayoutDashboard },
  { label: "My Assessments", href: "/student/assessments", icon: ClipboardList },
  { label: "My Results", href: "/student/results", icon: BookOpen },
  { label: "AI Feedback", href: "/student/feedback", icon: Sparkles },
  { label: "Learning Gaps", href: "/student/learning-gaps", icon: Target },
  { label: "Profile", href: "/student/profile", icon: User },
];

export function AppSidebar({ role }: { role: "faculty" | "student" }) {
  const pathname = usePathname();
  const items = role === "faculty" ? FACULTY_NAV : STUDENT_NAV;
  const faculty = getFaculty();
  const student = getStudentById(DEMO_STUDENT_ID);

  const isActive = (href: string) =>
    href === `/${role}` ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-slate-800/60 bg-slate-900 text-slate-200">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500 text-sm font-bold text-white">
          SX
        </div>
        <div>
          <p className="text-sm font-semibold text-white leading-tight">SNAPTIX</p>
          <p className="text-[11px] text-slate-400 leading-tight">
            {role === "faculty" ? "Faculty Portal" : "Student Portal"}
          </p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-2">
        {items.map((item) => {
          const active = isActive(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                active
                  ? "bg-indigo-500/15 text-white"
                  : "text-slate-400 hover:bg-slate-800/70 hover:text-slate-100"
              }`}
            >
              <Icon size={18} strokeWidth={2} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-slate-800/60 px-3 py-3">
        <Link
          href="/roadmap"
          className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-400 hover:bg-slate-800/70 hover:text-slate-100"
        >
          <Map size={18} strokeWidth={2} />
          Roadmap &amp; Status
        </Link>
      </div>

      <div className="flex items-center gap-3 border-t border-slate-800/60 px-4 py-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-700 text-sm font-semibold text-white">
          {(role === "faculty" ? faculty.name : student?.name ?? "Student")
            .split(" ")
            .map((p) => p[0])
            .slice(0, 2)
            .join("")}
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-white">
            {role === "faculty" ? faculty.name : student?.name}
          </p>
          <p className="truncate text-xs text-slate-400">
            {role === "faculty" ? faculty.title : `Roll No. ${student?.rollNumber}`}
          </p>
        </div>
      </div>
    </aside>
  );
}
