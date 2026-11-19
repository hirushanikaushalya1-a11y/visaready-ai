"use client";

import Link from "next/link";
import { Check, Clock, Minus } from "lucide-react";
import { money } from "@/lib/api";
import { useLoad } from "@/lib/auth";
import type { Country, Service } from "@/lib/types";
import { Badge, Card, Spinner } from "./ui";

export function Pricing() {
  const { data, error } = useLoad<Service[]>("/services");
  if (error) return <p className="text-sm text-ink-3">Pricing is temporarily unavailable. Please refresh in a moment.</p>;
  if (!data) return <Spinner label="Loading prices…" />;
  const core = data.find((s) => s.code === "assessment");
  const reassess = data.find((s) => s.code === "reassessment");
  const writing = data.filter((s) => s.kind === "writing");
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
      {core && (
        <Card className="relative lg:col-span-3 border-navy/20 p-7">
          <Badge tone="accent">Core package</Badge>
          <h3 className="mt-3 text-xl font-semibold text-ink">{core.name}</h3>
          <p className="mt-1 text-sm text-ink-3">{core.description}</p>
          <p className="mt-5 flex items-baseline gap-1"><span className="text-4xl font-semibold text-ink">{money(core.price_cents)}</span><span className="text-sm text-ink-3">per application · one-time</span></p>
          <ul className="mt-6 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {core.inclusions.map((i) => <li key={i} className="flex gap-2 text-sm text-ink-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-hidden />{i}</li>)}
          </ul>
          <div className="mt-6 rounded-lg bg-surface-2 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-3">Not included / limitations</p>
            <ul className="mt-2 space-y-1">
              {core.exclusions.map((i) => <li key={i} className="flex gap-2 text-sm text-ink-2"><Minus className="mt-0.5 h-4 w-4 shrink-0 text-ink-3" aria-hidden />{i}</li>)}
            </ul>
            {reassess && <p className="mt-3 text-xs text-ink-3">Further reassessments after the included ones: {money(reassess.price_cents)} each.</p>}
          </div>
          {core.disclaimer && <p className="mt-4 text-xs text-ink-3">{core.disclaimer}</p>}
          <Link href="/register" className="mt-6 inline-flex h-11 items-center rounded-lg bg-navy px-6 text-sm font-medium text-white hover:bg-navy-2">Start your assessment</Link>
        </Card>
      )}
      <Card className="lg:col-span-2 p-7">
        <h3 className="text-lg font-semibold text-ink">Document writing (optional)</h3>
        <p className="mt-1 flex items-center gap-1.5 text-sm text-ink-3"><Clock className="h-4 w-4" aria-hidden /> Delivered within 24 hours of complete submission — or the fee is refunded.</p>
        <ul className="mt-4 divide-y divide-line">
          {writing.map((s) => (
            <li key={s.code} className="flex items-center justify-between py-2.5 text-sm">
              <span className="text-ink-2">{s.name}</span><span className="font-medium tabular-nums text-ink">{money(s.price_cents)}</span>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-ink-3">Complex legal documents need a separate quotation. Affidavits are drafts only — never certified, notarised or legally approved.</p>
      </Card>
    </div>
  );
}

const STATUS_LABEL: Record<string, { label: string; tone: "ok" | "accent" | "neutral" }> = {
  live: { label: "Verified module", tone: "ok" },
  pilot: { label: "Requirements loaded · verification in progress", tone: "accent" },
  planned: { label: "Evidence checks available · requirements coming", tone: "neutral" },
};

export function Coverage() {
  const { data } = useLoad<Country[]>("/countries?kind=destination");
  const { data: future } = useLoad<Country[]>("/countries?kind=future");
  if (!data) return <Spinner />;
  return (
    <div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {data.map((c) => (
          <div key={c.code} className="flex min-w-0 flex-wrap items-center justify-between gap-x-3 gap-y-1.5 rounded-lg border border-line bg-surface px-4 py-3">
            <span className="font-medium text-ink">{c.name}</span>
            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${{ ok: "bg-ok-soft text-ok", accent: "bg-accent-soft text-accent", neutral: "bg-surface-2 text-ink-2" }[STATUS_LABEL[c.module_status].tone]}`}>
              {STATUS_LABEL[c.module_status].label}
            </span>
          </div>
        ))}
      </div>
      {future && future.length > 0 && (
        <p className="mt-5 text-sm text-ink-3">
          <span className="font-medium text-ink-2">Planned next:</span> {future.map((c) => c.name).join(" · ")}
        </p>
      )}
    </div>
  );
}
