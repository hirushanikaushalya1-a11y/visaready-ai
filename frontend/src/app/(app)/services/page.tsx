"use client";

import { useState } from "react";
import { Check, Clock } from "lucide-react";
import { money, post } from "@/lib/api";
import { useLoad } from "@/lib/auth";
import { startCheckout } from "@/lib/checkout";
import type { Application, Service, WritingOrder } from "@/lib/types";
import { PageHeader } from "@/components/shell";
import { Alert, Button, Card, Field, Select, Spinner, Textarea } from "@/components/ui";

export default function ServicesPage() {
  const { data } = useLoad<Service[]>("/services");
  const { data: apps } = useLoad<Application[]>("/applications");
  const [sel, setSel] = useState<Service | null>(null);
  const [notes, setNotes] = useState("");
  const [appId, setAppId] = useState("");
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!data) return <Spinner />;
  const writing = data.filter((s) => s.kind === "writing");

  async function order() {
    setBusy(true);
    setError(null);
    try {
      const o = await post<WritingOrder>("/writing-orders", { service_code: sel!.code, notes: notes || null, application_id: appId || null });
      await startCheckout("writing_order", o.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Order failed");
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Document writing services" subtitle={<span className="inline-flex items-center gap-1.5"><Clock className="h-4 w-4" aria-hidden /> Delivered within 24 hours of complete submission — or a full refund of the document fee.</span>} />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {writing.map((s) => (
          <button key={s.code} onClick={() => { setSel(s); setAgree(false); }} className={`rounded-xl border bg-surface p-5 text-left transition ${sel?.code === s.code ? "border-accent ring-2 ring-accent/20" : "border-line hover:border-accent/40"}`}>
            <div className="flex items-start justify-between gap-3"><p className="font-semibold text-ink">{s.name}</p><p className="text-lg font-semibold tabular-nums text-ink">{money(s.price_cents)}</p></div>
            <p className="mt-1 text-sm text-ink-3">{s.description}</p>
          </button>
        ))}
      </div>
      {sel && (
        <Card className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="space-y-3">
            <h2 className="text-lg font-semibold text-ink">{sel.name} — {money(sel.price_cents)}</h2>
            <div><p className="text-sm font-medium text-ink">After payment you will be asked to email:</p>
              <ul className="mt-1 space-y-1 text-sm text-ink-2">{sel.required_information.map((r) => <li key={r} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 text-ok" aria-hidden />{r}</li>)}</ul></div>
            <div><p className="text-sm font-medium text-ink">Please note before paying</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-ink-2">{sel.exclusions.map((r) => <li key={r}>{r}</li>)}</ul></div>
            {sel.disclaimer && <Alert tone="warn">{sel.disclaimer}</Alert>}
          </div>
          <div className="space-y-4">
            {apps && apps.length > 0 && (
              <Field label="Related application (optional)"><Select value={appId} onChange={(e) => setAppId(e.target.value)}><option value="">None</option>{apps.map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}</Select></Field>
            )}
            <Field label="Anything we should know? (optional)"><Textarea value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} /></Field>
            <label className="flex gap-2 text-sm text-ink-2"><input type="checkbox" className="mt-1" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
              I understand the 24-hour clock starts only when all required information is received, that the document is based solely on truthful information I provide, and the exclusions above.</label>
            {error && <Alert tone="bad">{error}</Alert>}
            <Button onClick={order} loading={busy} disabled={!agree} className="w-full">Pay {money(sel.price_cents)} and place order</Button>
          </div>
        </Card>
      )}
    </div>
  );
}
