import { ExternalLink, GitPullRequest } from "lucide-react";

import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusPill } from "@/components/ui/StatusPill";
import { usePullRequests } from "@/hooks/usePullRequests";
import { formatDateTime } from "@/utils/format";

export function PullRequestMonitor() {
  const pullRequests = usePullRequests();

  return (
    <main className="space-y-6 px-4 py-6 md:px-8">
      <div>
        <h1 className="text-3xl font-bold tracking-normal text-text">Pull request monitor</h1>
        <p className="mt-2 text-sm text-muted">Track generated-test PRs, links, and validation check states.</p>
      </div>
      <Card>
        <CardHeader><h2 className="text-lg font-semibold text-text">Automation pull requests</h2></CardHeader>
        <CardContent>
          {pullRequests.data?.length ? (
            <div className="divide-y divide-border">
              {pullRequests.data.map((pr) => (
                <div key={pr.id} className="flex flex-col gap-4 py-4 md:flex-row md:items-center md:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold text-text">#{pr.number} {pr.title}</p>
                      <StatusPill status={pr.status} />
                      <StatusPill status={pr.checks} />
                    </div>
                    <p className="mt-1 text-sm text-muted">By {pr.author} • Updated {formatDateTime(pr.updated_at)}</p>
                  </div>
                  <a href={pr.url} target="_blank" rel="noreferrer" className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-md border border-border px-4 text-sm font-semibold text-text transition hover:bg-panel2">
                    <ExternalLink size={16} />
                    Open PR
                  </a>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState icon={<GitPullRequest size={28} />} title="No pull requests monitored" description="Generated test pull requests will appear here when the backend PR agent publishes them." />
          )}
        </CardContent>
      </Card>
    </main>
  );
}
