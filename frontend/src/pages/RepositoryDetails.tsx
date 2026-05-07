import { useMutation } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, GitBranch, Play, RefreshCw, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusPill } from "@/components/ui/StatusPill";
import { DiffViewer } from "@/components/diff/DiffViewer";
import { useRepository } from "@/hooks/useRepositories";
import { testService } from "@/services/testService";
import { formatDateTime } from "@/utils/format";

export function RepositoryDetails() {
  const { repoId } = useParams();
  const repository = useRepository(repoId);
  const generate = useMutation({
    mutationFn: () => testService.generate(repository.data?.repo_path ?? "", repository.data?.repo_id ?? ""),
  });

  if (repository.isLoading) {
    return <main className="px-4 py-6 md:px-8">Loading repository...</main>;
  }

  if (!repository.data) {
    return (
      <main className="px-4 py-6 md:px-8">
        <EmptyState icon={<GitBranch size={28} />} title="Repository unavailable" description="The selected repository was not found in the local workspace cache." />
      </main>
    );
  }

  return (
    <main className="space-y-6 px-4 py-6 md:px-8">
      <Link to="/" className="inline-flex items-center gap-2 text-sm font-semibold text-brand hover:underline">
        <ArrowLeft size={16} />
        Back to dashboard
      </Link>
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div>
          <h1 className="text-3xl font-bold tracking-normal text-text">{repository.data.name}</h1>
          <p className="mt-2 max-w-3xl break-all text-sm text-muted">{repository.data.repo_url}</p>
        </div>
        <StatusPill status={repository.data.status} />
      </div>

      <section className="grid gap-4 md:grid-cols-3">
        <Card><CardContent><p className="text-sm text-muted">Repo ID</p><p className="mt-2 break-all font-mono text-sm text-text">{repository.data.repo_id}</p></CardContent></Card>
        <Card><CardContent><p className="text-sm text-muted">Local path</p><p className="mt-2 break-all font-mono text-sm text-text">{repository.data.repo_path}</p></CardContent></Card>
        <Card><CardContent><p className="text-sm text-muted">Last indexed</p><p className="mt-2 text-sm font-semibold text-text">{formatDateTime(repository.data.last_indexed_at)}</p></CardContent></Card>
      </section>

      <Card>
        <CardHeader className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
          <div>
            <h2 className="text-lg font-semibold text-text">Generate tests from latest diff</h2>
            <p className="mt-1 text-sm text-muted">Runs the backend diff pipeline and renders generated prompts with validation context.</p>
          </div>
          <Button onClick={() => generate.mutate()} disabled={generate.isPending}>
            {generate.isPending ? <RefreshCw className="animate-spin" size={16} /> : <Play size={16} />}
            {generate.isPending ? "Generating..." : "Run generation"}
          </Button>
        </CardHeader>
        <CardContent>
          {generate.data?.length ? (
            <div className="space-y-5">
              {generate.data.map((test) => (
                <div key={test.id} className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-text">{test.file}</p>
                      <p className="text-sm text-muted">{test.function_name}</p>
                    </div>
                    {test.validation ? <StatusPill status={test.validation.status === "passed" ? "succeeded" : test.validation.status === "failed" ? "failed" : "queued"} /> : null}
                  </div>
                  <DiffViewer oldCode={test.old_code} newCode={test.new_code} />
                  <div className="rounded-lg border border-border bg-panel2 p-4">
                    <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-text"><ShieldCheck size={16} /> Generated prompt</div>
                    <p className="whitespace-pre-wrap text-sm leading-6 text-muted">{test.prompt}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState icon={<Play size={28} />} title="No generation run yet" description="Run the diff pipeline to inspect generated prompts and validation reports for this repository." />
          )}
        </CardContent>
      </Card>
    </main>
  );
}
