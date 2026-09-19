import { Suspense, useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Activity,
  Boxes,
  Database,
  FileText,
  FlaskConical,
  GitCompareArrows,
  LayoutDashboard,
  Menu,
  Moon,
  Sun,
  Trophy,
  Waypoints,
  X,
} from "lucide-react";
import { useHealth } from "../../api/queries";
import { useTheme } from "../../hooks/useTheme";
import { cn } from "../../lib/cn";
import { Skeleton } from "../ui/Skeleton";
import { LogoMark } from "./Logo";

const NAV: { section: string; items: { to: string; label: string; icon: ReactNode; end?: boolean }[] }[] = [
  {
    section: "Evaluate",
    items: [
      { to: "/", label: "Overview", icon: <LayoutDashboard />, end: true },
      { to: "/experiments", label: "Experiments", icon: <FlaskConical /> },
      { to: "/compare", label: "Compare", icon: <GitCompareArrows /> },
      { to: "/leaderboard", label: "Leaderboard", icon: <Trophy /> },
    ],
  },
  {
    section: "Assets",
    items: [
      { to: "/datasets", label: "Datasets", icon: <Database /> },
      { to: "/prompts", label: "Prompts", icon: <FileText /> },
      { to: "/models", label: "Models", icon: <Boxes /> },
    ],
  },
  {
    section: "Observe",
    items: [
      { to: "/traces", label: "Traces", icon: <Waypoints /> },
      { to: "/monitoring", label: "Monitoring", icon: <Activity /> },
    ],
  },
];

function HealthPill({ collapsed }: { collapsed?: boolean }) {
  const { data, isError } = useHealth();
  const ok = !isError && data?.status === "ok";
  const label = isError ? "API unreachable" : !data ? "Connecting" : ok ? `API v${data.version}` : "API degraded";
  return (
    <div
      className={cn("flex items-center gap-2 px-2 text-xs text-zinc-500 dark:text-zinc-400", collapsed && "md:justify-center lg:justify-start")}
      title={label}
    >
      <span
        className={cn(
          "size-2 shrink-0 rounded-full",
          isError ? "bg-rose-500" : !data ? "bg-zinc-400" : ok ? "bg-emerald-500" : "bg-amber-500",
        )}
      />
      <span className={cn("truncate", collapsed && "md:hidden lg:inline")}>{label}</span>
    </div>
  );
}

function PageFallback() {
  return (
    <div className="space-y-4" role="status" aria-label="Loading page">
      <Skeleton className="h-7 w-48" />
      <Skeleton className="h-4 w-80" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-72" />
    </div>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { theme, toggle } = useTheme();
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 items-center gap-2.5 px-4 md:justify-center md:px-0 lg:justify-start lg:px-4">
        <LogoMark className="size-7 shrink-0" />
        <div className="leading-tight md:hidden lg:block">
          <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">LLM Eval Platform</div>
          <div className="text-[11px] text-zinc-500 dark:text-zinc-400">Evaluation and observability</div>
        </div>
      </div>
      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-3 md:px-2 lg:px-3" aria-label="Main">
        {NAV.map((group) => (
          <div key={group.section}>
            <div className="mb-1 px-2 text-[10px] font-semibold tracking-wider text-zinc-400 uppercase md:hidden lg:block dark:text-zinc-500">
              {group.section}
            </div>
            <ul className="space-y-0.5">
              {group.items.map((it) => (
                <li key={it.to}>
                  <NavLink
                    to={it.to}
                    end={it.end}
                    onClick={onNavigate}
                    title={it.label}
                    className={({ isActive }) =>
                      cn(
                        "flex h-8 items-center gap-2.5 rounded-md px-2 text-sm font-medium transition-colors md:justify-center lg:justify-start [&_svg]:size-4 [&_svg]:shrink-0",
                        isActive
                          ? "bg-accent-50 text-accent-700 dark:bg-accent-500/10 dark:text-accent-300"
                          : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-100",
                      )
                    }
                  >
                    {it.icon}
                    <span className="md:hidden lg:inline">{it.label}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <div className="space-y-2 border-t border-zinc-200 px-3 py-3 md:px-2 lg:px-3 dark:border-zinc-800">
        <HealthPill collapsed />
        <button
          type="button"
          onClick={toggle}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          title={theme === "dark" ? "Light mode" : "Dark mode"}
          className="flex h-8 w-full items-center gap-2.5 rounded-md px-2 text-sm text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 md:justify-center lg:justify-start dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-100"
        >
          {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
          <span className="md:hidden lg:inline">{theme === "dark" ? "Light mode" : "Dark mode"}</span>
        </button>
      </div>
    </div>
  );
}

export function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  return (
    <div className="flex min-h-full">
      <aside className="sticky top-0 hidden h-screen shrink-0 border-r border-zinc-200 bg-white md:block md:w-14 lg:w-60 dark:border-zinc-800/80 dark:bg-zinc-950">
        <SidebarContent />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-zinc-950/50" onClick={() => setMobileOpen(false)} aria-hidden />
          <aside className="animate-drawer-in absolute inset-y-0 left-0 w-64 border-r border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
            <button
              type="button"
              className="absolute top-3.5 right-3 rounded p-1 text-zinc-500"
              aria-label="Close navigation"
              onClick={() => setMobileOpen(false)}
            >
              <X className="size-4" />
            </button>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-12 items-center gap-3 border-b border-zinc-200 bg-white/80 px-4 backdrop-blur md:hidden dark:border-zinc-800 dark:bg-zinc-950/80">
          <button type="button" aria-label="Open navigation" onClick={() => setMobileOpen(true)} className="rounded p-1">
            <Menu className="size-5" />
          </button>
          <LogoMark className="size-6" />
          <span className="text-sm font-semibold">LLM Eval Platform</span>
        </header>
        <main key={location.pathname.split("/")[1]} className="animate-fade-in mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <Suspense fallback={<PageFallback />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
