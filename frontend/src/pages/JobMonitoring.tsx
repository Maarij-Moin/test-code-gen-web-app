import { Activity, Clock } from "lucide-react";

import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusPill } from "@/components/ui/StatusPill";
import { useJobs } from "@/hooks/useJobs";
import { formatDateTime, formatDuration, titleCase } from "@/utils/format";

export function JobMonitoring() {
  const jobs = useJobs();

  return (
    <main className="space-y-6 px-4 py-6 md:px-8">
      <div>
        <h1 className="text-3xl font-bold tracking-normal text-text">Job monitoring</h1>
        <p className="mt-2 text-sm text-muted">Live job status with websocket invalidation and polling fallback.</p>
      </div>
      {jobs.data?.length ? (
        <div className="grid gap-5">
          {jobs.data.map((job) => (
            <Card key={job.id}>
              <CardHeader className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <h2 className="text-lg font-semibold text-text">{job.repo_name}</h2>
                    <StatusPill status={job.status} />
                  </div>
                  <p className="mt-1 text-sm text-muted">{titleCase(job.type)} job • {job.message}</p>
                </div>
                <div className="flex items-center gap-2 text-sm text-muted"><Clock size={16} /> {formatDateTime(job.started_at)}</div>
              </CardHeader>
              <CardContent>
                <div className="mb-5 h-2 overflow-hidden rounded-full bg-panel2">
                  <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${job.progress}%` }} />
                </div>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  {job.steps.map((step) => (
                    <div key={step.name} className="rounded-md border border-border bg-panel2 p-3">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-text">{step.name}</p>
                        <StatusPill status={step.status} />
                      </div>
                      <p className="mt-2 text-xs text-muted">{formatDuration(step.duration_ms)}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState icon={<Activity size={28} />} title="No jobs yet" description="Repository indexing and test-generation jobs will appear here as they run." />
      )}
    </main>
  );
}
