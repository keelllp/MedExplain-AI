"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { UserPlus } from "lucide-react";

import { Alert, Button, Card, CardContent, Input, Label, Spinner } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function SignupPage() {
  const { user, register } = useAuth();
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [ack, setAck] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) router.replace("/dashboard");
  }, [user, router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) return setError("Password must be at least 8 characters.");
    if (password !== confirm) return setError("Passwords do not match.");
    if (!ack) return setError("Please acknowledge that this is an educational tool.");
    setBusy(true);
    try {
      await register(email, password, fullName || undefined);
      router.replace("/dashboard");
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 409
          ? "An account with this email already exists."
          : "Could not create your account. Please try again.",
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
              <UserPlus size={20} strokeWidth={2} aria-hidden />
            </span>
            <h1 className="mt-5 font-display text-3xl font-semibold leading-tight text-ink">
              Create your account
            </h1>
            <p className="mt-1.5 text-sm text-ink-muted">
              Start reading and understanding your reports.
            </p>
          </div>

          <form onSubmit={onSubmit} className="mt-8 space-y-4">
            <div className="space-y-1">
              <Label htmlFor="fullName">Full name (optional)</Label>
              <Input id="fullName" value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="password">Password (min 8 characters)</Label>
              <Input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="confirm">Confirm password</Label>
              <Input
                id="confirm"
                type="password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            </div>

            <label className="flex items-start gap-2.5 rounded-xl border border-line bg-surface-sunken px-3.5 py-3 text-sm text-ink-muted">
              <input
                type="checkbox"
                className="accent-brand size-4 mt-0.5"
                checked={ack}
                onChange={(e) => setAck(e.target.checked)}
              />
              <span>
                I understand MedExplain AI is an educational tool, not a doctor, and does not provide
                diagnosis or treatment. (Your data stays on your device in offline mode.)
              </span>
            </label>

            {error && <Alert>{error}</Alert>}
            <Button type="submit" disabled={busy} className="w-full">
              {busy && <Spinner />} Create account
            </Button>
            <p className="text-center text-sm text-ink-muted">
              Already have an account?{" "}
              <Link
                href="/login"
                className="font-medium text-brand underline underline-offset-4 hover:text-brand-strong"
              >
                Log in
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
