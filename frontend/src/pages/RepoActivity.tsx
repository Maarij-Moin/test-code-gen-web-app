import { useState } from "react";
import { AlertTriangle, CheckCircle2, Clock, GitMerge, Github, Webhook, XCircle, Zap } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { useWebhookHealth, useWebhookEvents } from "@/hooks/useWebhook";
import { formatDateTime } from "@/utils/format";

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${ok ? "bg-success" : "bg-danger"}`}
    />
  );
}

function EventRow({
  type,
  delivery_id,
  status,
  commit_sha,
  branch,
  created_at,
  error_message,
}: {
  type: string;
  delivery_id: string | null;
  status: string;
  commit_sha: string | null;
  branch: string | null;
  created_at: string;
  error_message: string | null;
}) {
  const ok = status !== "failed" && !error_message;
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border bg-panel p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        {ok ? (
          <CheckCircle2 size={16} className="shrink-0 text-success" />
        ) : (
          <XCircle size={16} className="shrink-0 text-danger" />
        )}
        <div>
          <p className="text-sm font-semibold text-text capitalize">{type}</p>
          {branch && <p className="text-xs text-muted">Branch: {branch}</p>}
          {commit_sha && (
            <p className="font-mono text-xs text-muted">{commit_sha.slice(0, 10)}…</p>
          )}
          {error_message && (
            <p className="text-xs text-danger">{error_message}</p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3 text-xs text-muted">
        <span className="flex items-center gap-1">
          <Clock size={12} /> {formatDateTime(created_at)}
        </span>
        {delivery_id && (
          <span className="hidden font-mono text-xs text-muted sm:block">
            #{delivery_id.slice(0, 8)}
          </span>
        )}
      </div>
    </div>
  );
}

export function RepoActivity() {
  const health = useWebhookHealth();
  const events = useWebhookEvents();

  const isHealthy = health.data?.status === "ok" && health.data.secret_configured;

  return (
    <main className="space-y-6 px-4 py-6 md:px-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-text">Repo Activity</h1>
        <p className="mt-1 text-sm text-muted">
          GitHub webhook health and incoming event log.
        </p>
      </div>

      {/* Webhook health card */}
      <div className="grid gap-5 md:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2 text-sm font-semibold text-text">
              <Webhook size={16} /> Webhook Status
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {health.isLoading ? (
              <div className="space-y-2">
                <div className="h-4 w-3/4 animate-pulse rounded bg-panel2" />
                <div className="h-4 w-1/2 animate-pulse rounded bg-panel2" />
              </div>
            ) : health.isError ? (
              <p className="text-sm text-danger">Could not reach webhook health endpoint.</p>
            ) : (
              <>
                <div className="flex items-center gap-2">
                  <StatusDot ok={isHealthy} />
                  <span className="text-sm font-medium text-text">
                    {isHealthy ? "Fully operational" : "Configuration incomplete"}
                  </span>
                </div>
                <div className="divide-y divide-border rounded-lg border border-border">
                  {[
                    {
                      label: "Signature verification",
                      value: health.data?.signature_verification ?? "—",
                      ok: health.data?.secret_configured,
                    },
                    {
                      label: "Replay protection",
                      value: health.data?.replay_protection ?? "—",
                      ok: true,
                    },
                    {
                      label: "Webhook path",
                      value: health.data?.webhook_path ?? "—",
                      ok: true,
                    },
                  ].map(({ label, value, ok }) => (
                    <div key={label} className="flex items-center justify-between px-4 py-2.5">
                      <span className="text-sm text-muted">{label}</span>
                      <div className="flex items-center gap-2">
                        <StatusDot ok={!!ok} />
                        <span className="max-w-[180px] truncate text-xs font-medium text-text">{String(value)}</span>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="rounded-lg bg-panel2 p-3">
                  <p className="text-xs text-muted">Supported events</p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {(health.data?.supported_events ?? []).map((ev) => (
                      <span
                        key={ev}
                        className="rounded-md bg-brand/10 px-2 py-0.5 text-xs font-medium text-brand"
                      >
                        {ev}
                      </span>
                    ))}
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Setup guide */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2 text-sm font-semibold text-text">
              <Github size={16} /> GitHub Setup
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {!health.data?.secret_configured && (
              <div className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 p-3">
                <AlertTriangle size={15} className="mt-0.5 shrink-0 text-warning" />
                <p className="text-sm text-warning">
                  <strong>GITHUB_WEBHOOK_SECRET</strong> is not set. Signature verification is disabled.
                </p>
              </div>
            )}
            <ol className="space-y-3 text-sm text-muted">
              {[
                {
                  icon: <Github size={14} />,
                  text: "Go to your repository → Settings → Webhooks → Add webhook",
                },
                {
                  icon: <Zap size={14} />,
                  text: `Payload URL: ${window.location.origin.replace("3000", "8000")}/webhooks/github`,
                },
                {
                  icon: <CheckCircle2 size={14} className="text-success" />,
                  text: "Content type: application/json",
                },
                {
                  icon: <GitMerge size={14} />,
                  text: "Events: ✅ Pushes, ✅ Pull requests",
                },
              ].map(({ icon, text }, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="mt-0.5 shrink-0 text-brand">{icon}</span>
                  <span>{text}</span>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      </div>

      {/* Event log */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-text">
              Recent Events ({events.data?.length ?? 0})
            </h2>
            <span className="flex items-center gap-1 text-xs text-muted">
              <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
              Polling every 10s
            </span>
          </div>
        </CardHeader>
        <CardContent>
          {events.isLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 animate-pulse rounded-xl bg-panel2" />
              ))}
            </div>
          ) : (events.data ?? []).length > 0 ? (
            <div className="space-y-2">
              {events.data!.map((ev) => (
                <EventRow key={ev.id} {...ev} type={ev.event_type} />
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<Webhook size={28} />}
              title="No webhook events yet"
              description="Configure the GitHub webhook above and push a commit to see events appear here."
            />
          )}
        </CardContent>
      </Card>
    </main>
  );
}
