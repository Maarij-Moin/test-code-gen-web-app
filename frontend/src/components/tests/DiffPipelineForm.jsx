import { FlaskConical, RefreshCcw } from "lucide-react";
import Button from "../common/Button.jsx";

export default function DiffPipelineForm({
  repoPath,
  repoId,
  onRepoPathChange,
  onRepoIdChange,
  onGenerate,
  onUpdate
}) {
  const handleGenerate = async () => {
    if (!repoPath || !repoId) return;
    await onGenerate(repoPath, repoId);
  };

  const handleUpdate = async () => {
    if (!repoPath || !repoId) return;
    await onUpdate(repoPath, repoId);
  };

  return (
    <div className="card">
      <div className="flex items-center gap-2">
        <FlaskConical size={18} className="text-brand" />
        <h3 className="text-lg font-semibold">Diff Pipeline</h3>
      </div>
      <p className="mt-2 text-sm text-muted">
        Run the git diff pipeline to generate AI test prompts for the latest changes.
      </p>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <input
          className="input"
          placeholder="Repo path"
          value={repoPath}
          onChange={(event) => onRepoPathChange(event.target.value)}
        />
        <input
          className="input"
          placeholder="Repo ID"
          value={repoId}
          onChange={(event) => onRepoIdChange(event.target.value)}
        />
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        <Button variant="primary" onClick={handleGenerate}>
          Generate Prompts
        </Button>
        <Button onClick={handleUpdate}>
          <RefreshCcw size={14} />
          Update Vectorstore
        </Button>
      </div>
    </div>
  );
}
