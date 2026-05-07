import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Activity,
  Bot,
  GitBranch,
  GitPullRequest,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Settings,
  Sun,
  TestTube2,
  Webhook,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/Button";
import { useAuth } from "@/hooks/useAuth";
import { useRealtime } from "@/hooks/useRealtime";
import { useAuthStore } from "@/stores/authStore";
import { useUiStore } from "@/stores/uiStore";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/jobs", label: "Jobs", icon: Activity, end: false },
  { to: "/tests", label: "Generated Tests", icon: TestTube2, end: false },
  { to: "/pull-requests", label: "Pull Requests", icon: GitPullRequest, end: false },
  { to: "/activity", label: "Repo Activity", icon: Webhook, end: false },
];

function NavItem({
  to,
  label,
  icon: Icon,
  end,
  onClick,
}: {
  to: string;
  label: string;
  icon: React.ElementType;
  end: boolean;
  onClick: () => void;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      className={({ isActive }) =>
        `group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all ${
          isActive
            ? "bg-gradient-to-r from-brand/20 to-brand2/10 text-brand shadow-sm"
            : "text-muted hover:bg-panel2 hover:text-text"
        }`
      }
    >
      {({ isActive }) => (
        <>
          <Icon size={17} className={isActive ? "text-brand" : "text-muted group-hover:text-text"} />
          {label}
          {isActive && (
            <span className="ml-auto h-1.5 w-1.5 rounded-full bg-brand" />
          )}
        </>
      )}
    </NavLink>
  );
}

export function AppLayout() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const user = useAuthStore((state) => state.user);
  const { theme, toggleTheme, sidebarOpen, setSidebarOpen } = useUiStore();
  const { connected } = useRealtime();

  const sidebar = (
    <aside className="flex h-full w-72 flex-col border-r border-border bg-panel">
      {/* Brand */}
      <div className="flex h-16 items-center justify-between px-5">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand to-brand2 shadow-glow">
            <Bot size={18} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-bold text-text">Autonomous QA</p>
            <p className="text-[10px] text-muted">
              {connected ? (
                <span className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-success" /> Live
                </span>
              ) : (
                "Polling active"
              )}
            </p>
          </div>
        </div>
        <button
          className="focus-ring rounded-lg p-1.5 lg:hidden text-muted hover:text-text"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close navigation"
        >
          <X size={16} />
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-4">
        <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest text-muted">
          Platform
        </p>
        {NAV.map((item) => (
          <NavItem
            key={item.to}
            {...item}
            onClick={() => setSidebarOpen(false)}
          />
        ))}
        <p className="mb-2 mt-5 px-3 text-[10px] font-semibold uppercase tracking-widest text-muted">
          Workspace
        </p>
        <NavItem
          to="/settings"
          label="Settings"
          icon={Settings}
          end={false}
          onClick={() => setSidebarOpen(false)}
        />
      </nav>

      {/* User footer */}
      <div className="border-t border-border p-4">
        <div className="mb-3 flex items-center gap-3 rounded-xl bg-panel2 p-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand to-brand2 text-xs font-bold text-white">
            {(user?.full_name ?? user?.email ?? "?")[0].toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-text">
              {user?.full_name ?? "QA Engineer"}
            </p>
            <p className="truncate text-xs text-muted">{user?.email}</p>
          </div>
        </div>
        <Button
          variant="ghost"
          className="w-full justify-start"
          onClick={() => {
            logout();
            navigate("/login");
          }}
        >
          <LogOut size={15} />
          Sign out
        </Button>
      </div>
    </aside>
  );

  return (
    <div className="min-h-screen bg-surface text-text">
      {/* Desktop fixed sidebar */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:block">{sidebar}</div>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Mobile drawer */}
      <div
        className={`fixed inset-y-0 left-0 z-50 transition-transform duration-300 lg:hidden ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {sidebar}
      </div>

      {/* Main content */}
      <div className="lg:pl-72">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-surface/90 px-4 backdrop-blur-md md:px-8">
          <button
            className="focus-ring rounded-lg p-2 text-muted hover:text-text lg:hidden"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open navigation"
          >
            <Menu size={20} />
          </button>
          <div className="hidden items-center gap-2 text-sm text-muted lg:flex">
            <GitBranch size={15} />
            <span>Autonomous testing platform</span>
          </div>
          <Button variant="secondary" onClick={toggleTheme} aria-label="Toggle theme">
            {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
            {theme === "dark" ? "Light" : "Dark"}
          </Button>
        </header>
        <Outlet />
      </div>
    </div>
  );
}
