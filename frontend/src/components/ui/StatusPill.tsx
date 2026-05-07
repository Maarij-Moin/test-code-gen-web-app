import type { JobStatus } from "@/types";
import { titleCase } from "@/utils/format";

type Status = JobStatus | "connected" | "indexing" | "idle" | "open" | "merged" | "closed" | "draft" | "passing" | "pending" | "failing";

const styles: Record<string, string> = {
  succeeded: "bg-success/10 text-success ring-success/20",
  connected: "bg-success/10 text-success ring-success/20",
  passing: "bg-success/10 text-success ring-success/20",
  running: "bg-brand/10 text-brand ring-brand/20",
  indexing: "bg-brand/10 text-brand ring-brand/20",
  open: "bg-brand/10 text-brand ring-brand/20",
  queued: "bg-warning/10 text-warning ring-warning/20",
  pending: "bg-warning/10 text-warning ring-warning/20",
  draft: "bg-warning/10 text-warning ring-warning/20",
  failed: "bg-danger/10 text-danger ring-danger/20",
  failing: "bg-danger/10 text-danger ring-danger/20",
  cancelled: "bg-muted/10 text-muted ring-muted/20",
  closed: "bg-muted/10 text-muted ring-muted/20",
  merged: "bg-brand2/10 text-brand2 ring-brand2/20",
  idle: "bg-muted/10 text-muted ring-muted/20",
};

export function StatusPill({ status }: { status: Status }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${styles[status] ?? styles.idle}`}>
      {titleCase(status)}
    </span>
  );
}
