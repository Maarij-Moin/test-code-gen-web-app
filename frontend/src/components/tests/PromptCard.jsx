import { useState } from "react";
import { ChevronDown, Copy } from "lucide-react";
import Button from "../common/Button.jsx";
import { safeCopy } from "../../utils/helpers.js";

export default function PromptCard({ prompt }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await safeCopy(prompt.prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold">{prompt.file}</p>
          <p className="text-xs text-muted">{prompt.function_name}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={handleCopy}>{copied ? "Copied" : "Copy"}</Button>
          <button
            className="btn"
            onClick={() => setOpen((prev) => !prev)}
            aria-expanded={open}
          >
            <ChevronDown size={16} className={open ? "rotate-180" : ""} />
          </button>
        </div>
      </div>
      {open && (
        <div className="mt-4 whitespace-pre-wrap rounded-xl border border-border bg-panel-2 p-4 text-xs text-muted">
          {prompt.prompt}
        </div>
      )}
    </div>
  );
}
