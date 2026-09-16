import { NavLink, Outlet } from "react-router";
import {
  Activity,
  Archive,
  BookOpen,
  Boxes,
  Brain,
  Cpu,
  FolderKanban,
  MessageSquare,
  NotebookPen,
  HardDrive,
  LayoutDashboard,
  Settings,
  KeyRound,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Terminal,
  UserRound,
} from "lucide-react";

import { useProfile, useStatus } from "../lib/api";
import { titleCase } from "@myai/api-client";
import { cx } from "../lib/cx";
import { StatusPill } from "./ui";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/console", label: "Console", icon: Terminal },
  { to: "/models", label: "Models", icon: Boxes },
  { to: "/memory", label: "Memory", icon: NotebookPen },
  { to: "/knowledge", label: "Knowledge", icon: BookOpen },
  { to: "/projects", label: "Projects", icon: FolderKanban },
  { to: "/skills", label: "Skills", icon: Sparkles },
  { to: "/profile", label: "My AI", icon: UserRound },
  { to: "/hardware", label: "Hardware", icon: Cpu },
  { to: "/storage", label: "Storage", icon: HardDrive },
  { to: "/privacy", label: "Privacy Center", icon: ShieldCheck },
  { to: "/security", label: "Security", icon: KeyRound },
  { to: "/sync", label: "Sync", icon: RefreshCw },
  { to: "/portable", label: "Portable", icon: Archive },
  { to: "/activity", label: "Activity", icon: Activity },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Layout() {
  const status = useStatus();
  const profile = useProfile();
  const internet = status.data?.internet;

  return (
    <div className="flex h-full">
      <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-bg-elevated">
        <div className="flex items-center gap-2 px-5 py-5">
          <Brain className="h-6 w-6 text-accent" aria-hidden />
          <div>
            <div className="text-sm font-bold tracking-tight">MyAI Academy</div>
            <div className="text-xs text-fg-muted">{profile.data?.name ?? "Your AI"}</div>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 px-3" aria-label="Main">
          {nav.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cx(
                  "flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition",
                  isActive
                    ? "bg-accent-soft text-accent"
                    : "text-fg-muted hover:bg-bg-muted hover:text-fg",
                )
              }
            >
              <Icon className="h-4 w-4" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="space-y-2 border-t border-border p-4 text-xs">
          <StatusPill tone="success">MyAI running locally</StatusPill>
          {status.data?.job && (
            <NavLink to="/skills" className="block">
              <StatusPill tone={status.data.job.status === "paused" ? "warning" : "info"}>
                {status.data.job.kind === "learn" ? "Learning" : "Evaluating"}{" "}
                {titleCase(status.data.job.skill_id)} {status.data.job.progress_percent}%
                {status.data.job.status === "paused" ? " (paused)" : ""}
              </StatusPill>
            </NavLink>
          )}
          <StatusPill
            tone={
              internet === "available" ? "info" : internet === "unavailable" ? "muted" : "warning"
            }
          >
            Internet:{" "}
            {internet === "available"
              ? "Online"
              : internet === "unavailable"
                ? "Offline"
                : "Checking"}
          </StatusPill>
          <StatusPill
            tone={
              status.data?.ai === "available"
                ? "success"
                : status.data?.ai === "unavailable"
                  ? "danger"
                  : "warning"
            }
          >
            AI:{" "}
            {status.data?.ai === "available"
              ? status.data.loaded_model_id
                ? "model loaded"
                : "model ready"
              : status.data?.ai === "unavailable"
                ? "runtime missing"
                : "no model yet"}
          </StatusPill>
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
