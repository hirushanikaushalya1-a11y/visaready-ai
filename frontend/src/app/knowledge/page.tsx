"use client";

import { useState } from "react";
import { ExternalLink, Search } from "lucide-react";
import { api, fmtDate } from "@/lib/api";
import { useLoad } from "@/lib/auth";
import type { Country } from "@/lib/types";
import { SiteFooter, SiteHeader } from "@/components/shell";
import { Alert, Badge, Button, Card, Input, Select } from "@/components/ui";

type Result = { id: string; title: string; description: string; level: string; source_url: string; review_status: string; last_verified_at: string | null;
  country_name: string; visa_category: string; financial_requirement: { notes?: string } | null; exceptions: string | null };

export default function Knowledge() {
  const { data: countries } = useLoad<Country[]>("/countries?kind=destination");
  const [q, setQ] = useState("");
  const [country, setCountry] = useState("");
  const [res, setRes] = useState<{ results: Result[]; message: string | null } | null>(null);
  const [busy, setBusy] = useState(false);
  async function search(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try { setRes(await api(`/knowledge/search?q=${encodeURIComponent(q)}${country ? `&country=${country}` : ""}`)); }
    catch (err) { setRes({ results: [], message: err instanceof Error ? err.message : "Search failed" }); }
    finally { setBusy(false); }
  }
  return (
    <>
      <SiteHeader />
      <main className="mx-auto max-w-4xl px-4 py-12">
        <h1 className="text-3xl font-semibold tracking-tight text-ink">Global Visa Knowledge Centre</h1>
        <p className="mt-2 text-ink-2">Answers come only from requirements recorded from official government sources. Every answer shows its source and verification status. If we don&apos;t have reliable information, we say so.</p>
        <form onSubmit={search} className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-[1fr_200px_auto]">
          <Input placeholder="e.g. English requirement student, financial proof, TB test" value={q} onChange={(e) => setQ(e.target.value)} minLength={2} required aria-label="Question" />
          <Select value={country} onChange={(e) => setCountry(e.target.value)} aria-label="Country"><option value="">All countries</option>{countries?.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}</Select>
          <Button type="submit" loading={busy}><Search className="h-4 w-4" aria-hidden /> Search</Button>
        </form>
        <div className="mt-8 space-y-4">
          {res?.message && <Alert tone="warn">{res.message}</Alert>}
          {res?.results.map((r) => (
            <Card key={r.id}>
              <div className="flex flex-wrap items-center gap-2"><Badge tone="accent">{r.country_name}</Badge><Badge tone="neutral">{r.visa_category}</Badge><Badge tone={r.level === "mandatory" ? "info" : "neutral"}>{r.level}</Badge></div>
              <h2 className="mt-2 font-semibold text-ink">{r.title}</h2>
              <p className="mt-1 text-sm text-ink-2">{r.description}</p>
              {r.financial_requirement?.notes && <p className="mt-1 text-xs text-ink-3">Financial: {r.financial_requirement.notes}</p>}
              {r.exceptions && <p className="mt-1 text-xs text-ink-3">Exceptions: {r.exceptions}</p>}
              <p className="mt-3 flex flex-wrap items-center gap-3 text-xs">
                <a href={r.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent">Official source <ExternalLink className="h-3 w-3" aria-hidden /></a>
                {r.review_status === "verified" ? <span className="text-ok">Verified {fmtDate(r.last_verified_at)}</span> : <span className="text-warn">Recorded from the official source — not yet re-verified by our team</span>}
              </p>
            </Card>
          ))}
        </div>
        <p className="mt-10 text-xs text-ink-3">This is general information, not legal advice. Immigration rules change; always confirm with the official source before applying.</p>
      </main>
      <SiteFooter />
    </>
  );
}
