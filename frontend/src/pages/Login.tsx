import { FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { LogIn } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { getApiErrorMessage } from "@/lib/apiClient";
import { useLogin } from "@/hooks/useAuth";

export function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    await login.mutateAsync({ email, password });
    const target = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? "/";
    navigate(target, { replace: true });
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <h2 className="text-2xl font-bold text-text">Sign in</h2>
        <p className="mt-1 text-sm text-muted">Use your platform account to continue.</p>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <Input label="Email" name="email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          <Input label="Password" name="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          {login.isError ? <p className="rounded-md bg-danger/10 p-3 text-sm text-danger">{getApiErrorMessage(login.error, "Unable to sign in")}</p> : null}
          <Button className="w-full" type="submit" disabled={login.isPending}>
            <LogIn size={16} />
            {login.isPending ? "Signing in..." : "Sign in"}
          </Button>
        </form>
        <p className="mt-5 text-center text-sm text-muted">
          New here?{" "}
          <Link className="font-semibold text-brand hover:underline" to="/register">
            Create an account
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
