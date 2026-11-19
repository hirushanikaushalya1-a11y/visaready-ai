"use client";

import { useState } from "react";
import { Check, Clock, ShieldAlert } from "lucide-react";
import { money, post } from "@/lib/api";
import { useLoad } from "@/lib/auth";
import { startCheckout } from "@/lib/checkout";
import type { Application, Service, WritingOrder } from "@/lib/types";
import { PageHeader } from "@/components/shell";
import { Alert, Button, Card, Field, Input, Select, Spinner, Textarea } from "@/components/ui";

const LETTER_CODES = ["cover_letter", "consent_letter", "explanation_letter", "study_gap_letter", "financial_explanation_letter",
  "sponsorship_letter", "employment_explanation_letter", "affidavit_draft", "other_letter"];

export default function ServicesPage() {
  const { data } = useLoad<Service[]>("/services");
  const { data: apps } = useLoad<Application[]>("/applications");
  const [sel, setSel] = useState<Service | null>(null);
  const [notes, setNotes] = useState("");
  const [appId, setAppId] = useState("");
  const [qty, setQty] = useState(1);
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!data) return <Spinner />;
  const writing = data.filter((s) => s.kind === "writing");
  const isLetter = (s: Service) => LETTER_CODES.includes(s.code);
  const groups: [string, Service[]][] = [
    ["Statement of purpose & portfolios", writing.filter((s) => ["sop", "relationship_portfolio"].includes(s.code))],
    ["Letters — priced per letter", writing.filter(isLetter)],
    ["Application services", writing.filter((s) => s.restricted_countries.length > 0)],
  ];
  const restricted = sel?.restricted_countries ?? [];
  const selApp = apps?.find((a) => a.id === appId);
  const blocked = !!selApp && restricted.includes(selApp.country_code);
  const needsApp = restricted.length > 0;
  const total = sel?.price_cents != null ? sel.price_cents * (sel && isLetter(sel) ? qty : 1) : null;

  async function order() {
    setBusy(true);
    setError(null);
    try {
      const o = await post<WritingOrder>("/writing-orders", { service_code: sel!.code, notes: notes || null, application_id: appId || null, quantity: isLetter(sel!) ? qty : 1 });
      await startCheckout("writing_order", o.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Order failed");
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader title="Writing & application services"
        subtitle={<span className="inline-flex items-center gap-1.5"><Clock className="h-4 w-4" aria-hidden /> Emailed to you within 24 hours of complete submission — or a full refund of the service fee.</span>} />
      {groups.map(([title, list]) => list.length > 0 && (
        <section key={title}>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-3">{title}</h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {list.map((s) => (
              <button key={s.code} onClick={() => { setSel(s); setAgree(false); setQty(1); setError(null); }}
                className={`rounded-xl border bg-surface p-5 text-left transition ${sel?.code === s.code ? "border-accent ring-2 ring-accent/20" : "border-line hover:border-accent/40"}`}>
                <div className="flex items-start justify-between gap-3">
                  <p className="font-semibold text-ink">{s.name}</p>
                  <p className="text-lg font-semibold tabular-nums text-ink">{money(s.price_cents, s.currency)}{isLetter(s) && <span className="text-xs font-normal text-ink-3"> /letter</span>}</p>
                </div>
                <p className="mt-1 text-sm text-ink-3">{s.description}</p>
                {s.restricted_countries.length > 0 && <p className="mt-2 text-xs text-warn">Not available for {s.restricted_countries.join(", ")}</p>}
              </button>
            ))}
          </div>
        </section>
      ))}

      {sel && (
        <Card className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="space-y-3">
            <h2 className="text-lg font-semibold text-ink">{sel.name}</h2>
            <div><p className="text-sm font-medium text-ink">After payment you will be asked to email:</p>
              <ul className="mt-1 space-y-1 text-sm text-ink-2">{sel.required_information.map((r) => <li key={r} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 text-ok" aria-hidden />{r}</li>)}</ul></div>
            <div><p className="text-sm font-medium text-ink">Please note before paying</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-ink-2">{sel.exclusions.map((r) => <li key={r}>{r}</li>)}</ul></div>
            {sel.disclaimer && <Alert tone="warn">{sel.disclaimer}</Alert>}
          </div>
          <div className="space-y-4">
            {isLetter(sel) && (
              <Field label="How many letters?" hint={`${money(sel.price_cents, sel.currency)} per letter. Describe each letter in the notes below.`}>
                <Input type="number" min={1} max={20} value={qty} onChange={(e) => setQty(Math.max(1, Math.min(20, Number(e.target.value) || 1)))} className="w-28" />
              </Field>
            )}
            {apps && apps.length > 0 && (
              <Field label={needsApp ? "Which application is this for? (required)" : "Related application (optional)"}>
                <Select value={appId} onChange={(e) => setAppId(e.target.value)}>
                  <option value="">{needsApp ? "Choose an application…" : "None"}</option>
                  {apps.map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}
                </Select>
              </Field>
            )}
            {needsApp && (!apps || apps.length === 0) && <Alert tone="info">Create an application first so we know which country&apos;s form to prepare.</Alert>}
            {blocked && (
              <Alert tone="bad" title="Not available for this country">
                <span className="flex gap-2"><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />In {selApp!.country_name}, preparing or lodging visa applications for a fee may only be done by a licensed immigration adviser.</span>
              </Alert>
            )}
            <Field label="Anything we should know? (optional)"><Textarea value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} /></Field>
            <label className="flex gap-2 text-sm text-ink-2"><input type="checkbox" className="mt-1" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
              I understand the 24-hour clock starts only when all required information is received, that the work is based solely on truthful information I provide, and the notes above.</label>
            {error && <Alert tone="bad">{error}</Alert>}
            <Button onClick={order} loading={busy} disabled={!agree || blocked || (needsApp && !appId)} className="w-full">
              Pay {money(total, sel.currency)} and place order
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
