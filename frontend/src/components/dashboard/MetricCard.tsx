import type { ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/Card";

export function MetricCard({ label, value, helper, icon }: { label: string; value: string | number; helper: string; icon: ReactNode }) {
  return (
    <Card>
      <CardContent className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted">{label}</p>
          <p className="mt-2 text-3xl font-bold tracking-normal text-text">{value}</p>
          <p className="mt-2 text-xs text-muted">{helper}</p>
        </div>
        <div className="rounded-md bg-brand/10 p-2 text-brand">{icon}</div>
      </CardContent>
    </Card>
  );
}
