"use client";

import { useParams } from "next/navigation";
import { useRef, useState } from "react";
import { fmtDate, label, post, upload } from "@/lib/api";
import { useAuth, useLoad } from "@/lib/auth";
import type { WritingOrder } from "@/lib/types";
import { PageHeader } from "@/components/shell";
import { Countdown } from "@/components/countdown";
import { Alert, Badge, Button, Card, Field, SectionTitle, Spinner, statusTone, Textarea } from "@/components/ui";

export default function AdminOrder() {
  const { id } = useParams<{ id: string }>();
  const { me } = useAuth();
  const { data: o, setData } = useLoad<WritingOrder>(`/admin/writing-orders/${id}`);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  if (!o) return <Spinner />;
  const can = (p: string) => me?.permissions.includes(p);

  async function act(action: string) {
    setBusy(true);
    setError(null);
    try { setData(await post<WritingOrder>(`/admin/writing-orders/${id}/action`, { action, note: note || null })); setNote(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed"); } finally { setBusy(false); }
  }
  async function deliver(f: File) {
    setBusy(true);
    const fd = new FormData();
    fd.append("file", f);
    try { setData(await upload<WritingOrder>(`/admin/writing-orders/${id}/deliver`, fd)); } catch (e) { setError(e instanceof Error ? e.message : "Failed"); } finally { setBusy(false); }
  }

  return (
    <div className="space-y-6">
      <PageHeader title={`${o.reference} · ${o.service_name}`} subtitle={`${o.customer?.name} <${o.customer?.email}> · $${o.price}`} actions={<Badge tone={statusTone[o.status]}>{label(o.status)}</Badge>} />
      {error && <Alert tone="bad">{error}</Alert>}
      {o.deadline_at && <Card className="flex justify-between"><span>Deadline {fmtDate(o.deadline_at, true)}</span>{o.seconds_remaining != null && <Countdown deadline={o.deadline_at} />}</Card>}
      {o.customer_notes && <Card><SectionTitle title="Customer notes" /><p className="whitespace-pre-line text-sm text-ink-2">{o.customer_notes}</p></Card>}
      {can("writing_orders.manage") && (
        <Card className="space-y-4">
          <SectionTitle title="Actions" subtitle={`Customers email documents to ${o.submission_email} quoting ${o.reference}.`} />
          {["awaiting_documents", "information_incomplete"].includes(o.status) && (<>
            <Field label="What is missing? (sent to the customer)"><Textarea value={note} onChange={(e) => setNote(e.target.value)} /></Field>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" onClick={() => act("incomplete")} disabled={!note} loading={busy}>Request missing information</Button>
              <Button onClick={() => act("complete")} loading={busy}>All information received — start 24h clock</Button>
            </div>
          </>)}
          {(o.status === "submission_complete" || o.status === "refund_eligible") && !o.delivered_at && <Button onClick={() => act("start")} loading={busy}>Start writing</Button>}
          {o.status === "processing" && <Button onClick={() => act("review")} loading={busy}>Send to quality review</Button>}
          {o.status === "quality_review" && <Button variant="secondary" onClick={() => act("rework")} loading={busy}>Return for rework</Button>}
          {(o.status === "quality_review" || (o.status === "refund_eligible" && !o.delivered_at)) && (<>
            <input ref={file} type="file" accept=".pdf,.docx" className="hidden" onChange={(e) => e.target.files?.[0] && deliver(e.target.files[0])} />
            <Button variant="accent" onClick={() => file.current?.click()} loading={busy}>Approve & deliver (upload PDF/DOCX)</Button>
          </>)}
        </Card>
      )}
      {o.status === "refund_eligible" && can("refunds.manage") && (
        <Card className="flex items-center justify-between gap-4 border-bad/30"><p className="text-sm text-ink-2">This order missed the 24-hour guarantee. Refund ${o.price} to the original payment method.</p>
          <Button variant="danger" onClick={async () => { try { setData(await post(`/admin/writing-orders/${id}/refund`)); } catch (e) { setError(e instanceof Error ? e.message : "Failed"); } }}>Process refund</Button></Card>
      )}
      <Card><SectionTitle title="Timeline" />
        <ul className="space-y-1.5 text-sm">{o.events?.map((e, i) => <li key={i}><span className="text-ink-3">{fmtDate(e.at, true)}</span> — {label(e.from)} → <b>{label(e.to)}</b>{e.note ? ` · ${e.note}` : ""}</li>)}</ul></Card>
    </div>
  );
}
