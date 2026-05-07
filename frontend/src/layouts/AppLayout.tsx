import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { Activity, GitBranch, GitPullRequest, LayoutDashboard, LogOut, Menu, Moon, ShieldCheck, Sun, TestTube2, X } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { useAuth } from "@/hooks/useAuth";
import { useRealtime } from "@/hooks/useRealtime";
import { useAuthStore } from "@/stores/authStore";
import { useUiStore } from "@/stores/uiStore";

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/jobs", label: "Jobs", icon: Activity },
  { to: "/tests", label: "Tests", icon: TestTube2 },
  { to: "/pull-requests", label: "Pull Requests", icon: GitPullRequest },
];

export function AppLayout() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const user = useAuthStore((state) => state.user);
  const { theme, toggleTheme, sidebarOpen, setSidebarOpen } = useUiStore();
  const { connected } = useRealtime();

  const sidebar = (
    <aside className="flex h-full w-72 flex-col border-r border-border bg-panel">
      <div className="flex h-16 items-center justify-between px-5">
        <div className="flex items-center gap-3">
          <div className="rounded-md bg-brand p-2 text-white">
            <ShieldCheck size={20} />
          </div>
          <div>
            <p className="text-sm font-bold text-text">Autonomous QA</p>
            <p className="text-xs text-muted">{connected ? "Realtime connected" : "Polling active"}</p>
          </div>
        </div>
        <button className="focus-ring rounded-md p-2 lg:hidden" onClick={() => setSidebarOpen(false)} aria-label="Close navigation">
          <X size={18} />
        </button>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition ${
                isActive ? "bg-brand text-white" : "text-muted hover:bg-panel2 hover:text-text"
              }`
            }
          >
            <item.icon size={18} />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-border p-4">
        <div className="mb-3 rounded-md bg-panel2 p-3">
          <p className="truncate text-sm font-semibold text-text">{user?.full_name ?? "QA Engineer"}</p>
          <p className="truncate text-xs text-muted">{user?.email}</p>
        </div>
        <Button
          variant="ghost"
          className="w-full justify-start"
          onClick={() => {
            logout();
            navigate("/login");
          }}
        >
          <LogOut size={16} />
          Sign out
        </Button>
      </div>
    </aside>
  );

  return (
    <div className="min-h-screen bg-surface text-text">
      <div className="hidden lg:fixed lg:inset-y-0 lg:block">{sidebar}</div>
      {sidebarOpen ? <div className="fixed inset-0 z-40 bg-black/50 lg:hidden" onClick={() => setSidebarOpen(false)} /> : null}
      <div className={`fixed inset-y-0 left-0 z-50 transition lg:hidden ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`}>{sidebar}</div>
      <div className="lg:pl-72">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-surface/95 px-4 backdrop-blur md:px-8">
          <button className="focus-ring rounded-md p-2 lg:hidden" onClick={() => setSidebarOpen(true)} aria-label="Open navigation">
            <Menu size={20} />
          </button>
          <div className="hidden items-center gap-2 text-sm text-muted lg:flex">
            <GitBranch size={16} />
            Autonomous testing platform
          </div>
          <Button variant="secondary" onClick={toggleTheme} aria-label="Toggle dark mode">
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            {theme === "dark" ? "Light" : "Dark"}
          </Button>
        </header>
        <Outlet />
      </div>
    </div>
  );
}
