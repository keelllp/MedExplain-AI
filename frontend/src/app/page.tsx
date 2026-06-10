import Link from "next/link";
import {
  Upload,
  FileSearch,
  Sparkles,
  TrendingUp,
  ShieldCheck,
  ArrowRight,
} from "lucide-react";

import { Button, Card, CardContent } from "@/components/ui";

const FEATURES = [
  {
    title: "Upload",
    body: "PDF, JPG, or PNG lab reports.",
    icon: Upload,
  },
  {
    title: "Auto-extract",
    body: "Biomarkers, values, units & abnormal flags.",
    icon: FileSearch,
  },
  {
    title: "Plain language",
    body: "Hedged explanations + questions for your doctor.",
    icon: Sparkles,
  },
  {
    title: "Trends",
    body: "Track your values over time.",
    icon: TrendingUp,
  },
];

export default function LandingPage() {
  return (
    <div className="space-y-8 py-10 sm:py-14">
      {/* ---------- Hero band ---------- */}
      <section className="grid items-center gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:gap-14">
        {/* Left: message */}
        <div className="max-w-xl space-y-6">
          <div className="animate-rise inline-flex items-center gap-2 rounded-full border border-brand/20 bg-brand-tint px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-brand">
            <span className="h-1.5 w-1.5 rounded-full bg-brand" />
            MedExplain AI
          </div>

          <h1 className="animate-rise font-display text-[2.5rem] font-semibold leading-[1.05] tracking-tight text-ink [animation-delay:80ms] sm:text-5xl lg:text-[3.5rem]">
            Understand your medical reports —{" "}
            <span className="text-brand">in plain English.</span>
          </h1>

          <p className="animate-rise max-w-md text-lg leading-relaxed text-ink-muted [animation-delay:160ms]">
            Educational explanations, never a diagnosis.
          </p>

          <div className="animate-rise flex flex-wrap items-center gap-3 [animation-delay:240ms]">
            <Link href="/signup">
              <Button>
                Get started
                <ArrowRight size={16} aria-hidden />
              </Button>
            </Link>
            <Link href="/login">
              <Button variant="outline">Log in</Button>
            </Link>
          </div>

          <div className="animate-rise flex items-center gap-2 rounded-full border border-line bg-surface px-3.5 py-2 text-sm text-ink-muted [animation-delay:320ms] sm:w-fit">
            <ShieldCheck size={16} aria-hidden className="shrink-0 text-brand" />
            <span>
              Local &amp; private. Offline (Ollama) mode keeps your data on your
              device.
            </span>
          </div>
        </div>

        {/* Right: decorative sample report card */}
        <div className="animate-rise [animation-delay:200ms]">
          <div className="relative mx-auto max-w-sm lg:mx-0 lg:ml-auto">
            {/* soft offset backdrop for depth */}
            <div
              aria-hidden
              className="absolute -inset-3 -z-10 rounded-[1.75rem] bg-brand-tint/50"
            />
            <Card className="shadow-lift">
              <div className="flex items-center justify-between border-b border-line px-6 py-4">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-faint">
                    Sample report
                  </div>
                  <div className="font-display text-lg font-semibold text-ink">
                    Lipid panel
                  </div>
                </div>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-ok-tint px-2.5 py-1 text-xs font-medium text-ok">
                  3 normal
                </span>
              </div>
              <CardContent className="space-y-3">
                <SampleRow
                  name="Total cholesterol"
                  value="182"
                  unit="mg/dL"
                  status="Normal"
                  tone="ok"
                />
                <SampleRow
                  name="HDL cholesterol"
                  value="58"
                  unit="mg/dL"
                  status="Normal"
                  tone="ok"
                />
                <SampleRow
                  name="LDL cholesterol"
                  value="121"
                  unit="mg/dL"
                  status="Mild"
                  tone="warn"
                />
                <SampleRow
                  name="Triglycerides"
                  value="96"
                  unit="mg/dL"
                  status="Normal"
                  tone="ok"
                />
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* ---------- How it works ---------- */}
      <section className="space-y-6 pt-4">
        <div className="flex flex-col gap-1.5">
          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-brand">
            How it works
          </div>
          <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
            From scan to plain English, in four steps.
          </h2>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((f, i) => {
            const Icon = f.icon;
            const delays = ["", "[animation-delay:80ms]", "[animation-delay:160ms]", "[animation-delay:240ms]"];
            return (
              <Card key={f.title} className={`animate-rise ${delays[i] ?? ""}`}>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex h-11 w-11 items-center justify-center rounded-full bg-brand-tint text-brand">
                      <Icon size={20} aria-hidden />
                    </div>
                    <span className="font-mono tabular text-sm font-medium text-ink-faint">
                      0{i + 1}
                    </span>
                  </div>
                  <div className="font-semibold text-ink">{f.title}</div>
                  <p className="text-sm leading-relaxed text-ink-muted">
                    {f.body}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>
    </div>
  );
}

/* ----------------------------------------------------------------------------
   SampleRow — decorative biomarker row for the hero's mock report card.
   Tokens only; not interactive, not real data.
-------------------------------------------------------------------------- */
function SampleRow({
  name,
  value,
  unit,
  status,
  tone,
}: {
  name: string;
  value: string;
  unit: string;
  status: string;
  tone: "ok" | "warn";
}) {
  const tones: Record<string, string> = {
    ok: "bg-ok-tint text-ok",
    warn: "bg-warn-tint text-warn",
  };
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-line bg-surface-sunken/60 px-3.5 py-2.5">
      <span className="truncate text-sm text-ink">{name}</span>
      <div className="flex shrink-0 items-center gap-3">
        <span className="font-mono tabular text-sm text-ink">
          {value}
          <span className="ml-1 text-xs text-ink-faint">{unit}</span>
        </span>
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}
        >
          {status}
        </span>
      </div>
    </div>
  );
}
