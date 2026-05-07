import { useCallback, useState } from "react";
import {
  cloneAndIndex,
  indexRepo,
  runDiffPipeline,
  updateRepo,
  uploadRepo
} from "../api/repoApi.js";
import { useAppContext } from "../context/AppContext.jsx";
import { useRepoContext } from "../context/RepoContext.jsx";

export function useRepo() {
  const { setLoading, setError, addActivity } = useAppContext();
  const { repoState, setRepoState } = useRepoContext();
  const [diffResults, setDiffResults] = useState([]);

  const updateState = useCallback(
    (data) =>
      setRepoState((prev) => ({
        ...prev,
        ...data,
        lastUpdated: new Date().toISOString()
      })),
    [setRepoState]
  );

  const cloneRepository = useCallback(
    async (repoUrl) => {
      setLoading(true);
      setError("");
      try {
        const data = await uploadRepo(repoUrl);
        updateState({ repoPath: data.repo_path, status: "cloned" });
        addActivity({ type: "clone", message: data.message });
        return data;
      } catch (err) {
        setError(err.message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [setLoading, setError, addActivity, updateState]
  );

  const indexRepository = useCallback(
    async (repoPath) => {
      setLoading(true);
      setError("");
      try {
        const data = await indexRepo(repoPath);
        updateState({ repoId: data.repo_id, status: "indexed", repoPath });
        addActivity({ type: "index", message: data.message });
        return data;
      } catch (err) {
        setError(err.message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [setLoading, setError, addActivity, updateState]
  );

  const cloneAndIndexRepo = useCallback(
    async (repoUrl) => {
      setLoading(true);
      setError("");
      try {
        const data = await cloneAndIndex(repoUrl);
        updateState({
          repoId: data.repo_id,
          repoPath: data.repo_path,
          status: "indexed"
        });
        addActivity({ type: "clone-index", message: data.message });
        return data;
      } catch (err) {
        setError(err.message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [setLoading, setError, addActivity, updateState]
  );

  const runPipeline = useCallback(
    async (repoPath, repoId) => {
      setLoading(true);
      setError("");
      try {
        const data = await runDiffPipeline(repoPath, repoId);
        setDiffResults(data.results || []);
        addActivity({ type: "diff", message: "Diff pipeline completed." });
        return data;
      } catch (err) {
        setError(err.message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [setLoading, setError, addActivity]
  );

  const updateIndex = useCallback(
    async (repoPath, repoId) => {
      setLoading(true);
      setError("");
      try {
        const data = await updateRepo(repoPath, repoId);
        addActivity({ type: "update", message: data.message });
        return data;
      } catch (err) {
        setError(err.message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [setLoading, setError, addActivity]
  );

  return {
    repoState,
    diffResults,
    cloneRepository,
    indexRepository,
    cloneAndIndexRepo,
    runPipeline,
    updateIndex
  };
}
