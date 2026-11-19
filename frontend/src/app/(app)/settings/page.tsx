"use client";

import { useState } from "react";
import { fmtDate as fmt, post, put } from "@/lib/api";
import { useAuth, useLoad } from "@/lib/auth";
import { PageHeader } from "@/components/shell";
import { Alert, Badge, Button, Card, Field, Input, SectionTitle, Spinner, Textarea } from "@/components/ui";

type Privacy = { ai_training_consent: boolean; marketing_consent: boolean; retention_days_after_completion: number;
  processors: { name: string; purpose: string }[]; deletion_requests: { id: string; scope: string; status: string; created_at: string }[] };

export default function SettingsPage() {
  const { me, reload } = useAuth();
  const { data, load } = useLoad<Privacy>("/privacy");
  const [msg, setMsg] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);
  const [mfa, setMfa] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [ticket, setTicket] = useState({ subject: "", body: "" });
  if (!data || !me) return <Spinner />;

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setMsg(null);
    try { await fn(); setMsg({ tone: "ok", text: ok }); load(); reload(); } catch (e) { setMsg({ tone: "bad", text: e instanceof Error ? e.message : "Failed" }); }
  };
  async function exportData() {
    const r = await fetch("/api/privacy/export", { credentials: "same-origin" });
    const blob = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "visaready-my-data.json";
    a.click();
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Privacy & security" />
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}
      <Card>
        <SectionTitle title="Your consents" subtitle="You can change these at any time." />
        <label className="flex items-start gap-3 py-2 text-sm"><input type="checkbox" className="mt-1" checked={data.ai_training_consent}
          onChange={(e) => run(() => put("/privacy", { ai_training_consent: e.target.checked }), "Preference saved")} />
          <span><b className="text-ink">Allow anonymised use of my documents to improve VisaReady AI models.</b><br /><span className="text-ink-3">Off by default. Your documents are never used for training unless you switch this on.</span></span></label>
        <label className="flex items-start gap-3 py-2 text-sm"><input type="checkbox" className="mt-1" checked={data.marketing_consent}
          onChange={(e) => run(() => put("/privacy", { marketing_consent: e.target.checked }), "Preference saved")} />
          <span className="text-ink">Product updates by email</span></label>
      </Card>
      <Card>
        <SectionTitle title="How we handle your data" />
        <p className="text-sm text-ink-2">Documents are deleted <b>{data.retention_days_after_completion} days</b> after you mark an application as submitted, or immediately on request. We do not sell personal data.</p>
        <ul className="mt-3 space-y-1.5 text-sm">{data.processors.map((p) => <li key={p.name}><b className="text-ink">{p.name}:</b> <span className="text-ink-2">{p.purpose}</span></li>)}</ul>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="secondary" onClick={exportData}>Download my data (JSON)</Button>
          <Button variant="danger" onClick={() => confirm("Request deletion of your account and all documents? This cannot be undone once processed.") && run(() => post("/privacy/deletion-requests", { scope: "account" }), "Deletion request received. We will confirm by email.")}>Request account deletion</Button>
        </div>
        {data.deletion_requests.length > 0 && <ul className="mt-3 space-y-1 text-xs text-ink-3">{data.deletion_requests.map((r) => <li key={r.id}>{r.scope} deletion requested {fmt(r.created_at)} — <Badge tone={r.status === "completed" ? "ok" : "warn"}>{r.status}</Badge></li>)}</ul>}
      </Card>
      <Card>
        <SectionTitle title="Two-step verification" subtitle="Protect your account with an authenticator app (TOTP)." />
        {me.mfa_enabled ? <Badge tone="ok">Enabled</Badge> : mfa ? (
          <div className="space-y-3">
            <p className="text-sm text-ink-2">Add this key to Google Authenticator, Microsoft Authenticator or similar:</p>
            <code className="block break-all rounded bg-surface-2 px-3 py-2 text-sm">{mfa.secret}</code>
            <Field label="Enter the 6-digit code"><Input value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" /></Field>
            <Button onClick={() => run(() => post("/auth/mfa/enable", { code }), "Two-step verification enabled")}>Confirm</Button>
          </div>
        ) : <Button variant="secondary" onClick={async () => setMfa(await post("/auth/mfa/setup"))}>Set up</Button>}
        <div className="mt-4"><Button variant="ghost" size="sm" onClick={() => run(() => post("/auth/logout-all"), "Signed out everywhere")}>Sign out of all devices</Button></div>
      </Card>
      <Card>
        <SectionTitle title="Contact support" />
        <div className="space-y-3">
          <Field label="Subject"><Input value={ticket.subject} onChange={(e) => setTicket({ ...ticket, subject: e.target.value })} /></Field>
          <Field label="Message"><Textarea value={ticket.body} onChange={(e) => setTicket({ ...ticket, body: e.target.value })} /></Field>
          <Button onClick={() => run(async () => { await post("/support/tickets", ticket); setTicket({ subject: "", body: "" }); }, "Message sent. We'll reply by email.")} disabled={ticket.subject.length < 3 || ticket.body.length < 5}>Send</Button>
        </div>
      </Card>
    </div>
  );
}
