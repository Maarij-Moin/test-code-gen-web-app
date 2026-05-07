import { useState } from "react";
import DiffPipelineForm from "../components/tests/DiffPipelineForm.jsx";
import GeneratedTestsPanel from "../components/tests/GeneratedTestsPanel.jsx";
import ErrorAlert from "../components/common/ErrorAlert.jsx";
import Loader from "../components/common/Loader.jsx";
import { useTests } from "../hooks/useTests.js";
import { useAppContext } from "../context/AppContext.jsx";
import { useRepoContext } from "../context/RepoContext.jsx";

export default function TestGenerationPage() {
  const { repoState } = useRepoContext();
  const { prompts, runGeneration, updateVectorstore } = useTests();
  const { loading, error, clearError } = useAppContext();
  const [repoPath, setRepoPath] = useState(repoState.repoPath || "");
  const [repoId, setRepoId] = useState(repoState.repoId || "");

  return (
    <div className="space-y-6">
      <ErrorAlert message={error} onClear={clearError} />
      {loading && <Loader label="Generating tests" />}
      <DiffPipelineForm
        repoPath={repoPath}
        repoId={repoId}
        onRepoPathChange={setRepoPath}
        onRepoIdChange={setRepoId}
        onGenerate={runGeneration}
        onUpdate={updateVectorstore}
      />
      <GeneratedTestsPanel prompts={prompts} />
    </div>
  );
}
