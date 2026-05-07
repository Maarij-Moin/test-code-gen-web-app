import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { UserPlus } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { getApiErrorMessage } from "@/lib/apiClient";
import { useLogin, useRegister } from "@/hooks/useAuth";

export function Register() {
  const navigate = useNavigate();
  const register = useRegister();
  const login = useLogin();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    await register.mutateAsync({ full_name: fullName, email, password });
    await login.mutateAsync({ email, password });
    navigate("/", { replace: true });
  }

  const error = register.error ?? login.error;

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <h2 className="text-2xl font-bold text-text">Create account</h2>
        <p className="mt-1 text-sm text-muted">Set up access for your QA workspace.</p>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <Input label="Full name" name="full_name" autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} />
          <Input label="Email" name="email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          <Input label="Password" name="password" type="password" autoComplete="new-password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required />
          {error ? <p className="rounded-md bg-danger/10 p-3 text-sm text-danger">{getApiErrorMessage(error, "Unable to register")}</p> : null}
          <Button className="w-full" type="submit" disabled={register.isPending || login.isPending}>
            <UserPlus size={16} />
            {register.isPending || login.isPending ? "Creating..." : "Create account"}
          </Button>
        </form>
        <p className="mt-5 text-center text-sm text-muted">
          Already registered?{" "}
          <Link className="font-semibold text-brand hover:underline" to="/login">
            Sign in
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
