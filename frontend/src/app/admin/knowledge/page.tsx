"use client";

import { useState } from "react";
import { ExternalLink } from "lucide-react";
import { api, fmtDate, patch, post } from "@/lib/api";
import { useAuth, useLoad } from "@/lib/auth";
import { PageHeader } from "@/components/shell";
import { Alert, Badge, Button, Card, Field, Input, SectionTitle, Spinner, Tabs, Textarea } from "@/components/ui";

type Cat = { id: string; country_code: string; name: string; category_type: string; requirements: number; verified: number; official_url: string };
type Req = { id: string; key: string; title: string; description: string; level: string; source_url: string; review_status: string; version: number; last_verified_at: string | null; source_excerpt: string | null };
type Source = { id: string; country_code: string; title: string; url: string; last_checked_at: string | null; last_changed_at: string | null };
type PAlert = { id: string; country_code: string; title: string; summary: string; status: string; source_url: string; affected: number; created_at: string };

function RequirementRow({ r, onChange }: { r: Req; onChange: () => void }) {
  const { me } = useAuth();
  const [mode, setMode] = useState<"" | "verify" | "edit">("");
  const [excerpt, setExcerpt] = useState(r.source_excerpt ?? "");
  const [checked, setChecked] = useState(false);
  const [desc, setDesc] = useState(r.description);
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const go = async (fn: () => Promise<unknown>) => { try { await fn(); setMode(""); onChange(); } catch (e) { setErr(e instanceof Error ? e.message : "Failed"); } };
  return (
    <li className="py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1"><p className="font-medium text-ink">{r.title} <span className="text-xs text-ink-3">v{r.version}</span></p><p className="text-sm text-ink-3">{r.description}</p>
          <a href={r.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-accent">{r.source_url} <ExternalLink className="h-3 w-3" aria-hidden /></a></div>
        <div className="flex items-center gap-2"><Badge tone={r.level === "mandatory" ? "info" : "neutral"}>{r.level}</Badge>
          <Badge tone={r.review_status === "verified" ? "ok" : "warn"}>{r.review_status === "verified" ? `verified ${fmtDate(r.last_verified_at)}` : r.review_status.replace("_", " ")}</Badge></div>
      </div>
      <div className="mt-2 flex gap-2">
        {me?.permissions.includes("knowledge.verify") && <Button size="sm" variant="secondary" onClick={() => setMode(mode === "verify" ? "" : "verify")}>Verify</Button>}
        {me?.permissions.includes("knowledge.manage") && <Button size="sm" variant="ghost" onClick={() => setMode(mode === "edit" ? "" : "edit")}>Edit</Button>}
      </div>
      {err && <div className="mt-2"><Alert tone="bad">{err}</Alert></div>}
      {mode === "verify" && (
        <div className="mt-3 space-y-3 rounded-lg bg-surface-2 p-3">
          <Field label="Quote the official wording you checked"><Textarea value={excerpt} onChange={(e) => setExcerpt(e.target.value)} /></Field>
          <label className="flex gap-2 text-sm"><input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} /> I opened the official source today and confirm this requirement matches it.</label>
          <Button size="sm" disabled={!checked} onClick={() => go(() => post(`/admin/knowledge/requirements/${r.id}/verify`, { confirm_checked_official_source: checked, source_excerpt: excerpt || null }))}>Mark verified</Button>
        </div>
      )}
      {mode === "edit" && (
        <div className="mt-3 space-y-3 rounded-lg bg-surface-2 p-3">
          <Field label="Description"><Textarea value={desc} onChange={(e) => setDesc(e.target.value)} /></Field>
          <Field label="Change note (required)" hint="Editing creates a new version and resets verification."><Input value={note} onChange={(e) => setNote(e.target.value)} /></Field>
          <Button size="sm" disabled={note.length < 3} onClick={() => go(() => patch(`/admin/knowledge/requirements/${r.id}`, { description: desc, change_note: note }))}>Save new version</Button>
        </div>
      )}
    </li>
  );
}

