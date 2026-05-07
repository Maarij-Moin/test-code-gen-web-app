import { useMemo, useState } from "react";
import { FileCode2, ShieldCheck } from "lucide-react";

import { DiffViewer } from "@/components/diff/DiffViewer";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusPill } from "@/components/ui/StatusPill";
import type { GeneratedTest } from "@/types";

const sampleTests: GeneratedTest[] = [
  {
    id: "sample-auth",
    repo_id: "local-demo",
    file: "src/services/auth_service.py",
    function_name: "authenticate_user",
    old_code: "if not user:\n    return None\nreturn user",
    new_code: "if not user or not user.is_active:\n    return None\nreturn user",
    prompt: "Generate tests that prove inactive users cannot authenticate and active users with valid credentials still receive access.",
    validation: {
      status: "passed",
      score: 94,
      assertions: 5,
      risks: [],
      summary: "Covers the added inactive-user branch and preserves existing success behavior.",
    },
  },
];

export function GeneratedTestsViewer() {
  const [selectedId, setSelectedId] = useState(sampleTests[0]?.id);
  const selected = useMemo(() => sampleTests.find((test) => test.id === selectedId), [selectedId]);

  return (
    <main className="space-y-6 px-4 py-6 md:px-8">
      <div>
        <h1 className="text-3xl font-bold tracking-normal text-text">Generated tests viewer</h1>
        <p className="mt-2 text-sm text-muted">Review generated prompts, source diffs, and validation reports before PR publication.</p>
      </div>
      <div className="grid gap-6 xl:grid-cols-[360px_1fr]">
        <Card>
          <CardHeader><h2 className="text-lg font-semibold text-text">Generated artifacts</h2></CardHeader>
          <CardContent className="space-y-2">
            {sampleTests.map((test) => (
              <button key={test.id} onClick={() => setSelectedId(test.id)} className={`focus-ring w-full rounded-md border p-3 text-left transition ${selectedId === test.id ? "border-brand bg-brand/10" : "border-border bg-panel2 hover:border-brand/50"}`}>
                <p className="truncate text-sm font-semibold text-text">{test.file}</p>
                <p className="mt-1 truncate text-xs text-muted">{test.function_name}</p>
              </button>
            ))}
          </CardContent>
        </Card>
        {selected ? (
          <Card>
            <CardHeader className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
              <div>
                <h2 className="text-lg font-semibold text-text">{selected.file}</h2>
                <p className="mt-1 text-sm text-muted">{selected.function_name}</p>
              </div>
              <StatusPill status={selected.validation?.status === "passed" ? "succeeded" : "queued"} />
            </CardHeader>
            <CardContent className="space-y-5">
              <DiffViewer oldCode={selected.old_code} newCode={selected.new_code} />
              <section className="grid gap-4 md:grid-cols-[1fr_280px]">
                <div className="rounded-lg border border-border bg-panel2 p-4">
                  <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-text"><FileCode2 size={16} /> Generated test prompt</div>
                  <p className="whitespace-pre-wrap text-sm leading-6 text-muted">{selected.prompt}</p>
                </div>
                <div className="rounded-lg border border-border bg-panel2 p-4">
                  <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-text"><ShieldCheck size={16} /> Validation report</div>
                  <p className="text-3xl font-bold text-text">{selected.validation?.score}%</p>
                  <p className="mt-2 text-sm text-muted">{selected.validation?.summary}</p>
                  <p className="mt-4 text-xs font-semibold uppercase text-muted">Assertions: {selected.validation?.assertions}</p>
                </div>
              </section>
            </CardContent>
          </Card>
        ) : (
          <EmptyState icon={<FileCode2 size={28} />} title="No generated tests selected" description="Choose a generated artifact to inspect its diff and validation details." />
        )}
      </div>
    </main>
  );
}
