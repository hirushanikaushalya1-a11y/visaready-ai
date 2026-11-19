"use client";

import Link from "next/link";
import { forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { AlertTriangle, CheckCircle2, Info, Loader2, XCircle } from "lucide-react";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

type Variant = "primary" | "secondary" | "ghost" | "danger" | "accent";
const variants: Record<Variant, string> = {
  primary: "bg-navy text-white hover:bg-navy-2 shadow-sm",
  accent: "bg-accent text-white hover:opacity-90 shadow-sm",
  secondary: "bg-surface text-ink border border-line hover:bg-surface-2",
  ghost: "text-ink-2 hover:bg-surface-2",
  danger: "bg-bad text-white hover:opacity-90",
};

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean; size?: "sm" | "md" | "lg" }>(
  function Button({ variant = "primary", loading, size = "md", className, children, disabled, ...rest }, ref) {
    const sizes = { sm: "h-8 px-3 text-sm", md: "h-10 px-4 text-sm", lg: "h-12 px-6 text-base" };
    return (
      <button ref={ref} disabled={disabled || loading}
        className={cx("inline-flex items-center justify-center gap-2 rounded-lg font-medium transition disabled:opacity-50 disabled:cursor-not-allowed", sizes[size], variants[variant], className)} {...rest}>
        {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
        {children}
      </button>
    );
  },
);

export function ButtonLink({ href, variant = "primary", size = "md", className, children }: { href: string; variant?: Variant; size?: "sm" | "md" | "lg"; className?: string; children: ReactNode }) {
  const sizes = { sm: "h-8 px-3 text-sm", md: "h-10 px-4 text-sm", lg: "h-12 px-6 text-base" };
  return (
    <Link href={href} className={cx("inline-flex items-center justify-center gap-2 rounded-lg font-medium transition", sizes[size], variants[variant], className)}>
      {children}
    </Link>
  );
}

export function Card({ className, children, ...rest }: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cx("rounded-xl border border-line bg-surface p-5 shadow-[0_1px_2px_rgba(14,26,51,0.04)]", className)} {...rest}>{children}</div>;
}

export function SectionTitle({ title, subtitle, action }: { title: string; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold text-ink">{title}</h2>
        {subtitle && <p className="mt-0.5 text-sm text-ink-3">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

type Tone = "neutral" | "ok" | "warn" | "bad" | "info" | "accent";
const tones: Record<Tone, string> = {
  neutral: "bg-surface-2 text-ink-2", ok: "bg-ok-soft text-ok", warn: "bg-warn-soft text-warn", bad: "bg-bad-soft text-bad",
  info: "bg-info-soft text-info", accent: "bg-accent-soft text-accent",
};
export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={cx("inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap", tones[tone], className)}>{children}</span>;
}

export const severityTone: Record<string, Tone> = { high: "bad", medium: "warn", low: "info", info: "neutral" };
export const statusTone: Record<string, Tone> = {
  satisfied: "ok", supported: "ok", completed: "ok", delivered: "ok", succeeded: "ok", active: "ok", processed: "ok", refunded: "info",
  partially_supported: "warn", uploaded_unconfirmed: "warn", requires_clarification: "warn", awaiting_documents: "warn", information_incomplete: "warn",
  missing: "bad", unsupported: "bad", conflicting: "bad", failed: "bad", refund_eligible: "bad",
  human_review_recommended: "info", processing: "info", quality_review: "info", submission_complete: "info", queued: "neutral", running: "info",
  draft: "neutral", pending: "neutral", payment_pending: "neutral",
};

export function Field({ label, hint, error, children, htmlFor }: { label: string; hint?: ReactNode; error?: string; children: ReactNode; htmlFor?: string }) {
  // With an explicit id the label points at it; otherwise the label wraps the control so the
  // association is implicit — every form control always has an accessible name.
  return (
    <div className="space-y-1.5">
      {htmlFor ? (
        <>
          <label htmlFor={htmlFor} className="block text-sm font-medium text-ink">{label}</label>
          {children}
        </>
      ) : (
        <label className="block space-y-1.5">
          <span className="block text-sm font-medium text-ink">{label}</span>
          {children}
        </label>
      )}
      {hint && !error && <p className="text-xs text-ink-3">{hint}</p>}
      {error && <p className="text-xs text-bad">{error}</p>}
    </div>
  );
}

const inputCls = "w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20";
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...rest }, ref) {
  return <input ref={ref} className={cx(inputCls, "h-10", className)} {...rest} />;
});
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, children, ...rest }, ref) {
  return <select ref={ref} className={cx(inputCls, "h-10", className)} {...rest}>{children}</select>;
});
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...rest }, ref) {
  return <textarea ref={ref} className={cx(inputCls, "min-h-24", className)} {...rest} />;
});

