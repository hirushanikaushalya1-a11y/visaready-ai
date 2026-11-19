"use client";

import { useParams } from "next/navigation";
import { CheckCircle2, Circle, Download, Mail } from "lucide-react";
import { fmtDate, label, amount } from "@/lib/api";
import { useLoad } from "@/lib/auth";
import { startCheckout } from "@/lib/checkout";
import type { WritingOrder } from "@/lib/types";
import { PageHeader } from "@/components/shell";
import { Countdown } from "@/components/countdown";
import { Alert, Badge, Button, Card, SectionTitle, Spinner, statusTone } from "@/components/ui";

const STAGES = [
  ["payment_successful", "Payment received"], ["awaiting_documents", "Waiting for your information"], ["submission_complete", "Everything received — clock started"],
  ["processing", "Being written"], ["quality_review", "Quality review"], ["delivered", "Delivered"],
];
const ORDER = ["payment_pending", "payment_successful", "awaiting_documents", "information_incomplete", "submission_complete", "processing", "quality_review", "delivered"];

export default function OrderPage() {
  const { id } = useParams<{ id: string }>();
  const { data: o } = useLoad<WritingOrder>(`/writing-orders/${id}`);
  if (!o) return <Spinner />;
  const idx = ORDER.indexOf(o.status === "refund_eligible" || o.status.startsWith("refund") ? (o.delivered_at ? "delivered" : "quality_review") : o.status);
  return (
    <div className="space-y-6">
      <PageHeader title={o.service_name} subtitle={<>Order <b>{o.reference}</b> · {amount(o.price, o.currency)}{o.quantity > 1 ? ` (${o.quantity} letters)` : ""}</>} actions={<Badge tone={statusTone[o.status]}>{label(o.status)}</Badge>} />
      {o.status === "payment_pending" && <Card className="flex items-center justify-between gap-4"><p className="text-sm text-ink-2">Payment not completed yet.</p><Button onClick={() => startCheckout("writing_order", o.id)}>Pay {amount(o.price, o.currency)}</Button></Card>}
      {["awaiting_documents", "information_incomplete"].includes(o.status) && (
        <Card className="border-accent/30">
          <div className="flex gap-3"><Mail className="mt-1 h-5 w-5 text-accent" aria-hidden />
            <div className="space-y-2">
              <p className="font-medium text-ink">Send your information to <a className="text-accent underline" href={`mailto:${o.submission_email}?subject=${o.reference}`}>{o.submission_email}</a></p>
              <p className="text-sm text-ink-2">Put <b>{o.reference}</b> in the subject line and include:</p>
              <ul className="list-disc pl-5 text-sm text-ink-2">{o.required_information.map((r) => <li key={r}>{r}</li>)}</ul>
              <p className="text-xs text-ink-3">Your 24-hour delivery clock starts when we confirm we have everything. We&apos;ll notify you right away if something is missing.</p>
            </div>
          </div>
        </Card>
      )}
      {o.status === "information_incomplete" && o.missing_information_note && <Alert tone="warn" title="We need a little more information">{o.missing_information_note}</Alert>}
      {o.deadline_at && o.seconds_remaining != null && (
        <Card className="flex flex-wrap items-center justify-between gap-4">
          <div><p className="text-sm text-ink-3">Guaranteed delivery by</p><p className="font-medium text-ink">{fmtDate(o.deadline_at, true)}</p></div>
          <div className="text-right"><p className="text-sm text-ink-3">Time remaining</p><p className="text-2xl"><Countdown deadline={o.deadline_at} /></p></div>
        </Card>
      )}
      {o.refund_eligible && <Alert tone="info" title="You are entitled to a full refund of this order's fee">We missed our 24-hour guarantee. The refund is returned to your original payment method; banks can take 5–10 business days to show it. Status: {label(o.status)}.</Alert>}
      {o.deliverables.length > 0 && (
        <Card><SectionTitle title="Your document" subtitle="Review every fact carefully before using it. You are responsible for the truth of what you submit." />
          {o.deliverables.map((d) => <a key={d.id} href={`/api/writing-orders/${o.id}/deliverables/${d.id}`} className="inline-flex items-center gap-2 rounded-lg border border-line px-4 py-2 text-sm hover:bg-surface-2"><Download className="h-4 w-4" aria-hidden />{d.filename}</a>)}
          {o.disclaimer && <p className="mt-3 text-xs text-warn">{o.disclaimer}</p>}
        </Card>
      )}
      <Card><SectionTitle title="Progress" />
        <ol className="space-y-3">
          {STAGES.map(([k, l]) => {
            const done = ORDER.indexOf(k) <= idx;
            return <li key={k} className="flex items-center gap-3 text-sm">{done ? <CheckCircle2 className="h-5 w-5 text-ok" aria-hidden /> : <Circle className="h-5 w-5 text-line" aria-hidden />}<span className={done ? "text-ink" : "text-ink-3"}>{l}</span></li>;
          })}
        </ol>
        {o.events && <details className="mt-4 text-xs text-ink-3"><summary className="cursor-pointer">Full timeline</summary><ul className="mt-2 space-y-1">{o.events.map((e, i) => <li key={i}>{fmtDate(e.at, true)} — {label(e.to)}{e.note ? ` (${e.note})` : ""}</li>)}</ul></details>}
      </Card>
    </div>
  );
}
