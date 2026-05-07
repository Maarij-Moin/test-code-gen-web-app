import QuerySearchBar from "../components/query/QuerySearchBar.jsx";
import QueryResults from "../components/query/QueryResults.jsx";
import ErrorAlert from "../components/common/ErrorAlert.jsx";
import Loader from "../components/common/Loader.jsx";
import { useQuery } from "../hooks/useQuery.js";
import { useRepoContext } from "../context/RepoContext.jsx";
import { useAppContext } from "../context/AppContext.jsx";

export default function QueryPage() {
  const { runSearch, results } = useQuery();
  const { repoState } = useRepoContext();
  const { loading, error, clearError } = useAppContext();

  const handleSearch = async (query, k) => {
    if (!repoState.repoId) return;
    await runSearch(repoState.repoId, query, k);
  };

  return (
    <div className="space-y-6">
      <ErrorAlert message={error} onClear={clearError} />
      {loading && <Loader label="Searching" />}
      <QuerySearchBar onSearch={handleSearch} />
      <QueryResults results={results} />
    </div>
  );
}
