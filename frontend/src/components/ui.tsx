import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  LabelHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from "react";

import { cn } from "@/lib/utils";

/* ----------------------------------------------------------------------------
   Button — pill-shaped, brand-forward, with a soft press interaction.
-------------------------------------------------------------------------- */
type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "outline" | "ghost" | "danger";
  size?: "md" | "sm";
};

export function Button({ className, variant = "primary", size = "md", ...props }: ButtonProps) {
  const variants: Record<string, string> = {
    primary:
      "bg-brand text-white shadow-sm shadow-brand/25 hover:bg-brand-strong",
    outline:
      "border border-line-strong bg-surface text-ink hover:border-brand hover:text-brand",
    ghost: "text-ink-muted hover:bg-surface-sunken hover:text-ink",
    danger: "bg-alert text-white shadow-sm shadow-alert/25 hover:brightness-[0.93]",
  };
  const sizes: Record<string, string> = {
    md: "h-11 px-5 text-sm",
    sm: "h-9 px-4 text-[13px]",
  };
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full font-medium tracking-tight",
        "transition-all duration-150 ease-out active:scale-[0.98]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40 focus-visible:ring-offset-2 focus-visible:ring-offset-paper",
        "disabled:pointer-events-none disabled:opacity-50",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  );
}

/* ----------------------------------------------------------------------------
   Card — soft, warm-shadowed surface on the paper canvas.
-------------------------------------------------------------------------- */
export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn("rounded-2xl border border-line bg-surface shadow-card", className)}>
      {children}
    </div>
  );
}

export function CardHeader({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("border-b border-line px-6 py-4", className)}>{children}</div>;
}

export function CardTitle({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <h2 className={cn("text-lg font-semibold tracking-tight text-ink", className)}>{children}</h2>
  );
}

export function CardContent({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("px-6 py-5", className)}>{children}</div>;
}

/* ----------------------------------------------------------------------------
   PageHeader — shared page title pattern. Serif display title + optional
   eyebrow / description, with an actions slot on the right.
-------------------------------------------------------------------------- */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  className,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
    >
      <div className="space-y-1.5">
        {eyebrow && (
          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-brand">
            {eyebrow}
          </div>
        )}
        <h1 className="font-display text-[1.75rem] font-semibold leading-tight text-ink sm:text-4xl">
          {title}
        </h1>
        {description && <p className="max-w-2xl text-ink-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ----------------------------------------------------------------------------
   Form fields — explicit ink text color so values are always readable
   (this is the bug the dark-mode media query used to cause).
-------------------------------------------------------------------------- */
export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-xl border border-line-strong bg-surface px-3.5 text-sm text-ink",
        "placeholder:text-ink-faint shadow-sm outline-none transition",
        "focus:border-brand focus:shadow-focus",
        "disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-muted",
        className,
      )}
      {...props}
    />
  );
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "field-select h-11 w-full appearance-none rounded-xl border border-line-strong bg-surface pl-3.5 pr-10 text-sm text-ink",
        "shadow-sm outline-none transition focus:border-brand focus:shadow-focus",
        "disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-muted",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}

export function Label({ className, children, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label className={cn("text-[13px] font-medium text-ink-muted", className)} {...props}>
      {children}
    </label>
  );
}

/* ----------------------------------------------------------------------------
   Badge / Spinner / Alert
-------------------------------------------------------------------------- */
export function Badge({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent",
        className,
      )}
      aria-label="loading"
    />
  );
}

type AlertProps = { className?: string; children: ReactNode; variant?: "error" | "info" | "success" };

export function Alert({ className, children, variant = "error" }: AlertProps) {
  const variants: Record<string, string> = {
    error: "bg-alert-tint text-alert border-alert/20",
    info: "bg-info-tint text-info border-info/20",
    success: "bg-ok-tint text-ok border-ok/25",
  };
  return (
    <div
      className={cn("rounded-xl border px-4 py-3 text-sm", variants[variant], className)}
      role="alert"
    >
      {children}
    </div>
  );
}
