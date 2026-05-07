import { Activity, Server } from "lucide-react";
import { useLocation } from "react-router-dom";
import { NAV_ITEMS } from "../../utils/constants.js";
import { useRepoContext } from "../../context/RepoContext.jsx";
import { useAppContext } from "../../context/AppContext.jsx";

export default function Navbar() {
  const location = useLocation();
  const { repoState } = useRepoContext();
  const { loading } = useAppContext();

  const current = NAV_ITEMS.find((item) => item.path === location.pathname);
  const title = current?.label || "Dashboard";

  return (
    <header className="flex items-center justify-between border-b border-border bg-panel/80 px-6 py-4 backdrop-blur">
      <div>
        <p className="label">Automated Test Generation</p>
        <h1 className="text-2xl font-semibold">{title}</h1>
      </div>
      <div className="flex items-center gap-3">
        <span className="badge flex items-center gap-2">
          <Server size={14} />
          {repoState.status}
        </span>
        <span className="badge flex items-center gap-2">
          <Activity size={14} />
          {loading ? "Working" : "Idle"}
        </span>
      </div>
    </header>
  );
}
