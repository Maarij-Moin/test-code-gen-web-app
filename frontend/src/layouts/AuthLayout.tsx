import { Outlet } from "react-router-dom";
import { ShieldCheck } from "lucide-react";

export function AuthLayout() {
  return (
    <main className="grid min-h-screen bg-surface lg:grid-cols-[0.95fr_1.05fr]">
      <section className="hidden border-r border-border bg-panel px-10 py-12 lg:flex lg:flex-col lg:justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-md bg-brand p-2 text-white">
            <ShieldCheck size={22} />
          </div>
          <span className="text-lg font-bold text-text">Autonomous QA</span>
        </div>
        <div>
          <h1 className="max-w-xl text-5xl font-bold tracking-normal text-text">AI testing operations, controlled from one console.</h1>
          <p className="mt-6 max-w-lg text-base leading-7 text-muted">
            Connect repositories, monitor autonomous jobs, inspect generated diffs, and keep pull requests moving with validation evidence.
          </p>
        </div>
        <p className="text-sm text-muted">Production dashboard for automated test generation.</p>
      </section>
      <section className="flex min-h-screen items-center justify-center px-5 py-10">
        <Outlet />
      </section>
    </main>
  );
}
