import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/Card";

type Props = {
  label: string;
  value: string | number;
  helper: string;
  icon: ReactNode;
  highlight?: boolean;
  trend?: { value: number; label: string };
};

export function MetricCard({ label, value, helper, icon, highlight = false, trend }: Props) {
  return (
    <Card className={highlight ? "border-brand/40 shadow-glow" : ""}>
      <CardContent className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="text-sm text-muted">{label}</p>
          <p className={`mt-2 text-3xl font-bold tracking-tight ${highlight ? "text-brand" : "text-text"}`}>
            {value}
          </p>
          <p className="mt-1 truncate text-xs text-muted">{helper}</p>
          {trend && (
            <p className={`mt-1 text-xs font-medium ${trend.value >= 0 ? "text-success" : "text-danger"}`}>
              {trend.value >= 0 ? "↑" : "↓"} {Math.abs(trend.value)}% {trend.label}
            </p>
          )}
        </div>
        <div
          className={`rounded-xl p-2.5 ${
            highlight ? "bg-brand/20 text-brand shadow-glow" : "bg-brand/10 text-brand"
          }`}
        >
          {icon}
        </div>
      </CardContent>
    </Card>
  );
}
