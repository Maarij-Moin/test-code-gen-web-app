import { FileCode2 } from "lucide-react";
import { truncate } from "../../utils/helpers.js";

export default function ResultCard({ item }) {
  return (
    <div className="card">
      <div className="flex items-center gap-2">
        <FileCode2 size={16} className="text-brand" />
        <p className="text-sm font-semibold">{item.metadata?.file_path || "Unknown file"}</p>
      </div>
      <p className="mt-3 text-sm text-muted">{truncate(item.content || "", 320)}</p>
      <div className="mt-4 flex flex-wrap gap-2 text-xs text-muted">
        <span className="badge">{item.metadata?.language || "Unknown"}</span>
        <span className="badge">{item.metadata?.chunk_strategy || "unit"}</span>
        <span className="badge">{item.metadata?.unit_name || "n/a"}</span>
      </div>
    </div>
  );
}