export function Alert({ tone = "info", title, children }: { tone?: "info" | "ok" | "warn" | "bad"; title?: string; children?: ReactNode }) {
  const Icon = { info: Info, ok: CheckCircle2, warn: AlertTriangle, bad: XCircle }[tone];
  return (
    <div role={tone === "bad" ? "alert" : "status"} className={cx("flex gap-3 rounded-lg px-4 py-3 text-sm", tones[tone])}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="space-y-1">{title && <p className="font-semibold">{title}</p>}{children && <div className="text-ink-2">{children}</div>}</div>
    </div>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return <div className="flex items-center gap-2 py-10 text-sm text-ink-3 justify-center"><Loader2 className="h-4 w-4 animate-spin" aria-hidden />{label}</div>;
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-line bg-surface px-6 py-10 text-center">
      <p className="font-medium text-ink">{title}</p>
      {children && <div className="mx-auto mt-1 max-w-md text-sm text-ink-3">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Progress({ value, tone = "accent" }: { value: number; tone?: "accent" | "ok" | "warn" | "bad" }) {
  const col = { accent: "bg-accent", ok: "bg-ok", warn: "bg-warn", bad: "bg-bad" }[tone];
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}>
      <div className={cx("h-full rounded-full transition-all", col)} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

export function ScoreRing({ score, size = 132 }: { score: number | null; size?: number }) {
  const r = 52, c = 2 * Math.PI * r;
  const v = score ?? 0;
  const col = v >= 75 ? "var(--ok)" : v >= 50 ? "var(--warn)" : "var(--bad)";
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg viewBox="0 0 120 120" width={size} height={size} aria-hidden>
        <circle cx="60" cy="60" r={r} fill="none" stroke="var(--surface-2)" strokeWidth="10" />
        {score != null && <circle cx="60" cy="60" r={r} fill="none" stroke={col} strokeWidth="10" strokeLinecap="round"
          strokeDasharray={`${(v / 100) * c} ${c}`} transform="rotate(-90 60 60)" />}
      </svg>
      <div className="absolute text-center">
        <div className="text-3xl font-semibold tabular-nums text-ink">{score ?? "—"}</div>
        <div className="text-[11px] uppercase tracking-wide text-ink-3">readiness</div>
      </div>
    </div>
  );
}

export function Tabs({ tabs, active, onChange }: { tabs: { id: string; label: string; count?: number }[]; active: string; onChange: (id: string) => void }) {
  return (
    <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <div role="tablist" className="flex min-w-max gap-1 border-b border-line">
        {tabs.map((t) => (
          <button key={t.id} role="tab" aria-selected={active === t.id} onClick={() => onChange(t.id)}
            className={cx("relative -mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition",
              active === t.id ? "border-accent text-ink" : "border-transparent text-ink-3 hover:text-ink")}>
            {t.label}
            {t.count != null && t.count > 0 && <span className="ml-1.5 rounded-full bg-surface-2 px-1.5 text-xs text-ink-2">{t.count}</span>}
          </button>
        ))}
      </div>
    </div>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-ink-3">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-ink">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-ink-3">{hint}</p>}
    </div>
  );
}
