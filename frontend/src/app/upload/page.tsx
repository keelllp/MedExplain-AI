"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { FileText, ShieldCheck, Upload } from "lucide-react";

import { Alert, Button, Card, CardContent, CardHeader, CardTitle, Input, Label, Select, Spinner } from "@/components/ui";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

const TYPES = ["blood", "cbc", "mri", "ct", "xray", "pathology", "prescription", "discharge", "other"];

export default function UploadPage() {
  const { user, loading } = useRequireAuth();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [type, setType] = useState("other");
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<"idle" | "uploading" | "analyzing">("idle");
  const [status, setStatus] = useState("");
  const [progress, setProgress] = useState(0);
  const cancelled = useRef(false);
  useEffect(() => {
    // Reset on mount so React Strict Mode's dev-only mount→cleanup→mount cycle (which fires
    // the cleanup once before the real mount) doesn't leave this latched true and abort the
    // poll loop on its first iteration. Cleanup still aborts polling on a real unmount.
    cancelled.current = false;
    return () => {
      cancelled.current = true;
    };
  }, []);

  if (loading || !user) {
    return (
      <div className="flex justify-center py-16">
        <Spinner className="h-6 w-6 text-ink-faint" />
      </div>
    );
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!file) return setError("Please choose a file.");
    if (file.size > 20 * 1024 * 1024) return setError("File exceeds the 20 MB limit.");
    if (file.type && !["application/pdf", "image/jpeg", "image/png"].includes(file.type)) {
      return setError("Unsupported file type. Use a PDF, JPG, or PNG.");
    }
    setPhase("uploading");
    try {
      const form = new FormData();
      form.append("file", file);
      if (title) form.append("title", title);
      form.append("report_type", type);
      const uploaded = await api.uploadReport(form);

      setPhase("analyzing");
      setStatus("processing");
      await api.analyzeReport(uploaded.report_id);

      // Poll until analysis finishes (bounded; stops if the user navigates away).
      for (let attempt = 0; attempt < 160; attempt++) {
        if (cancelled.current) return;
        const detail = await api.getReport(uploaded.report_id);
        setStatus(detail.status);
        setProgress(detail.progress);
        if (detail.status === "analyzed") {
          router.push(`/reports/${uploaded.report_id}`);
          return;
        }
        if (detail.status === "failed") {
          setError("Analysis failed. Please try another file.");
          setPhase("idle");
          return;
        }
        await new Promise((res) => setTimeout(res, 1500));
      }
      // Took longer than expected — open the report; it keeps polling there.
      router.push(`/reports/${uploaded.report_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
      setPhase("idle");
    }
  }

  return (
    <div className="mx-auto max-w-xl py-6">
      <Card className="animate-rise">
        <CardHeader>
          <CardTitle className="font-display text-2xl">Upload a medical report</CardTitle>
          <p className="mt-1.5 text-sm text-ink-muted">
            Add a lab result, scan, or summary and we&rsquo;ll explain it in plain language.
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-5">
            <label className="group block cursor-pointer rounded-2xl border-2 border-dashed border-line-strong bg-surface-sunken/40 p-8 text-center transition-colors hover:border-brand">
              <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-brand-tint text-brand">
                <Upload size={22} strokeWidth={2} aria-hidden />
              </span>
              <span className="mt-4 block text-sm font-medium text-ink">
                Drop a file here, or click to browse
              </span>
              <span className="mt-1 block text-xs text-ink-faint">
                PDF, JPG, or PNG &middot; max 20 MB &middot; one report
              </span>
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="sr-only"
              />
              {file && (
                <span className="mx-auto mt-4 inline-flex max-w-full items-center gap-2 rounded-full border border-line bg-surface px-3.5 py-1.5 text-sm text-ink shadow-sm">
                  <FileText size={16} className="shrink-0 text-brand" aria-hidden />
                  <span className="truncate">{file.name}</span>
                  <span className="shrink-0 font-mono tabular text-xs text-ink-muted">
                    {Math.round(file.size / 1024)} KB
                  </span>
                </span>
              )}
            </label>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="title">Title</Label>
                <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. CBC – Apr 2026" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="type">Type</Label>
                <Select id="type" value={type} onChange={(e) => setType(e.target.value)} className="w-full">
                  {TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            {error && <Alert>{error}</Alert>}
            {phase === "analyzing" && (
              <Alert variant="info">
                <span className="flex items-center gap-2">
                  <Spinner /> Analyzing… {progress}% ({status}) — OCR → extract → rules → explanations
                </span>
                <span className="mt-2.5 block h-1.5 w-full overflow-hidden rounded-full bg-surface-sunken">
                  <span
                    className="block h-full rounded-full bg-brand transition-all duration-500 ease-out"
                    style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
                  />
                </span>
              </Alert>
            )}
            <Button type="submit" disabled={phase !== "idle"} className="w-full">
              {phase !== "idle" && <Spinner />}{" "}
              {phase === "uploading" ? "Uploading…" : phase === "analyzing" ? "Analyzing…" : "Upload & analyze"}
            </Button>
          </form>
        </CardContent>
      </Card>
      <p className="mt-4 flex items-center justify-center gap-1.5 text-xs text-ink-faint">
        <ShieldCheck size={14} className="text-brand" aria-hidden />
        Your report is private and processed securely.
      </p>
    </div>
  );
}
