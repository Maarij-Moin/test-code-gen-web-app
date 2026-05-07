function splitLines(value: string) {
  return value ? value.split("\n") : ["No code captured"];
}

export function DiffViewer({ oldCode, newCode }: { oldCode: string; newCode: string }) {
  const oldLines = splitLines(oldCode);
  const newLines = splitLines(newCode);
  const max = Math.max(oldLines.length, newLines.length);

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-panel font-mono text-xs">
      <div className="grid grid-cols-1 border-b border-border bg-panel2 text-muted md:grid-cols-2">
        <div className="px-4 py-2">Before</div>
        <div className="border-t border-border px-4 py-2 md:border-l md:border-t-0">After</div>
      </div>
      <div className="grid max-h-[520px] grid-cols-1 overflow-auto md:grid-cols-2">
        <div>
          {Array.from({ length: max }).map((_, index) => (
            <pre key={`old-${index}`} className="min-h-7 overflow-x-auto border-b border-border/60 bg-danger/5 px-4 py-1 text-danger">
              <span className="mr-3 select-none text-muted">{index + 1}</span>
              - {oldLines[index] ?? ""}
            </pre>
          ))}
        </div>
        <div className="border-t border-border md:border-l md:border-t-0">
          {Array.from({ length: max }).map((_, index) => (
            <pre key={`new-${index}`} className="min-h-7 overflow-x-auto border-b border-border/60 bg-success/5 px-4 py-1 text-success">
              <span className="mr-3 select-none text-muted">{index + 1}</span>
              + {newLines[index] ?? ""}
            </pre>
          ))}
        </div>
      </div>
    </div>
  );
}
