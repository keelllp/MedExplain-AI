"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, FileSearch, FileText, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Alert, Badge, Button, Card, CardContent, PageHeader, Spinner } from "@/components/ui";
import * as api from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

const STATUS_BADGE: Record<string, string> = {
  uploaded: "bg-surface-sunken text-ink-muted",
  processing: "bg-info-tint text-info",
  analyzed: "bg-ok-tint text-ok",
  failed: "bg-alert-tint text-alert",
};

function CenterSpinner() {
  return (
    <div className="flex justify-center py-16">
      <Spinner className="h-6 w-6 text-ink-faint" />
    </div>
  );
}

export default function DashboardPage() {
  const { user, loading } = useRequireAuth();
  const router = useRouter();

  const query = useQuery({
    queryKey: ["reports"],
    queryFn: () => api.listReports(50, 0),
    enabled: !!user,
    refetchInterval: (q) => {
      const data = q.state.data;
      const pending = data?.items.some((r) => r.status === "processing" || r.status === "uploaded");
      return pending ? 3000 : false;
    },
  });

  if (loading || !user) return <CenterSpinner />;

  return (
    <div className="space-y-6">
      <PageHeader
        className="animate-rise"
        eyebrow="Library"
        title="Your reports"
        description="Every report you’ve uploaded, with its analysis status."
        actions={
          <Link href="/upload">
            <Button>
              <Plus size={18} aria-hidden />
              Upload report
            </Button>
          </Link>
        }
      />

      {query.isLoading && <CenterSpinner />}
      {query.isError && <Alert>Could not load your reports.</Alert>}

      {query.data && query.data.items.length === 0 && (
        <Card className="animate-rise [animation-delay:80ms]">
          <CardContent className="space-y-5 py-14 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-brand-tint text-brand">
              <FileSearch size={24} aria-hidden />
            </div>
            <div className="space-y-1">
              <p className="font-display text-xl font-semibold text-ink">No reports yet</p>
              <p className="text-ink-muted">Upload your first medical report to get a plain-language explanation.</p>
            </div>
            <div className="flex justify-center">
              <Link href="/upload">
                <Button>
                  <Plus size={18} aria-hidden />
                  Upload report
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}

      {query.data && query.data.items.length > 0 && (
        <Card className="animate-rise [animation-delay:80ms]">
          <div className="divide-y divide-line">
            {query.data.items.map((r) => (
              <button
                key={r.id}
                onClick={() => router.push(`/reports/${r.id}`)}
                className="group flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-surface-sunken"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-surface-sunken text-ink-muted">
                  <FileText size={18} aria-hidden />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium text-ink">{r.title}</div>
                  <div className="mt-0.5 flex items-center gap-2 text-xs text-ink-faint">
                    <span className="font-medium uppercase tracking-wide text-ink-muted">
                      {r.report_type.toUpperCase()}
                    </span>
                    <span aria-hidden="true">·</span>
                    <span className="font-mono tabular">{r.uploaded_at.slice(0, 10)}</span>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2.5">
                  {r.status === "processing" && <Spinner className="text-info" />}
                  <Badge className={STATUS_BADGE[r.status] ?? "bg-surface-sunken text-ink-muted"}>
                    {r.status}
                  </Badge>
                  <ChevronRight
                    size={18}
                    aria-hidden
                    className="text-ink-faint transition-transform group-hover:translate-x-0.5"
                  />
                </div>
              </button>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
