import { useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Filter,
  RefreshCw,
  Search,
  XCircle,
} from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusPill } from "@/components/ui/StatusPill";
import { useJobs } from "@/hooks/useJobs";
import { formatDateTime, formatDuration, titleCase } from "@/utils/format";
import type { Job, JobStatus } from "@/types";

const STATUS_FILTERS: Array<{ value: "all" | JobStatus; label: string }> = [
  { value: "all", label: "All" },
  { value: "running", label: "Running" },
  { value: "queued", label: "Queued" },
  { value: "succeeded", label: "Succeeded" },
  { value: "failed", label: "Failed" },
];

function StepIcon({ status }: { status: JobStatus }) {
  if (status === "succeeded") return <CheckCircle2 size={14} className="text-success" />;
  if (status === "failed") return <XCircle size={14} className="text-danger" />;
  if (status === "running") return <RefreshCw size={14} className="animate-spin text-brand" />;
  return <AlertTriangle size={14} className="text-muted" />;
}

function ProgressBar({ value, status }: { value: number; status: JobStatus }) {
  const color =
    status === "succeeded"
      ? "bg-success"
      : status === "failed"
        ? "bg-danger"
        : status === "running"
          ? "bg-brand"
          : "bg-muted";

  return (
    <div className="h-2 overflow-hidden rounded-full bg-panel2">
      <div
        className={`h-full rounded-full transition-all duration-500 ${color} ${status === "running" ? "animate-pulse" : ""}`}
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

function JobCard({ job }: { job: Job }) {
  const elapsed =
    job.finished_at
      ? Date.parse(job.finished_at) - Date.parse(job.started_at)
      : Date.now() - Date.parse(job.started_at);

  return (
    <Card>
      <CardHeader className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-bold text-text">{job.repo_name}</h2>
            <span className="rounded-md bg-panel2 px-2 py-0.5 text-xs font-medium text-muted">
              {titleCase(job.type)}
            </span>
            <StatusPill status={job.status} />
          </div>
          {job.message && (
            <p className="mt-1 truncate text-sm text-muted">{job.message}</p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-4 text-xs text-muted">
          <span className="flex items-center gap-1">
            <Clock size={13} /> {formatDateTime(job.started_at)}
          </span>
          <span className="font-mono">{formatDuration(elapsed)}</span>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Progress */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs text-muted">
            <span>Progress</span>
            <span>{job.progress}%</span>
          </div>
          <ProgressBar value={job.progress} status={job.status} />
        </div>

        {/* Steps */}
        {job.steps.length > 0 && (
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {job.steps.map((step) => (
              <div
                key={step.name}
                className="rounded-lg border border-border bg-panel2 p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs font-semibold leading-tight text-text">{step.name}</p>
                  <StepIcon status={step.status} />
                </div>
                {step.duration_ms != null && (
                  <p className="mt-1.5 text-xs text-muted">{formatDuration(step.duration_ms)}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function JobMonitoring() {
  const jobs = useJobs();
  const [statusFilter, setStatusFilter] = useState<"all" | JobStatus>("all");
  const [search, setSearch] = useState("");

  const filtered = (jobs.data ?? []).filter((job) => {
    const matchStatus = statusFilter === "all" || job.status === statusFilter;
    const matchSearch =
      !search ||
      job.repo_name.toLowerCase().includes(search.toLowerCase()) ||
      job.type.toLowerCase().includes(search.toLowerCase());
    return matchStatus && matchSearch;
  });

  const counts = {
    running: jobs.data?.filter((j) => j.status === "running").length ?? 0,
    queued: jobs.data?.filter((j) => j.status === "queued").length ?? 0,
    succeeded: jobs.data?.filter((j) => j.status === "succeeded").length ?? 0,
    failed: jobs.data?.filter((j) => j.status === "failed").length ?? 0,
  };

  return (
    <main className="space-y-6 px-4 py-6 md:px-8">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-text">Job Monitoring</h1>
          <p className="mt-1 text-sm text-muted">
            Live job status with 5-second polling fallback.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted">
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-success" /> Live
          </span>
          <span>·</span>
          <span>Auto-refresh 5s</span>
        </div>
      </div>

      {/* Stat pills */}
      <div className="flex flex-wrap gap-3">
        {[
          { label: "Running", count: counts.running, color: "text-brand" },
          { label: "Queued", count: counts.queued, color: "text-muted" },
          { label: "Succeeded", count: counts.succeeded, color: "text-success" },
          { label: "Failed", count: counts.failed, color: "text-danger" },
        ].map(({ label, count, color }) => (
          <div key={label} className="rounded-lg border border-border bg-panel px-4 py-2">
            <p className="text-xs text-muted">{label}</p>
            <p className={`text-xl font-bold ${color}`}>{count}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            type="text"
            placeholder="Search jobs…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="rounded-lg border border-border bg-panel py-2 pl-9 pr-4 text-sm text-text placeholder:text-muted focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
          />
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-border bg-panel p-1">
          <Filter size={13} className="ml-2 text-muted" />
          {STATUS_FILTERS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => setStatusFilter(value)}
              className={`rounded-md px-3 py-1 text-xs font-medium transition ${
                statusFilter === value
                  ? "bg-brand text-white"
                  : "text-muted hover:text-text"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Job cards */}
      {jobs.isLoading ? (
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div key={i} className="h-40 animate-pulse rounded-xl bg-panel" />
          ))}
        </div>
      ) : filtered.length > 0 ? (
        <div className="space-y-4">
          {filtered.map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Activity size={28} />}
          title="No jobs match"
          description="Try changing your filter or connect a repository to trigger your first job."
        />
      )}
    </main>
  );
}
