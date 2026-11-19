"use client";

import { useState } from "react";
import { fmtDate } from "@/lib/api";
import { useLoad } from "@/lib/auth";
import { PageHeader } from "@/components/shell";
import { Card, Input, Spinner } from "@/components/ui";

type L = { id: string; action: string; actor_role: string | null; target_type: string | null; target_id: string | null; ip: string | null; details: Record<string, unknown>; created_at: string };

export default function AdminAudit() {
  const [action, setAction] = useState("");
  const { data } = useLoad<L[]>(`/admin/audit-logs${action ? `?action=${encodeURIComponent(action)}` : ""}`);
  return (
    <div className="space-y-4">
      <PageHeader title="Audit log" subtitle="Authentication, document access, admin actions, payments and privacy events." />
      <Input placeholder="Filter by action prefix (e.g. document, auth, privacy)" value={action} onChange={(e) => setAction(e.target.value)} className="max-w-sm" />
      {!data ? <Spinner /> : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full min-w-[820px] text-sm">
            <thead className="border-b border-line text-left text-xs uppercase text-ink-3"><tr><th className="px-4 py-3">Time</th><th>Action</th><th>Actor role</th><th>Target</th><th>IP</th><th>Details</th></tr></thead>
            <tbody className="divide-y divide-line">{data.map((l) => (
              <tr key={l.id}><td className="whitespace-nowrap px-4 py-2">{fmtDate(l.created_at, true)}</td><td className="font-mono text-xs">{l.action}</td><td>{l.actor_role ?? "system"}</td>
                <td className="text-xs text-ink-3">{l.target_type}{l.target_id ? `:${l.target_id.slice(0, 8)}` : ""}</td><td className="text-xs">{l.ip}</td>
                <td className="max-w-xs truncate font-mono text-xs text-ink-3">{JSON.stringify(l.details)}</td></tr>
            ))}</tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
