import { useCallback, useState } from "react";
import {
  generateTests,
  queryTestChunks,
  updateTestVectorstore
} from "../api/testApi.js";
import { useAppContext } from "../context/AppContext.jsx";

export function useTests() {
  const { setLoading, setError, addActivity } = useAppContext();
  const [prompts, setPrompts] = useState([]);
  const [testResults, setTestResults] = useState([]);

  const runGeneration = useCallback(
    async (repoPath, repoId) => {
      setLoading(true);
      setError("");
      try {
        const data = await generateTests(repoPath, repoId);
        setPrompts(data.results || []);
        addActivity({ type: "tests", message: "Test prompts generated." });
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

  const updateVectorstore = useCallback(
    async (repoPath, repoId) => {
      setLoading(true);
      setError("");
      try {
        const data = await updateTestVectorstore(repoPath, repoId);
        addActivity({ type: "update", message: "Vectorstore updated." });
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

  const queryTests = useCallback(
    async (repoId, query, k) => {
      setLoading(true);
      setError("");
      try {
        const data = await queryTestChunks(repoId, query, k);
        setTestResults(data.results || []);
        addActivity({ type: "query-tests", message: "Test chunks retrieved." });
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
    prompts,
    testResults,
    runGeneration,
    updateVectorstore,
    queryTests
  };
}
