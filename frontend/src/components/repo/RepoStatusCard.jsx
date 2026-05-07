import { useRepoContext } from "../../context/RepoContext.jsx";
import { formatDate } from "../../utils/formatters.js";

export default function RepoStatusCard() {
  const { repoState } = useRepoContext();

  return (
    <div className="card-muted">
      <p className="label">Repository Status</p>
      <div className="mt-4 grid gap-3 text-sm">
        <div className="flex justify-between">
          <span className="text-muted">Status</span>
          <span className="text-text">{repoState.status}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Repo Path</span>
          <span className="text-text">{repoState.repoPath || "-"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Repo ID</span>
          <span className="text-text">{repoState.repoId || "-"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Last Updated</span>
          <span className="text-text">{formatDate(repoState.lastUpdated)}</span>
        </div>
      </div>
    </div>
  );
}
