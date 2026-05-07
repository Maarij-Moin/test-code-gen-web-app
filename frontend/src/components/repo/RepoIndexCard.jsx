import { useState } from "react";
import { Database } from "lucide-react";
import Button from "../common/Button.jsx";
import { useRepo } from "../../hooks/useRepo.js";
import { useRepoContext } from "../../context/RepoContext.jsx";

export default function RepoIndexCard() {
  const { repoState } = useRepoContext();
  const { indexRepository, updateIndex } = useRepo();
  const [repoPath, setRepoPath] = useState(repoState.repoPath || "");

  const handleIndex = async () => {
    if (!repoPath) return;
    await indexRepository(repoPath);
  };

  const handleUpdate = async () => {
    if (!repoPath || !repoState.repoId) return;
    await updateIndex(repoPath, repoState.repoId);
  };

  return (
    <div className="card">
      <div className="flex items-center gap-2">
        <Database size={18} className="text-brand" />
        <h3 className="text-lg font-semibold">Index Repository</h3>
      </div>
      <p className="mt-2 text-sm text-muted">
        Embed the repository code into ChromaDB for semantic search.
      </p>
      <div className="mt-4 flex flex-col gap-3">
        <input
          className="input"
          placeholder="C:/repos/project"
          value={repoPath}
          onChange={(event) => setRepoPath(event.target.value)}
        />
        <div className="flex flex-wrap gap-3">
          <Button variant="primary" onClick={handleIndex}>
            Index Repository
          </Button>
          <Button onClick={handleUpdate}>Incremental Update</Button>
        </div>
        {repoState.repoId && (
          <div className="text-xs text-muted">
            Current repo_id: <span className="text-text">{repoState.repoId}</span>
          </div>
        )}
      </div>
    </div>
  );
}
