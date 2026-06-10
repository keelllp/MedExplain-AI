"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Lock } from "lucide-react";

import { Alert, Button, Card, CardContent, Input, Label, Spinner } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { user, login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) router.replace("/dashboard");
  }, [user, router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      router.replace("/dashboard");
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 429
          ? "Too many attempts — please wait a moment and try again."
          : err instanceof ApiError && err.status === 401
            ? "Invalid email or password."
            : "Could not sign you in. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-14">
      <Card className="animate-rise">
        <CardContent className="px-7 py-8">
          <div className="flex flex-col items-center text-center">
            <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-tint text-brand">
              <Lock size={20} strokeWidth={2} aria-hidden />
            </span>
            <h1 className="mt-5 font-display text-3xl font-semibold leading-tight text-ink">
              Welcome back
            </h1>
            <p className="mt-1.5 text-sm text-ink-muted">
              Sign in to read and understand your reports.
            </p>
          </div>

          <form onSubmit={onSubmit} className="mt-8 space-y-4">
            <div className="space-y-1">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            {error && <Alert>{error}</Alert>}
            <Button type="submit" disabled={busy} className="w-full">
              {busy && <Spinner />} Log in
            </Button>
            <p className="text-center text-sm text-ink-muted">
              No account?{" "}
              <Link href="/signup" className="font-medium text-brand underline underline-offset-4 hover:text-brand-strong">
                Sign up
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
