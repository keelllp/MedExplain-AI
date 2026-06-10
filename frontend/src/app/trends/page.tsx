"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { LineChart, Minus, TrendingDown, TrendingUp } from "lucide-react";

import { Dropdown } from "@/components/dropdown";
import { SeverityBadge } from "@/components/severity-badge";
import { TrendChart } from "@/components/trend-chart";
import { Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Spinner } from "@/components/ui";
import * as api from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { TrendLabel, TrendResponse } from "@/lib/types";

const TREND_BADGE: Record<TrendLabel, { label: string; cls: string; icon: typeof TrendingUp }> = {
  improving: { label: "Trending toward range", cls: "bg-info-tint text-info", icon: TrendingUp },
  worsening: { label: "Trending away from range", cls: "bg-alert-tint text-alert", icon: TrendingDown },
  stable: { label: "Stable", cls: "bg-surface-sunken text-ink-muted", icon: Minus },
  insufficient_data: { label: "Not enough data", cls: "bg-surface-sunken text-ink-muted", icon: Minus },
};

function Center() {
  return (
    <div className="flex justify-center py-16">
      <Spinner className="h-6 w-6 text-ink-faint" />
    </div>
  );
}

export default function TrendsPage() {
  const { user, loading } = useRequireAuth();
  const [selected, setSelected] = useState<string | null>(null);

  const trendable = useQuery({
    queryKey: ["trendable"],
    queryFn: api.listTrendableBiomarkers,
    enabled: !!user,
  });

  // Default to the most-recently-updated trendable series once the list loads.
  useEffect(() => {
    if (selected == null && trendable.data && trendable.data.length > 0) {
      setSelected(trendable.data[0].canonical_name);
    }
  }, [selected, trendable.data]);

  const trend = useQuery({
    queryKey: ["trend", selected],
    queryFn: () => api.getTrend(selected!),
    enabled: !!user && selected != null,
  });

  if (loading || !user) return <Center />;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="font-display text-3xl font-semibold leading-tight text-ink sm:text-4xl">
          Trends over time
        </h1>
        <p className="max-w-2xl text-ink-muted">
          Track one marker across your reports. This shows your own values against the reference
          range — it&apos;s a descriptive view of your data, not a diagnosis.
        </p>
      </div>

      {trendable.isLoading ? (
        <Center />
      ) : trendable.isError ? (
        <Alert>
          Couldn&apos;t load your trends.{" "}
          <button onClick={() => trendable.refetch()} className="font-medium underline underline-offset-2">
            Retry
          </button>
        </Alert>
      ) : !trendable.data || trendable.data.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          <div className="max-w-xs space-y-1.5">
            <label htmlFor="biomarker" className="text-[13px] font-medium text-ink-muted">
              Biomarker
            </label>
            <Dropdown
              id="biomarker"
              value={selected}
              onChange={setSelected}
              options={trendable.data.map((b) => ({
                value: b.canonical_name,
                label: `${b.display} (${b.count})`,
              }))}
            />
          </div>

          {trend.isLoading || !trend.data ? (
            <Card>
              <CardContent className="py-20">
                <Center />
              </CardContent>
            </Card>
          ) : trend.isError ? (
            <Alert>
              Couldn&apos;t load that series.{" "}
              <button onClick={() => trend.refetch()} className="font-medium underline underline-offset-2">
                Retry
              </button>
            </Alert>
          ) : (
            <TrendCard data={trend.data} />
          )}
        </>
      )}
    </div>
  );
}

function TrendCard({ data }: { data: TrendResponse }) {
  const badge = TREND_BADGE[data.trend];
  const TrendIcon = badge.icon;
  const last = data.points[data.points.length - 1];
  const unit = last?.unit ?? last?.canonical_unit ?? null;
  const latestAbnormal = last?.severity && last.severity !== "normal";

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle>
            {data.display}
            {unit ? <span className="ml-2 text-sm font-normal text-ink-muted">{unit}</span> : null}
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge className={badge.cls}>
              <TrendIcon size={13} aria-hidden />
              {badge.label}
            </Badge>
            {last &&
              (latestAbnormal ? (
                <SeverityBadge severity={last.severity!} />
              ) : (
                <Badge className="bg-surface-sunken text-ink-muted">Latest within range</Badge>
              ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <TrendChart points={data.points} unit={unit} />

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-ink-muted">
          <LegendDot className="fill-info" label="Below range" />
          <LegendDot className="fill-alert" label="Above range" />
          <LegendDot className="fill-ink-muted" label="Within range" />
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-4 rounded-sm bg-brand/10 ring-1 ring-line-strong" aria-hidden />
            Reference range
          </span>
        </div>

        <p className="border-t border-line pt-3 text-xs leading-relaxed text-ink-faint">
          {data.disclaimer}
        </p>
      </CardContent>
    </Card>
  );
}

function LegendDot({ className, label }: { className: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <svg viewBox="0 0 10 10" className="h-2.5 w-2.5" aria-hidden>
        <circle cx="5" cy="5" r="5" className={className} />
      </svg>
      {label}
    </span>
  );
}

function EmptyState() {
  return (
    <Card className="animate-rise">
      <CardContent className="flex flex-col items-center px-6 py-16 text-center">
        <span className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-brand-tint text-brand">
          <LineChart size={28} strokeWidth={1.75} aria-hidden />
        </span>
        <h2 className="mt-6 font-display text-2xl font-semibold tracking-tight text-ink">
          No trends yet
        </h2>
        <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-ink-muted">
          A trend needs the same test measured at least twice. Upload two or more reports that
          include the same marker (e.g. hemoglobin) and it&apos;ll chart here.
        </p>
        <Link href="/upload" className="mt-6">
          <Button>Upload a report</Button>
        </Link>
      </CardContent>
    </Card>
  );
}
