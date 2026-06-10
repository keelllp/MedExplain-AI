"use client";

import { useState } from "react";

import type { TrendPoint } from "@/lib/types";

// Hand-built SVG line chart (no chart lib): line + reference band + direction-colored
// markers + hover tooltip. Scales to its container via the viewBox. Data-only — the band
// is a neutral reference shade, never framed as "healthy" (no-reassurance rule).

const W = 720;
const H = 300;
const PAD = { top: 20, right: 20, bottom: 44, left: 52 };

const num = (v: number) => (Number.isInteger(v) ? String(v) : String(Math.round(v * 100) / 100));

function fmtDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "2-digit" });
}

function dotClass(p: TrendPoint): string {
  if (p.direction === "low") return "fill-info";
  if (p.direction === "high") return "fill-alert";
  return "fill-ink-muted";
}

export function TrendChart({ points, unit }: { points: TrendPoint[]; unit?: string | null }) {
  const [hover, setHover] = useState<number | null>(null);
  if (points.length === 0) return null;

  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  // Reference band from the most recent point that has bounds.
  const banded = [...points].reverse().find((p) => p.reference_low != null && p.reference_high != null);
  const low = banded?.reference_low ?? null;
  const high = banded?.reference_high ?? null;

  const values = points.map((p) => p.value);
  let yMin = Math.min(...values, low ?? Number.POSITIVE_INFINITY);
  let yMax = Math.max(...values, high ?? Number.NEGATIVE_INFINITY);
  if (!Number.isFinite(yMin)) yMin = Math.min(...values);
  if (!Number.isFinite(yMax)) yMax = Math.max(...values);
  if (yMin === yMax) {
    yMin -= 1;
    yMax += 1;
  }
  const padY = (yMax - yMin) * 0.12 || 1;
  yMin -= padY;
  yMax += padY;

  const x = (i: number) =>
    PAD.left + (points.length === 1 ? innerW / 2 : (innerW * i) / (points.length - 1));
  const y = (v: number) => PAD.top + innerH * (1 - (v - yMin) / (yMax - yMin));

  const line = points.map((p, i) => `${x(i)},${y(p.value)}`).join(" ");
  const yTicks = Array.from(
    new Set([yMin + padY, low, high, yMax - padY].filter((v): v is number => v != null)),
  );

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Biomarker values over time">
      {/* reference band (neutral, not "healthy") */}
      {low != null && high != null && (
        <>
          <rect
            x={PAD.left}
            y={y(high)}
            width={innerW}
            height={Math.max(0, y(low) - y(high))}
            className="fill-brand/5"
          />
          {[low, high].map((b) => (
            <line
              key={b}
              x1={PAD.left}
              x2={PAD.left + innerW}
              y1={y(b)}
              y2={y(b)}
              className="stroke-line-strong"
              strokeWidth={1}
              strokeDasharray="3 3"
            />
          ))}
          <text x={PAD.left + innerW} y={y(high) - 5} textAnchor="end" className="fill-ink-faint" fontSize={10}>
            reference range
          </text>
        </>
      )}

      {/* y-axis labels */}
      {yTicks.map((v) => (
        <text key={v} x={PAD.left - 8} y={y(v) + 4} textAnchor="end" className="fill-ink-faint tabular" fontSize={11}>
          {num(v)}
        </text>
      ))}

      {/* the line */}
      <polyline
        points={line}
        fill="none"
        className="stroke-brand"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* markers + x labels + hover hit-areas */}
      {points.map((p, i) => (
        <g key={`${p.report_id}-${i}`}>
          <circle cx={x(i)} cy={y(p.value)} r={hover === i ? 6 : 4.5} className={dotClass(p)} />
          <circle
            cx={x(i)}
            cy={y(p.value)}
            r={16}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover((h) => (h === i ? null : h))}
          />
          <text x={x(i)} y={H - PAD.bottom + 22} textAnchor="middle" className="fill-ink-faint" fontSize={11}>
            {fmtDate(p.point_time)}
          </text>
        </g>
      ))}

      {hover != null && <Tooltip p={points[hover]} px={x(hover)} py={y(points[hover].value)} unit={unit} />}
    </svg>
  );
}

function Tooltip({
  p,
  px,
  py,
  unit,
}: {
  p: TrendPoint;
  px: number;
  py: number;
  unit?: string | null;
}) {
  const status =
    p.direction === "low" ? "Below range" : p.direction === "high" ? "Above range" : "Within range";
  const u = unit ?? p.unit ?? p.canonical_unit ?? "";
  const lines = [fmtDate(p.point_time), `${num(p.value)} ${u}`.trim(), status];

  const w = 138;
  const h = 14 + lines.length * 15;
  let tx = px - w / 2;
  tx = Math.max(PAD.left, Math.min(tx, W - PAD.right - w));
  let ty = py - h - 12;
  if (ty < PAD.top) ty = py + 16;

  return (
    <g pointerEvents="none">
      <rect x={tx} y={ty} width={w} height={h} rx={8} className="fill-ink" opacity={0.93} />
      {lines.map((l, i) => (
        <text
          key={l}
          x={tx + 11}
          y={ty + 17 + i * 15}
          className="fill-paper"
          fontSize={i === 1 ? 12.5 : 11}
          fontWeight={i === 1 ? 600 : 400}
        >
          {l}
        </text>
      ))}
    </g>
  );
}
