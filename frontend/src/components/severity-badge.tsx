import { Badge } from "@/components/ui";
import type { Severity } from "@/lib/types";

const MAP: Record<Severity, { label: string; cls: string }> = {
  normal: { label: "Normal", cls: "bg-ok-tint text-ok" },
  mild: { label: "Mild", cls: "bg-warn-tint text-warn" },
  moderate: { label: "Moderate", cls: "bg-elevated-tint text-elevated" },
  severe: { label: "Severe", cls: "bg-alert-tint text-alert" },
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  const m = MAP[severity] ?? MAP.normal;
  return (
    <Badge className={m.cls}>
      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-current" />
      {m.label}
    </Badge>
  );
}
