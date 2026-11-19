"use client";

import Link from "next/link";
import { useState } from "react";
import { fmtDate, label, post } from "@/lib/api";
import { useLoad } from "@/lib/auth";
import type { WritingOrder } from "@/lib/types";
import { PageHeader } from "@/components/shell";
import { Countdown } from "@/components/countdown";
import { Badge, Button, Card, Select, Spinner, statusTone } from "@/components/ui";

export default function AdminOrders() {
  const [status, setStatus] = useState("");
  const { data, load } = useLoad<WritingOrder[]>(`/admin/writing-orders${status ? `?status=${status}` : ""}`);
  return (
    <div className="space-y-4">
      <PageHeader title="Writing orders" subtitle="Sorted by deadline. The clock starts only when you mark a submission complete."
        actions={<Button variant="secondary" size="sm" onClick={async () => { await post("/admin/writing-orders/sla-sweep"); load(); }}>Run SLA check now</Button>} />
      <Select className="!w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="">All statuses</option>{["awaiting_documents", "information_incomplete", "submission_complete", "processing", "quality_review", "delivered", "refund_eligible", "refunded"].map((s) => <option key={s} value={s}>{label(s)}</option>)}
      </Select>
      {!data ? <Spinner /> : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="border-b border-line text-left text-xs uppercase text-ink-3"><tr><th className="px-4 py-3">Reference</th><th>Service</th><th>Customer</th><th>Status</th><th>Deadline</th><th>Remaining</th></tr></thead>
            <tbody className="divide-y divide-line">
              {data.map((o) => (
                <tr key={o.id} className="hover:bg-surface-2">
                  <td className="px-4 py-3"><Link href={`/admin/orders/${o.id}`} className="font-medium text-accent">{o.reference}</Link></td>
                  <td>{o.service_name}</td><td className="text-ink-3">{o.customer?.email}</td>
                  <td><Badge tone={statusTone[o.status]}>{label(o.status)}</Badge></td>
                  <td>{fmtDate(o.deadline_at, true)}</td>
                  <td>{o.deadline_at && o.seconds_remaining != null ? <Countdown deadline={o.deadline_at} /> : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
