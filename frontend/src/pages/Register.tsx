import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Bot, Eye, EyeOff, Lock, Mail, User } from "lucide-react";
import { useRegister } from "@/hooks/useAuth";
import { getApiErrorMessage } from "@/lib/apiClient";

export function Register() {
  const navigate = useNavigate();
  const register = useRegister();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    await register.mutateAsync({ email, password, full_name: fullName });
    navigate("/login");
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
          <p className="mt-1 text-sm text-muted">Create your workspace account</p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-border bg-panel p-8 shadow-card">
          <h2 className="mb-6 text-lg font-semibold text-text">New account</h2>

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-muted" htmlFor="reg-name">Full name</label>
              <div className="relative">
                <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                <input
                  id="reg-name"
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full rounded-lg border border-border bg-panel2 py-2.5 pl-9 pr-4 text-sm text-text placeholder:text-muted focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
                  placeholder="Jane Smith"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium text-muted" htmlFor="reg-email">Email</label>
              <div className="relative">
                <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                <input
                  id="reg-email"
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
              <label className="text-sm font-medium text-muted" htmlFor="reg-password">Password</label>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                <input
                  id="reg-password"
                  type={showPassword ? "text" : "password"}
                  required
                  minLength={8}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-lg border border-border bg-panel2 py-2.5 pl-9 pr-10 text-sm text-text placeholder:text-muted focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
                  placeholder="Min. 8 characters"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-text"
                  aria-label={showPassword ? "Hide" : "Show"}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Password strength bar */}
            <div className="space-y-1">
              <div className="flex gap-1">
                {[8, 12, 16].map((threshold) => (
                  <div
                    key={threshold}
                    className={`h-1 flex-1 rounded-full transition-all ${
                      password.length >= threshold ? "bg-brand2" : "bg-panel2"
                    }`}
                  />
                ))}
              </div>
              <p className="text-xs text-muted">
                {password.length === 0 ? "Enter a password" : password.length < 8 ? "Too short" : password.length < 12 ? "Fair" : "Strong"}
              </p>
            </div>

            {register.isError && (
              <div className="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
                {getApiErrorMessage(register.error, "Registration failed. Try again.")}
              </div>
            )}

            {register.isSuccess && (
              <div className="rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success">
                Account created! Redirecting to sign in…
              </div>
            )}

            <button
              type="submit"
              disabled={register.isPending}
              id="register-submit"
              className="w-full rounded-lg bg-gradient-to-r from-brand to-brand2 py-2.5 text-sm font-semibold text-white shadow-md transition hover:opacity-90 disabled:opacity-60"
            >
              {register.isPending ? "Creating account…" : "Create account"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-muted">
            Have an account?{" "}
            <Link to="/login" className="font-medium text-brand hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
