import ResultCard from "./ResultCard.jsx";
import EmptyState from "../common/EmptyState.jsx";

export default function QueryResults({ results }) {
  if (!results?.length) {
    return (
      <EmptyState
        title="No results yet"
        message="Run a query to see related code chunks and metadata."
      />
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {results.map((item, index) => (
        <ResultCard key={index} item={item} />
      ))}
    </div>
  );
}
