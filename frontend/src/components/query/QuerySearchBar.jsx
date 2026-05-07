import { useState } from "react";
import { Search } from "lucide-react";
import Button from "../common/Button.jsx";

export default function QuerySearchBar({ onSearch }) {
  const [query, setQuery] = useState("");
  const [k, setK] = useState(5);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!query) return;
    await onSearch(query, k);
  };

  return (
    <form className="card" onSubmit={handleSubmit}>
      <div className="flex items-center gap-2">
        <Search size={18} className="text-brand" />
        <h3 className="text-lg font-semibold">Semantic Search</h3>
      </div>
      <div className="mt-4 flex flex-col gap-3 md:flex-row">
        <input
          className="input"
          placeholder="Search for a symbol, class, or behavior"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <input
          className="input md:w-28"
          type="number"
          min="1"
          max="20"
          value={k}
          onChange={(event) => setK(Number(event.target.value))}
        />
        <Button variant="primary" type="submit">
          Run Search
        </Button>
      </div>
    </form>
  );
}
