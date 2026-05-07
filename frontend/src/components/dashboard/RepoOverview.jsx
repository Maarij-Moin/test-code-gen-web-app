import { useRepoContext } from "../../context/RepoContext.jsx";

export default function RepoOverview() {
  const { repoState } = useRepoContext();

  return (
    <div className="card-muted">
      <p className="label">Active Repository</p>
      <h3 className="mt-3 text-lg font-semibold">{repoState.repoPath || "Not set"}</h3>
      <div className="mt-4 text-sm text-muted">
        Repo ID: <span className="text-text">{repoState.repoId || "-"}</span>
      </div>
    </div>
  );
}
