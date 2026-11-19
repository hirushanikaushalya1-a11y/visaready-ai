"use client";

import { useState } from "react";
import { fmtDate, post, put } from "@/lib/api";
import { useLoad } from "@/lib/auth";
import { PageHeader } from "@/components/shell";
import { Alert, Badge, Button, Card, Field, Input, SectionTitle, Spinner } from "@/components/ui";

type R = { id: string; user_email: string; scope: string; status: string; reason: string | null; created_at: string; result: Record<string, number> };

export default function AdminPrivacy() {
  const { data, load } = useLoad<R[]>("/admin/deletion-requests");
  const { data: ret } = useLoad<{ days: number }>("/admin/settings/retention");
  const [daysInput, setDays] = useState<string | null>(null);
  const days = daysInput ?? (ret ? String(ret.days) : "");
  const [msg, setMsg] = useState<string | null>(null);
  if (!data) return <Spinner />;
  return (
    <div className="space-y-6">
      <PageHeader title="Privacy & retention" />
      {msg && <Alert tone="info">{msg}</Alert>}
      <Card className="flex flex-wrap items-end gap-3">
        <Field label="Delete documents this many days after an application is completed"><Input type="number" min={1} value={days} onChange={(e) => setDays(e.target.value)} className="w-32" /></Field>
        <Button onClick={async () => { const r = await put<{ note: string }>("/admin/settings/retention", { days: Number(days) }); setMsg(r.note); }}>Save</Button>
      </Card>
      <Card>
        <SectionTitle title="Deletion requests" subtitle="Processing permanently destroys documents and their encryption keys." />
        <ul className="divide-y divide-line">{data.map((r) => (
          <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
            <div><p className="font-medium">{r.user_email} · {r.scope}</p><p className="text-xs text-ink-3">{fmtDate(r.created_at, true)}{r.reason ? ` · “${r.reason}”` : ""}</p></div>
            {r.status === "requested" ? <Button variant="danger" size="sm" onClick={async () => { if (confirm("Permanently delete this data?")) { await post(`/admin/deletion-requests/${r.id}/process`); load(); } }}>Process deletion</Button>
              : <Badge tone="ok">{r.status} · {r.result?.documents_purged ?? 0} docs purged</Badge>}
          </li>
        ))}{!data.length && <li className="py-3 text-sm text-ink-3">No requests.</li>}</ul>
      </Card>
    </div>
  );
}
