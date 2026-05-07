import { useState } from "react";
import { CheckCircle2, FileCode2, Search, ShieldCheck, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusPill } from "@/components/ui/StatusPill";
import { DiffViewer } from "@/components/diff/DiffViewer";
import type { GeneratedTest } from "@/types";

// ---------- Sample data (replaced by real API when wired) ----------
const SAMPLE: GeneratedTest[] = [
  {
    id: "gt-001",
    repo_id: "demo",
    file: "src/services/auth_service.py",
    function_name: "authenticate_user",
    old_code: "if not user:\n    return None\nreturn user",
    new_code: "if not user or not user.is_active:\n    return None\nreturn user",
    prompt:
      "Generate pytest tests covering: inactive user rejection, active user success, missing user returns None.",
    validation: { status: "passed", score: 94, assertions: 5, risks: [], summary: "All branches covered." },
  },
  {
    id: "gt-002",
    repo_id: "demo",
    file: "src/api/billing.py",
    function_name: "calculate_invoice",
    old_code: "total = sum(items)",
    new_code: "total = sum(items) * (1 + tax_rate)",
    prompt: "Generate pytest tests for calculate_invoice with zero, positive, and negative tax rates.",
    validation: { status: "failed", score: 61, assertions: 3, risks: ["negative tax edge case"], summary: "Edge case for negative tax uncovered." },
  },
  {
    id: "gt-003",
    repo_id: "demo",
    file: "src/utils/formatter.ts",
    function_name: "formatCurrency",
    old_code: "return `$${amount}`",
    new_code: "return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount)",
    prompt: "Generate Jest tests for formatCurrency with USD, EUR, and zero amounts.",
    validation: { status: "passed", score: 88, assertions: 6, risks: [], summary: "Locale and currency switching verified." },
  },
];

function ScoreRing({ score, status }: { score: number; status: string }) {
  const color = status === "passed" ? "text-success" : status === "failed" ? "text-danger" : "text-warning";
  return (
    <div className="flex flex-col items-center">
      <span className={`text-4xl font-bold ${color}`}>{score}%</span>
      <span className="mt-1 text-xs text-muted">confidence</span>
    </div>
  );
}

export function GeneratedTestsViewer() {
  const [selectedId, setSelectedId] = useState(SAMPLE[0]?.id);
  const [search, setSearch] = useState("");
  const selected = SAMPLE.find((t) => t.id === selectedId);

  const filtered = SAMPLE.filter(
    (t) =>
      !search ||
      t.file.toLowerCase().includes(search.toLowerCase()) ||
      t.function_name.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <main className="space-y-6 px-4 py-6 md:px-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-text">Generated Tests</h1>
        <p className="mt-1 text-sm text-muted">
          Review AI-generated tests, diff context, and validation outcomes.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[340px_1fr]">
        {/* Sidebar list */}
        <div className="space-y-3">
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="text"
              placeholder="Search artifacts…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-lg border border-border bg-panel py-2 pl-9 pr-4 text-sm text-text placeholder:text-muted focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
            />
          </div>
          <Card>
            <CardHeader>
              <h2 className="text-sm font-semibold text-text">
                Artifacts ({filtered.length})
              </h2>
            </CardHeader>
            <CardContent className="space-y-2 p-3">
              {filtered.map((test) => (
                <button
                  key={test.id}
                  id={`test-item-${test.id}`}
                  onClick={() => setSelectedId(test.id)}
                  className={`w-full rounded-xl border p-3 text-left transition ${
                    selectedId === test.id
                      ? "border-brand bg-brand/10"
                      : "border-border bg-panel2 hover:border-brand/40"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="truncate text-xs font-bold text-text">{test.file}</p>
                    {test.validation?.status === "passed" ? (
                      <CheckCircle2 size={13} className="shrink-0 text-success" />
                    ) : (
                      <XCircle size={13} className="shrink-0 text-danger" />
                    )}
                  </div>
                  <p className="mt-0.5 truncate text-xs text-muted">{test.function_name}</p>
                </button>
              ))}
            </CardContent>
          </Card>
        </div>

        {/* Detail pane */}
        {selected ? (
          <div className="space-y-5">
            <Card>
              <CardHeader className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                <div>
                  <h2 className="font-bold text-text">{selected.file}</h2>
                  <p className="mt-0.5 font-mono text-sm text-muted">{selected.function_name}</p>
                </div>
                <StatusPill
                  status={
                    selected.validation?.status === "passed"
                      ? "succeeded"
                      : selected.validation?.status === "failed"
                        ? "failed"
                        : "queued"
                  }
                />
              </CardHeader>
              <CardContent>
                <DiffViewer oldCode={selected.old_code} newCode={selected.new_code} />
              </CardContent>
            </Card>

            <div className="grid gap-5 md:grid-cols-[1fr_220px]">
              {/* Prompt */}
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2 text-sm font-semibold text-text">
                    <FileCode2 size={15} /> LLM Prompt
                  </div>
                </CardHeader>
                <CardContent>
                  <pre className="whitespace-pre-wrap text-sm leading-6 text-muted">
                    {selected.prompt}
                  </pre>
                </CardContent>
              </Card>

              {/* Validation */}
              {selected.validation && (
                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-2 text-sm font-semibold text-text">
                      <ShieldCheck size={15} /> Validation
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4 text-center">
                    <ScoreRing score={selected.validation.score} status={selected.validation.status} />
                    <div className="rounded-lg bg-panel2 p-3 text-left">
                      <p className="text-xs font-semibold text-muted uppercase">Summary</p>
                      <p className="mt-1 text-sm text-text">{selected.validation.summary}</p>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted">Assertions</span>
                      <span className="font-bold text-text">{selected.validation.assertions}</span>
                    </div>
                    {selected.validation.risks.length > 0 && (
                      <div className="rounded-lg bg-warning/10 p-3 text-left">
                        <p className="text-xs font-semibold text-warning">Risks</p>
                        <ul className="mt-1 space-y-0.5 text-xs text-text">
                          {selected.validation.risks.map((r) => (
                            <li key={r}>• {r}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        ) : (
          <EmptyState
            icon={<FileCode2 size={28} />}
            title="Select an artifact"
            description="Choose a generated test from the list to review its diff, prompt, and validation report."
          />
        )}
      </div>
    </main>
  );
}
