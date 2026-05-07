import { useState } from "react";
import { GitBranch } from "lucide-react";
import Button from "../common/Button.jsx";
import { useRepo } from "../../hooks/useRepo.js";

export default function RepoUploadForm() {
  const [repoUrl, setRepoUrl] = useState("");
  const { cloneRepository, cloneAndIndexRepo } = useRepo();

  const handleClone = async () => {
    if (!repoUrl) return;
    await cloneRepository(repoUrl);
  };

  const handleCloneAndIndex = async () => {
    if (!repoUrl) return;
    await cloneAndIndexRepo(repoUrl);
  };

  return (
    <div className="card">
      <div className="flex items-center gap-2">
        <GitBranch size={18} className="text-brand" />
        <h3 className="text-lg font-semibold">Clone Repository</h3>
      </div>
      <p className="mt-2 text-sm text-muted">
        Provide a Git URL to clone and optionally index into ChromaDB.
      </p>
      <div className="mt-4 flex flex-col gap-3">
        <input
          className="input"
          placeholder="https://github.com/org/repo.git"
          value={repoUrl}
          onChange={(event) => setRepoUrl(event.target.value)}
        />
        <div className="flex flex-wrap gap-3">
          <Button onClick={handleClone}>Clone Only</Button>
          <Button variant="primary" onClick={handleCloneAndIndex}>
            Clone + Index
          </Button>
        </div>
      </div>
    </div>
  );
}
