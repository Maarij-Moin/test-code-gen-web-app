import RepoUploadForm from "../components/repo/RepoUploadForm.jsx";
import RepoIndexCard from "../components/repo/RepoIndexCard.jsx";
import RepoStatusCard from "../components/repo/RepoStatusCard.jsx";
import ErrorAlert from "../components/common/ErrorAlert.jsx";
import Loader from "../components/common/Loader.jsx";
import { useAppContext } from "../context/AppContext.jsx";

export default function RepoPage() {
  const { loading, error, clearError } = useAppContext();

  return (
    <div className="space-y-6">
      <ErrorAlert message={error} onClear={clearError} />
      {loading && <Loader label="Processing repository" />}
      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <RepoUploadForm />
        <RepoStatusCard />
      </div>
      <RepoIndexCard />
    </div>
  );
}
