import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  FolderGit2,
  Search,
  FlaskConical,
  Settings
} from "lucide-react";

const navItems = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { path: "/repositories", label: "Repositories", icon: FolderGit2 },
  { path: "/search", label: "Semantic Search", icon: Search },
  { path: "/tests", label: "Test Generation", icon: FlaskConical },
  { path: "/settings", label: "Settings", icon: Settings }
];

export default function Sidebar() {
  return (
    <aside className="hidden w-72 flex-col border-r border-border bg-panel px-4 py-6 lg:flex">
      <div className="mb-8">
        <p className="label">AI Platform</p>
        <h2 className="text-xl font-semibold">Test Gen Suite</h2>
      </div>
      <nav className="flex flex-col gap-2">
        {navItems.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              [
                "flex items-center gap-3 rounded-xl px-4 py-3 text-sm transition",
                isActive
                  ? "bg-brand text-black shadow-glow"
                  : "text-muted hover:bg-panel-2 hover:text-text"
              ].join(" ")
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto rounded-2xl border border-border bg-panel-2 p-4 text-xs text-muted">
        <p className="mb-2 text-sm font-medium text-text">Env</p>
        <p>API: {import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"}</p>
      </div>
    </aside>
  );
}
