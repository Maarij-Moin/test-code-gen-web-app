import { useCallback, useState } from "react";
import { semanticSearch } from "../api/queryApi.js";
import { useAppContext } from "../context/AppContext.jsx";

export function useQuery() {
  const { setLoading, setError, addActivity } = useAppContext();
  const [results, setResults] = useState([]);

  const runSearch = useCallback(
    async (repoId, query, k) => {
      setLoading(true);
      setError("");
      try {
        const data = await semanticSearch(repoId, query, k);
        const items = data.code_chunks || [];
        setResults(items);
        addActivity({ type: "search", message: "Semantic search completed." });
        return items;
      } catch (err) {
        setError(err.message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [setLoading, setError, addActivity]
  );

  return { results, runSearch };
}
