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
  const free = data.find((s) => s.code === "free_assessment");
  const report = data.find((s) => s.code === "assessment_report");
  const services = data.filter((s) => s.kind === "writing");
  const perLetter = (code: string) => code.includes("letter") || code === "affidavit_draft";
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {free && (
          <Card className="p-7">
            <Badge tone="ok">Start here</Badge>
            <h3 className="mt-3 text-xl font-semibold text-ink">{free.name}</h3>
            <p className="mt-1 text-sm text-ink-3">{free.description}</p>
            <p className="mt-5 text-4xl font-semibold text-ok">Free</p>
            <ul className="mt-6 space-y-2">
              {free.inclusions.map((i) => <li key={i} className="flex gap-2 text-sm text-ink-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-hidden />{i}</li>)}
            </ul>
            <Link href="/register" className="mt-6 inline-flex h-11 items-center rounded-lg bg-navy px-6 text-sm font-medium text-white hover:bg-navy-2">Check my file for free</Link>
            {free.disclaimer && <p className="mt-4 text-xs text-ink-3">{free.disclaimer}</p>}
          </Card>
        )}
        {report && (
          <Card className="border-navy/30 p-7">
            <Badge tone="accent">Most useful</Badge>
            <h3 className="mt-3 text-xl font-semibold text-ink">{report.name}</h3>
            <p className="mt-1 text-sm text-ink-3">{report.description}</p>
            <p className="mt-5 flex items-baseline gap-1"><span className="text-4xl font-semibold text-ink">{money(report.price_cents, report.currency)}</span><span className="text-sm text-ink-3">per application · one-time</span></p>
            <ul className="mt-6 space-y-2">
              {report.inclusions.map((i) => <li key={i} className="flex gap-2 text-sm text-ink-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-hidden />{i}</li>)}
            </ul>
            {report.exclusions.map((i) => <p key={i} className="mt-4 flex gap-2 text-xs text-ink-3"><Minus className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />{i}</p>)}
          </Card>
        )}
      </div>
      <Card className="p-7">
        <h3 className="text-lg font-semibold text-ink">We write it for you</h3>
        <p className="mt-1 flex items-center gap-1.5 text-sm text-ink-3"><Clock className="h-4 w-4" aria-hidden /> Emailed to you within 24 hours of complete submission — or the fee is refunded.</p>
        <ul className="mt-4 grid grid-cols-1 gap-x-8 md:grid-cols-2">
          {services.map((s) => (
            <li key={s.code} className="flex items-center justify-between gap-3 border-b border-line py-2.5 text-sm">
              <span className="text-ink-2">{s.name}{s.restricted_countries.length > 0 && <span className="block text-xs text-ink-3">Not available for {s.restricted_countries.join(", ")}</span>}</span>
              <span className="shrink-0 font-medium tabular-nums text-ink">{money(s.price_cents, s.currency)}{perLetter(s.code) && <span className="text-xs font-normal text-ink-3"> /letter</span>}</span>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-ink-3">Affidavits are drafts only — never certified, notarised or legally approved. Complex legal documents need a separate quotation.</p>
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
