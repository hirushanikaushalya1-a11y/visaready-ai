"use client";

import { useState } from "react";
import { fmtDate, label, post } from "@/lib/api";
import { useAuth, useLoad } from "@/lib/auth";
import { PageHeader } from "@/components/shell";
import { Alert, Badge, Card, Spinner, statusTone } from "@/components/ui";

type P = { id: string; user_email: string; purpose: string; amount: string; currency: string; status: string; provider: string; invoice_number: string | null; created_at: string; refunded: string };

export default function AdminPayments() {
  const { me } = useAuth();
  const { data, load } = useLoad<P[]>("/admin/payments");
  const [msg, setMsg] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);
  async function refund(p: P) {
    const reason = prompt(`Refund reason for ${p.invoice_number} ($${p.amount})`);
    if (!reason) return;
    try {
      const r = await post<{ status: string; failure_reason: string | null }>(`/admin/payments/${p.id}/refund`, { reason });
      setMsg(r.status === "succeeded" ? { tone: "ok", text: "Refund processed." } : { tone: "bad", text: `Refund failed: ${r.failure_reason}` });
      load();
    } catch (e) { setMsg({ tone: "bad", text: e instanceof Error ? e.message : "Failed" }); }
  }
  if (!data) return <Spinner />;
  return (
    <div className="space-y-4">
      <PageHeader title="Payments & refunds" />
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[820px] text-sm">
          <thead className="border-b border-line text-left text-xs uppercase text-ink-3"><tr><th className="px-4 py-3">Date</th><th>Customer</th><th>Purpose</th><th>Amount</th><th>Provider</th><th>Status</th><th /></tr></thead>
          <tbody className="divide-y divide-line">{data.map((p) => (
            <tr key={p.id}><td className="px-4 py-2">{fmtDate(p.created_at, true)}</td><td className="text-ink-3">{p.user_email}</td><td>{label(p.purpose)}</td>
              <td className="tabular-nums">${p.amount}{p.refunded !== "0.00" && <span className="text-xs text-info"> (−{p.refunded})</span>}</td>
              <td>{p.provider === "sandbox" ? <Badge tone="warn">sandbox</Badge> : p.provider}</td><td><Badge tone={statusTone[p.status]}>{label(p.status)}</Badge></td>
              <td className="pr-4 text-right">{me?.permissions.includes("refunds.manage") && ["succeeded", "partially_refunded"].includes(p.status) && <button className="text-bad" onClick={() => refund(p)}>Refund</button>}</td></tr>
          ))}</tbody>
        </table>
      </Card>
    </div>
  );
}
