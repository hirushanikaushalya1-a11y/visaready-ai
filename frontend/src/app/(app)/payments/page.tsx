"use client";

import { fmtDate, label } from "@/lib/api";
import { useLoad } from "@/lib/auth";
import { PageHeader } from "@/components/shell";
import { Badge, Card, Empty, Spinner, statusTone } from "@/components/ui";

type P = { id: string; purpose: string; amount: string; currency: string; status: string; invoice_number: string | null; created_at: string; provider: string; refunded: string };

export default function PaymentsPage() {
  const { data } = useLoad<P[]>("/payments");
  if (!data) return <Spinner />;
  return (
    <div>
      <PageHeader title="Payments" subtitle="We never see or store your card details." />
      {!data.length ? <Empty title="No payments yet" /> : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="border-b border-line text-left text-xs uppercase text-ink-3"><tr><th className="px-4 py-3">Date</th><th>For</th><th>Amount</th><th>Status</th><th>Invoice</th></tr></thead>
            <tbody className="divide-y divide-line">
              {data.map((p) => (
                <tr key={p.id}>
                  <td className="px-4 py-3">{fmtDate(p.created_at)}</td>
                  <td>{label(p.purpose)}{p.provider === "sandbox" && <Badge tone="warn" className="ml-2">test</Badge>}</td>
                  <td className="tabular-nums">${p.amount} {p.currency}{p.refunded !== "0.00" && <span className="ml-1 text-xs text-info">(−${p.refunded} refunded)</span>}</td>
                  <td><Badge tone={statusTone[p.status]}>{label(p.status)}</Badge></td>
                  <td>{p.invoice_number ? <a className="text-accent underline" href={`/api/payments/${p.id}/invoice`} target="_blank" rel="noreferrer">{p.invoice_number}</a> : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
