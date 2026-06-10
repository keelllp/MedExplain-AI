"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Cloud, HardDrive, ShieldCheck, TriangleAlert } from "lucide-react";

import {
  Alert,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  Label,
  PageHeader,
  Spinner,
} from "@/components/ui";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";
import { useAuth, useRequireAuth } from "@/lib/auth";

export default function ProfilePage() {
  const { user, loading } = useRequireAuth();
  const { setUser, logout } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [msg, setMsg] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (user) setName(user.full_name ?? "");
  }, [user]);

  if (loading || !user) {
    return (
      <div className="flex justify-center py-16">
        <Spinner className="h-6 w-6 text-ink-faint" />
      </div>
    );
  }

  async function saveName() {
    setMsg(null);
    try {
      setUser(await api.updateProfile(name));
      setMsg({ kind: "success", text: "Profile updated." });
    } catch {
      setMsg({ kind: "error", text: "Could not update profile." });
    }
  }

  async function setMode(mode: string) {
    setMsg(null);
    if (
      mode === "cloud" &&
      !window.confirm(
        "Cloud (Gemini) mode sends your report text to Google to generate explanations. " +
          "On Google's free tier, your inputs may be used to improve their models and can be " +
          "reviewed by humans — don't use it with real patient data. Offline mode keeps " +
          "everything on your device. Continue with cloud mode?",
      )
    ) {
      return;
    }
    try {
      setUser(await api.updateSettings(mode));
      setMsg({ kind: "success", text: `Explanation engine set to ${mode}.` });
    } catch (err) {
      setMsg({
        kind: "error",
        text:
          err instanceof ApiError && err.status === 403
            ? "Cloud mode is not available on this server (no Gemini key configured)."
            : "Could not update settings.",
      });
    }
  }

  async function changePw() {
    setMsg(null);
    try {
      await api.changePassword(current, next);
      setCurrent("");
      setNext("");
      setMsg({ kind: "success", text: "Password updated." });
    } catch (err) {
      const text =
        err instanceof ApiError && err.status === 401
          ? "Current password is incorrect."
          : err instanceof ApiError && err.status === 422
            ? "New password must be at least 8 characters and differ from the current one."
            : "Could not change password.";
      setMsg({ kind: "error", text });
    }
  }

  async function deleteAccount() {
    if (!window.confirm("Permanently delete your account and all data?")) return;
    try {
      await api.deleteAccount();
      logout();
      router.push("/");
    } catch {
      setMsg({ kind: "error", text: "Could not delete account." });
    }
  }

  const isOffline = user.llm_mode !== "cloud";

  return (
    <div className="mx-auto max-w-2xl space-y-6 py-2">
      <PageHeader
        className="animate-rise"
        eyebrow="Your account"
        title="Profile & settings"
        description="Manage your details, choose how explanations are generated, and control your data."
      />

      {msg && <Alert variant={msg.kind}>{msg.text}</Alert>}

      <Card className="animate-rise [animation-delay:80ms]">
        <CardHeader>
          <CardTitle>Account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="profile-email">Email</Label>
            <Input id="profile-email" value={user.email} disabled />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="profile-name">Full name</Label>
            <Input id="profile-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <p className="text-xs text-ink-faint">Member since {user.created_at.slice(0, 10)}</p>
          <Button onClick={saveName}>Save changes</Button>
        </CardContent>
      </Card>

      <Card className="animate-rise [animation-delay:160ms]">
        <CardHeader>
          <CardTitle>Privacy &amp; LLM</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-ink-muted">
            Current explanation engine:{" "}
            <span className="font-medium text-ink">
              {user.llm_mode === "cloud" ? "Cloud (Gemini)" : "Offline (Ollama)"}
            </span>
          </p>

          <div className="grid gap-3 sm:grid-cols-2">
            <button
              type="button"
              onClick={() => setMode("offline")}
              aria-pressed={isOffline}
              className={
                "flex flex-col gap-2 rounded-xl border p-4 text-left transition " +
                (isOffline
                  ? "border-brand bg-brand-tint"
                  : "border-line bg-surface hover:border-line-strong")
              }
            >
              <span className="flex items-center gap-2">
                <HardDrive
                  size={18}
                  className={isOffline ? "text-brand" : "text-ink-muted"}
                  aria-hidden
                />
                <span className={"text-sm font-semibold " + (isOffline ? "text-brand" : "text-ink")}>
                  Offline (Ollama)
                </span>
              </span>
              <span className="text-xs text-ink-muted">
                Runs entirely on your device. Nothing leaves your machine.
              </span>
            </button>

            <button
              type="button"
              onClick={() => setMode("cloud")}
              aria-pressed={!isOffline}
              className={
                "flex flex-col gap-2 rounded-xl border p-4 text-left transition " +
                (!isOffline
                  ? "border-brand bg-brand-tint"
                  : "border-line bg-surface hover:border-line-strong")
              }
            >
              <span className="flex items-center gap-2">
                <Cloud
                  size={18}
                  className={!isOffline ? "text-brand" : "text-ink-muted"}
                  aria-hidden
                />
                <span className={"text-sm font-semibold " + (!isOffline ? "text-brand" : "text-ink")}>
                  Cloud (Gemini)
                </span>
              </span>
              <span className="text-xs text-ink-muted">
                Richer explanations via Google Gemini. Free tier may train on your inputs — not
                for real patient data.
              </span>
            </button>
          </div>

          <p className="flex items-start gap-2 text-xs text-warn">
            <TriangleAlert size={16} className="mt-0.5 shrink-0" aria-hidden />
            <span>
              Cloud mode sends your report text to Google Gemini. On the free tier, Google may use
              your inputs to improve its models and allow human review — keep real patient data on
              offline mode.
            </span>
          </p>

          {user.llm_mode === "cloud" && user.gemini_consented_at && (
            <p className="flex items-center gap-2 text-xs text-ink-faint">
              <ShieldCheck size={16} className="shrink-0 text-ink-faint" aria-hidden />
              Cloud egress consent recorded {user.gemini_consented_at.slice(0, 10)}.
            </p>
          )}
        </CardContent>
      </Card>

      <Card className="animate-rise [animation-delay:240ms]">
        <CardHeader>
          <CardTitle>Security</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="profile-current">Current password</Label>
              <Input
                id="profile-current"
                type="password"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="profile-next">New password</Label>
              <Input
                id="profile-next"
                type="password"
                value={next}
                onChange={(e) => setNext(e.target.value)}
              />
            </div>
          </div>
          <Button onClick={changePw}>Update password</Button>

          <div className="border-t border-line pt-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-alert">
              Danger zone
            </p>
            <Button variant="danger" onClick={deleteAccount}>
              Delete account &amp; all data
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
