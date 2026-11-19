"use client";

import { useState } from "react";
import { fmtDate, patch } from "@/lib/api";
import { useAuth, useLoad } from "@/lib/auth";
import { PageHeader } from "@/components/shell";
import { Alert, Badge, Card, Input, Select, Spinner } from "@/components/ui";

type U = { id: string; email: string; full_name: string; role: string; is_active: boolean; mfa_enabled: boolean; created_at: string; last_login_at: string | null };
const ROLES = ["applicant", "support", "translator", "reviewer", "document_team", "admin", "super_admin"];

export default function AdminUsers() {
  const { me } = useAuth();
  const [q, setQ] = useState("");
  const { data, load } = useLoad<U[]>(`/admin/users${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  const [err, setErr] = useState<string | null>(null);
  const canManage = me?.permissions.includes("users.manage");
  const change = async (u: U, body: object) => { setErr(null); try { await patch(`/admin/users/${u.id}`, body); load(); } catch (e) { setErr(e instanceof Error ? e.message : "Failed"); } };
  return (
    <div className="space-y-4">
      <PageHeader title="Users & roles" subtitle="Staff only see what their role requires. Role changes are audit-logged." />
      <Input placeholder="Search email or name" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-sm" />
      {err && <Alert tone="bad">{err}</Alert>}
      {!data ? <Spinner /> : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="border-b border-line text-left text-xs uppercase text-ink-3"><tr><th className="px-4 py-3">User</th><th>Role</th><th>MFA</th><th>Last login</th><th>Status</th></tr></thead>
            <tbody className="divide-y divide-line">{data.map((u) => (
              <tr key={u.id}>
                <td className="px-4 py-2"><p className="font-medium">{u.full_name}</p><p className="text-xs text-ink-3">{u.email}</p></td>
                <td>{canManage && u.id !== me?.id ? <Select className="h-8 !w-auto py-0" value={u.role} onChange={(e) => change(u, { role: e.target.value })}>{ROLES.map((r) => <option key={r} value={r}>{r.replace("_", " ")}</option>)}</Select> : u.role}</td>
                <td>{u.mfa_enabled ? <Badge tone="ok">on</Badge> : <Badge tone={u.role === "applicant" ? "neutral" : "warn"}>off</Badge>}</td>
                <td>{fmtDate(u.last_login_at, true)}</td>
                <td>{canManage && u.id !== me?.id ? <button className={u.is_active ? "text-bad" : "text-ok"} onClick={() => change(u, { is_active: !u.is_active })}>{u.is_active ? "Suspend" : "Reactivate"}</button> : (u.is_active ? "active" : "suspended")}</td>
              </tr>))}</tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
