import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Bot, Eye, EyeOff, Lock, Mail, ShieldCheck } from "lucide-react";
import { useLogin } from "@/hooks/useAuth";
import { getApiErrorMessage } from "@/lib/apiClient";

export function Login() {
  const navigate = useNavigate();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    await login.mutateAsync({ email, password });
    navigate("/");
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-4">
      <div className="w-full max-w-md">
        {/* Brand */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand to-brand2 shadow-glow">
            <Bot size={28} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-text">Autonomous QA</h1>
          <p className="mt-1 text-sm text-muted">AI-powered test generation platform</p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-border bg-panel p-8 shadow-card">
          <h2 className="mb-6 text-lg font-semibold text-text">Sign in to your workspace</h2>

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-muted" htmlFor="login-email">Email</label>
              <div className="relative">
                <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                <input
                  id="login-email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-lg border border-border bg-panel2 py-2.5 pl-9 pr-4 text-sm text-text placeholder:text-muted focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
                  placeholder="you@example.com"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium text-muted" htmlFor="login-password">Password</label>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                <input
                  id="login-password"
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-lg border border-border bg-panel2 py-2.5 pl-9 pr-10 text-sm text-text placeholder:text-muted focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-text"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {login.isError && (
              <div className="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
                {getApiErrorMessage(login.error, "Invalid email or password.")}
              </div>
            )}

            <button
              type="submit"
              disabled={login.isPending}
              id="login-submit"
              className="w-full rounded-lg bg-gradient-to-r from-brand to-brand2 py-2.5 text-sm font-semibold text-white shadow-md transition hover:opacity-90 disabled:opacity-60"
            >
              {login.isPending ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-muted">
            No account?{" "}
            <Link to="/register" className="font-medium text-brand hover:underline">
              Create one
            </Link>
          </p>
        </div>

        <p className="mt-6 text-center text-xs text-muted">
          <ShieldCheck size={12} className="mr-1 inline" />
          JWT-secured · All traffic encrypted
        </p>
      </div>
    </div>
  );
}
