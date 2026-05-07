import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, Boxes, GitBranch, GitPullRequest, Plus, TestTube2 } from "lucide-react";

import { MetricCard } from "@/components/dashboard/MetricCard";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { StatusPill } from "@/components/ui/StatusPill";
import { useJobs } from "@/hooks/useJobs";
import { usePullRequests } from "@/hooks/usePullRequests";
import { useConnectRepository, useRepositories } from "@/hooks/useRepositories";
import { getApiErrorMessage } from "@/lib/apiClient";
import { formatDateTime } from "@/utils/format";

export function Dashboard() {
  const repositories = useRepositories();
  const jobs = useJobs();
  const pullRequests = usePullRequests();
  const connectRepository = useConnectRepository();
  const [repoUrl, setRepoUrl] = useState("");

  async function handleConnect(event: FormEvent) {
    event.preventDefault();
    await connectRepository.mutateAsync(repoUrl);
    setRepoUrl("");
  }

  const repoCount = repositories.data?.length ?? 0;
  const runningJobs = jobs.data?.filter((job) => job.status === "running").length ?? 0;
  const generatedJobs = jobs.data?.filter((job) => job.type === "generate").length ?? 0;
  const activePrs = pullRequests.data?.filter((pr) => pr.status === "open" || pr.status === "draft").length ?? 0;

  return (
    <main className="space-y-6 px-4 py-6 md:px-8">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <h1 className="text-3xl font-bold tracking-normal text-text">Dashboard</h1>
          <p className="mt-2 text-sm text-muted">Connect repositories and supervise autonomous testing workflows.</p>
        </div>
      </div>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Repositories" value={repoCount} helper="Connected in this workspace" icon={<GitBranch size={20} />} />
        <MetricCard label="Running jobs" value={runningJobs} helper="Live generation or validation" icon={<Activity size={20} />} />
        <MetricCard label="Generated suites" value={generatedJobs} helper="Recent generation jobs" icon={<TestTube2 size={20} />} />
        <MetricCard label="Active PRs" value={activePrs} helper="Open or draft monitored PRs" icon={<GitPullRequest size={20} />} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-text">Repository connection</h2>
            <p className="mt-1 text-sm text-muted">Clone and index a Git repository through the backend pipeline.</p>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleConnect}>
              <Input label="Git repository URL" type="url" placeholder="https://github.com/org/project.git" value={repoUrl} onChange={(event) => setRepoUrl(event.target.value)} required />
              {connectRepository.isError ? <p className="rounded-md bg-danger/10 p-3 text-sm text-danger">{getApiErrorMessage(connectRepository.error, "Repository connection failed")}</p> : null}
              <Button type="submit" disabled={connectRepository.isPending}>
                <Plus size={16} />
                {connectRepository.isPending ? "Connecting..." : "Connect repository"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-text">Connected repositories</h2>
          </CardHeader>
          <CardContent>
            {repoCount === 0 ? (
              <EmptyState icon={<Boxes size={28} />} title="No repositories connected" description="Connect a repository to generate tests from code diffs and monitor its automation jobs." />
            ) : (
              <div className="divide-y divide-border">
                {repositories.data?.map((repository) => (
                  <Link key={repository.repo_id} to={`/repositories/${repository.repo_id}`} className="flex flex-col gap-3 py-4 transition hover:bg-panel2/60 md:flex-row md:items-center md:justify-between">
                    <div className="min-w-0 px-2">
                      <p className="truncate font-semibold text-text">{repository.name}</p>
                      <p className="truncate text-sm text-muted">{repository.repo_url}</p>
                    </div>
                    <div className="flex items-center gap-3 px-2">
                      <StatusPill status={repository.status} />
                      <span className="text-xs text-muted">{formatDateTime(repository.last_indexed_at)}</span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