export default function AdminKnowledge() {
  const [tab, setTab] = useState("requirements");
  const { data: cats, load: loadCats } = useLoad<Cat[]>("/admin/knowledge/categories");
  const [cat, setCat] = useState<Cat | null>(null);
  const [reqs, setReqs] = useState<Req[] | null>(null);
  const { data: sources, load: loadSources } = useLoad<Source[]>("/admin/knowledge/sources");
  const { data: alerts, load: loadAlerts } = useLoad<PAlert[]>("/admin/policy-alerts");
  const [msg, setMsg] = useState<string | null>(null);
  const openCat = async (c: Cat) => { setCat(c); setReqs(await api<Req[]>(`/admin/knowledge/requirements?category_id=${c.id}`)); };
  if (!cats) return <Spinner />;
  return (
    <div className="space-y-6">
      <PageHeader title="Immigration knowledge base" subtitle="Only official government sources. Nothing is shown to applicants as verified until a person has checked it." />
      <Tabs active={tab} onChange={setTab} tabs={[{ id: "requirements", label: "Requirements" }, { id: "sources", label: "Official sources" }, { id: "alerts", label: "Policy alerts" }]} />
      {msg && <Alert tone="info">{msg}</Alert>}
      {tab === "requirements" && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="max-h-[70vh] overflow-y-auto p-2">
            <ul>{cats.map((c) => (
              <li key={c.id}><button onClick={() => openCat(c)} className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-2 ${cat?.id === c.id ? "bg-surface-2" : ""}`}>
                <span><b>{c.country_code}</b> · {c.name}</span><span className="text-xs text-ink-3">{c.verified}/{c.requirements}</span></button></li>
            ))}</ul>
          </Card>
          <Card className="lg:col-span-2">
            {!cat ? <p className="text-sm text-ink-3">Select a visa category.</p> : !reqs ? <Spinner /> : (
              <>
                <SectionTitle title={`${cat.country_code} · ${cat.name}`} subtitle={<a href={cat.official_url} className="text-accent" target="_blank" rel="noreferrer">{cat.official_url}</a>} />
                {!reqs.length ? <Alert tone="warn">No requirements loaded for this category yet. Add them from the official source via the API (POST /api/admin/knowledge/requirements).</Alert> :
                  <ul className="divide-y divide-line">{reqs.map((r) => <RequirementRow key={r.id} r={r} onChange={() => { openCat(cat); loadCats(); }} />)}</ul>}
              </>
            )}
          </Card>
        </div>
      )}
      {tab === "sources" && (
        <Card className="overflow-x-auto p-0">
          <table className="w-full min-w-[700px] text-sm"><thead className="border-b border-line text-left text-xs uppercase text-ink-3"><tr><th className="px-4 py-3">Country</th><th>Source</th><th>Last checked</th><th>Last change</th><th /></tr></thead>
            <tbody className="divide-y divide-line">{sources?.map((s) => (
              <tr key={s.id}><td className="px-4 py-2">{s.country_code}</td><td><a href={s.url} target="_blank" rel="noreferrer" className="text-accent">{s.title}</a></td><td>{fmtDate(s.last_checked_at, true)}</td><td>{fmtDate(s.last_changed_at)}</td>
                <td className="pr-4 text-right"><Button size="sm" variant="secondary" onClick={async () => { const r = await post<{ ok: boolean; changed?: boolean; error?: string }>(`/admin/knowledge/sources/${s.id}/check`); setMsg(r.ok ? (r.changed ? "Change detected — a policy alert was created for review." : "No change detected (or first baseline recorded).") : r.error ?? "Check failed"); loadSources(); loadAlerts(); }}>Check now</Button></td></tr>
            ))}</tbody></table>
        </Card>
      )}
      {tab === "alerts" && (
        <div className="space-y-3">
          {!alerts?.length && <p className="text-sm text-ink-3">No policy alerts.</p>}
          {alerts?.map((a) => (
            <Card key={a.id} className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1"><p className="font-medium text-ink">{a.country_code} · {a.title}</p><p className="text-sm text-ink-3">{a.summary}</p><a href={a.source_url} target="_blank" rel="noreferrer" className="text-xs text-accent">{a.source_url}</a></div>
              {a.status === "published" ? <Badge tone="ok">Published · {a.affected} notified</Badge> :
                <Button size="sm" onClick={async () => { if (confirm("Publish only after verifying the change on the official source. Affected applicants will be notified.")) { await post(`/admin/policy-alerts/${a.id}/publish`); loadAlerts(); } }}>Verify & notify applicants</Button>}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
