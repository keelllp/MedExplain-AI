"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, ArrowDown, ArrowUp, Download, MessageSquare, Trash2, TriangleAlert } from "lucide-react";

import { SeverityBadge } from "@/components/severity-badge";
import { Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Spinner } from "@/components/ui";
import * as api from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { Finding } from "@/lib/types";

const ERROR_LABELS: Record<string, string> = {
  ocr_failed: "We couldn't read text from this file.",
  extraction_failed: "We couldn't extract results from this report.",
  llm_unavailable: "The explanation service was unavailable.",
  timeout: "Analysis timed out.",
  internal_error: "Something went wrong during analysis.",
};

const STATUS_LABELS: Record<string, string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  analyzed: "Analyzed",
  failed: "Failed",
};

const MODE_LABELS: Record<string, string> = {
  offline_template: "Offline summary",
  ollama: "Local AI",
  gemini: "Cloud AI",
};

const MODE_BADGE: Record<string, string> = {
  offline_template: "bg-surface-sunken text-ink-muted",
  ollama: "bg-brand-tint text-brand",
  gemini: "bg-info-tint text-info",
};

function Center() {
  return (
    <div className="flex justify-center py-16">
      <Spinner className="h-6 w-6 text-ink-faint" />
    </div>
  );
}

export default function ReportPage() {
  const { user, loading } = useRequireAuth();
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const router = useRouter();
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["report", id],
    queryFn: () => api.getReport(id),
    enabled: !!user && Number.isFinite(id),
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      return status === "processing" || status === "uploaded" ? 2000 : false;
    },
  });

  const del = useMutation({
    mutationFn: () => api.deleteReport(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reports"] });
      router.push("/dashboard");
    },
  });
  const reanalyze = useMutation({
    mutationFn: () => api.analyzeReport(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["report", id] }),
  });
  const exportPdf = useMutation({
    mutationFn: () => api.exportReportPdf(id),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${query.data?.title ?? "report"}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },
  });

  if (loading || !user) return <Center />;
  if (!Number.isFinite(id)) return <Alert>Report not found.</Alert>;
  if (query.isLoading) return <Center />;
  if (query.isError || !query.data) return <Alert>Could not load this report.</Alert>;

  const report = query.data;
  const findingByBiomarker = new Map<number, Finding>(report.findings.map((f) => [f.biomarker_id, f]));
  const explained = report.findings.filter((f) => f.explanation);

  return (
    <div className="space-y-6">
      <div className="flex animate-rise flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1.5 text-sm text-ink-muted transition-colors hover:text-ink"
          >
            <ArrowLeft size={16} aria-hidden />
            Back
          </Link>
          <h1 className="font-display text-3xl font-semibold leading-tight text-ink sm:text-4xl">
            {report.title}
          </h1>
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink-muted">
            <span className="font-medium uppercase tracking-wide">{report.report_type.toUpperCase()}</span>
            <span aria-hidden className="text-ink-faint">·</span>
            <span>{STATUS_LABELS[report.status] ?? report.status}</span>
            {report.ocr_confidence != null && (
              <>
                <span aria-hidden className="text-ink-faint">·</span>
                <span>
                  OCR <span className="font-mono tabular">{Math.round(report.ocr_confidence * 100)}%</span>
                </span>
              </>
            )}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {report.status === "analyzed" && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push(`/chat?report_id=${id}`)}
            >
              <MessageSquare size={16} aria-hidden />
              Chat
            </Button>
          )}
          {report.status === "analyzed" && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => exportPdf.mutate()}
              disabled={exportPdf.isPending}
              title="Download a PDF summary"
            >
              {exportPdf.isPending ? <Spinner /> : <Download size={16} aria-hidden />}
              Export PDF
            </Button>
          )}
          <Button
            variant="danger"
            size="sm"
            onClick={() => {
              if (window.confirm("Delete this report and its file?")) del.mutate();
            }}
          >
            <Trash2 size={16} aria-hidden />
            Delete
          </Button>
        </div>
      </div>

      {(report.status === "processing" || report.status === "uploaded") && (
        <Alert variant="info">
          <span className="inline-flex items-center gap-2">
            <Spinner /> Analyzing… <span className="font-mono tabular">{report.progress}%</span>
          </span>
        </Alert>
      )}
      {report.status === "failed" && (
        <Alert>
          <span className="inline-flex items-center gap-2">
            <TriangleAlert size={16} className="shrink-0" aria-hidden />
            <span>
              {ERROR_LABELS[report.error_code ?? ""] ?? "Analysis failed."}{" "}
              <button
                onClick={() => reanalyze.mutate()}
                disabled={reanalyze.isPending}
                className="font-medium underline underline-offset-2"
              >
                Re-analyze
              </button>
            </span>
          </span>
        </Alert>
      )}

      {report.status === "analyzed" && (
        <>
          {report.summary && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <CardTitle>Summary</CardTitle>
                  <Badge className={MODE_BADGE[report.summary.generation_mode] ?? "bg-surface-sunken text-ink-muted"}>
                    {MODE_LABELS[report.summary.generation_mode] ?? report.summary.generation_mode}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <p className="max-w-prose whitespace-pre-wrap leading-relaxed text-ink">
                  {report.summary.summary_text}
                </p>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Biomarkers</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto p-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-surface-sunken text-left text-xs uppercase tracking-wide text-ink-muted">
                    <th className="px-5 py-2.5 font-semibold">Test</th>
                    <th className="px-5 py-2.5 font-semibold">Value</th>
                    <th className="px-5 py-2.5 font-semibold">Reference</th>
                    <th className="px-5 py-2.5 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {report.biomarkers.map((b) => {
                    const finding = findingByBiomarker.get(b.id);
                    return (
                      <tr key={b.id} className="border-b border-line transition-colors hover:bg-surface-sunken/60">
                        <td className="px-5 py-3 font-medium text-ink">{b.test_name}</td>
                        <td className="px-5 py-3">
                          {b.value != null ? (
                            <span className="font-mono tabular text-ink">
                              {b.value}
                              {b.unit ? <span className="text-ink-muted"> {b.unit}</span> : null}
                            </span>
                          ) : (
                            <span className="text-ink">{b.value_text ?? "—"}</span>
                          )}
                        </td>
                        <td className="px-5 py-3 font-mono tabular text-ink-muted">{b.reference_range_text ?? "—"}</td>
                        <td className="px-5 py-3">
                          {finding ? (
                            <span className="inline-flex items-center gap-1.5">
                              {finding.direction === "low" && (
                                <ArrowDown size={14} className="text-info" role="img" aria-label="Below reference range" />
                              )}
                              {finding.direction === "high" && (
                                <ArrowUp size={14} className="text-alert" role="img" aria-label="Above reference range" />
                              )}
                              <SeverityBadge severity={finding.severity} />
                            </span>
                          ) : (
                            <span className="text-ink-faint">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </CardContent>
          </Card>

          {explained.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Explanations</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {explained.map((f) => (
                  <div key={f.id} className="rounded-xl border border-line bg-surface-sunken/50 p-4">
                    <p className="whitespace-pre-wrap leading-relaxed text-ink">{f.explanation}</p>
                    {f.citations.length > 0 && (
                      <p className="mt-2 text-xs text-ink-muted">
                        Sources:{" "}
                        {f.citations
                          .map((c) => `${c.doc_title}${c.section ? ` › ${c.section}` : ""}`)
                          .join("; ")}
                      </p>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {report.doctor_questions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Questions for your doctor</CardTitle>
              </CardHeader>
              <CardContent>
                <ol className="list-decimal space-y-2 pl-5 text-sm leading-relaxed text-ink marker:font-semibold marker:text-brand">
                  {report.doctor_questions.map((q) => (
                    <li key={q.id} className="pl-1">
                      {q.question_text} <span className="text-xs text-ink-faint">({q.category})</span>
                    </li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
