"use client";

import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle, ArrowRight, Check, CheckCircle2, CircleDashed, Copy, Download, ExternalLink, FileText, HelpCircle, Link2, Lock, PenLine,
  RefreshCw, Scale, ShieldAlert, Trash2, Upload, X,
} from "lucide-react";
import { api, del, fmtDate, label, post, put, upload } from "@/lib/api";
import type { Application, Assessment, ChecklistItem, Claim, Diff, Doc, Finding } from "@/lib/types";
import { DropZone } from "./quickcheck";
import { Alert, Badge, Button, Card, cx, Empty, Field, Input, Progress, ScoreRing, SectionTitle, Select, severityTone, Spinner, statusTone } from "./ui";

export const DOC_TYPES: [string, string][] = [
  ["passport", "Passport"], ["birth_certificate", "Birth certificate"], ["marriage_certificate", "Marriage certificate"],
  ["academic_certificate", "Academic certificate"], ["academic_transcript", "Academic transcript"], ["bank_statement", "Bank statement"],
  ["salary_slip", "Salary slip"], ["employment_letter", "Employment letter"], ["experience_certificate", "Experience certificate"],
  ["tax_record", "Tax record"], ["business_registration", "Business registration"], ["affidavit", "Affidavit"],
  ["offer_letter", "Offer / CAS / CoE / acceptance letter"], ["employment_contract", "Job offer / contract / CoS"],
  ["english_test_result", "English test result"], ["travel_document", "Previous visa / permit"], ["visa_refusal", "Visa refusal letter"],
  ["sponsorship_letter", "Sponsorship letter"], ["relationship_evidence", "Relationship evidence"], ["cv", "CV"], ["sop", "Statement of purpose"],
  ["police_certificate", "Police certificate"], ["medical_report", "Medical / TB certificate"], ["professional_registration", "Professional registration"],
  ["skills_assessment", "Skills assessment"], ["other", "Other"],
];
const docTypeLabel = (t?: string | null) => DOC_TYPES.find(([k]) => k === t)?.[1] ?? label(t);

const CERTAINTY: Record<string, { label: string; tone: "bad" | "warn" | "info" | "neutral" }> = {
  confirmed_missing_requirement: { label: "Confirmed missing requirement", tone: "bad" },
  potential_concern: { label: "Potential concern", tone: "warn" },
  requires_professional_judgement: { label: "Needs professional judgement", tone: "info" },
  observation: { label: "Observation", tone: "neutral" },
};

// ------------------------------------------------------------------ Overview
export function Overview({ app, a, onRun, running, onBuyReport }: { app: Application; a: Assessment | null; onRun: () => void; running: boolean; onBuyReport: () => void }) {
  const remaining = app.reassessments.remaining;
  if (!a) {
    return (
      <Card className="text-center">
        <p className="font-semibold text-ink">Ready for your first assessment?</p>
        <p className="mx-auto mt-1 max-w-lg text-sm text-ink-3">Your assessment is free. Complete your profile and upload your documents first — the assessment can only check what it can see. You have {remaining} free assessment run(s) for this application.</p>
        <Button className="mt-4" onClick={onRun} loading={running} disabled={!remaining}>Run assessment</Button>
      </Card>
    );
  }
  const comps = a.score_breakdown.components;
  const strengths = a.findings.filter((f) => f.kind === "strength");
  const names: Record<string, string> = { profile: "Profile completeness", requirements: "Official requirements covered", evidence: "Claims supported by evidence", consistency: "Consistency between documents" };
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <Card className="flex flex-col items-center gap-3 text-center">
        <ScoreRing score={a.readiness_score} size={148} />
        <p className="text-xs text-ink-3">Version {a.version} · {fmtDate(a.created_at, true)}</p>
        <p className="text-xs text-ink-3">{a.score_breakdown.note}</p>
        <div className="flex flex-wrap justify-center gap-2">
          <Button onClick={onRun} loading={running} disabled={!remaining} size="sm"><RefreshCw className="h-4 w-4" aria-hidden /> Reassess ({remaining} left)</Button>
          {app.report_unlocked
            ? <a href={`/api/assessments/${a.id}/report`} target="_blank" rel="noreferrer" className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-line px-3 text-sm text-ink hover:bg-surface-2"><Download className="h-4 w-4" aria-hidden /> Full report</a>
            : <Button size="sm" variant="secondary" onClick={onBuyReport}><Lock className="h-4 w-4" aria-hidden /> Full report</Button>}
        </div>
      </Card>
      <Card className="lg:col-span-2">
        <SectionTitle title="Why this score" subtitle="Every point is explained. Uploading unrelated documents never changes it." />
        <div className="space-y-4">
          {Object.entries(comps).map(([k, c]) => (
            <div key={k}>
              <div className="flex items-center justify-between text-sm"><span className="font-medium text-ink">{names[k]}</span>
                <span className="tabular-nums text-ink-2">{c.points == null ? "excluded" : `${c.points} / ${c.max_points}`}</span></div>
              {c.ratio != null && <div className="mt-1.5"><Progress value={c.ratio * 100} tone={c.ratio > 0.75 ? "ok" : c.ratio > 0.4 ? "warn" : "bad"} /></div>}
              <p className="mt-1 text-xs text-ink-3">{c.explanation}</p>
              {c.deductions && c.deductions.length > 0 && (
                <ul className="mt-1 space-y-0.5 text-xs text-ink-3">{c.deductions.slice(0, 5).map((d) => <li key={d.title}>−{d.points}: {d.title}</li>)}</ul>
              )}
            </div>
          ))}
        </div>
      </Card>
      <Card className="lg:col-span-2">
        <SectionTitle title="Summary" />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[["High-priority issues", a.summary.counts.high], ["Medium", a.summary.counts.medium], ["Checklist done", `${a.summary.counts.satisfied_items}/${a.summary.counts.total_items}`], ["Claims supported", `${a.summary.counts.claims_supported}/${a.summary.counts.claims_total}`]].map(([l, v]) => (
            <div key={l as string} className="rounded-lg bg-surface-2 p-3"><p className="text-xs text-ink-3">{l}</p><p className="text-xl font-semibold tabular-nums text-ink">{v}</p></div>
          ))}
        </div>
        {strengths.length > 0 && (
          <div className="mt-5"><p className="text-sm font-medium text-ink">Strengths</p>
            <ul className="mt-2 space-y-1.5">{strengths.map((s) => <li key={s.id} className="flex gap-2 text-sm text-ink-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-hidden /><span><b className="font-medium">{s.title}.</b> {s.explanation}</span></li>)}</ul></div>
        )}
      </Card>
      <Card>
        <SectionTitle title="Limitations" />
        <ul className="space-y-2 text-xs text-ink-2">{a.summary.limitations.map((l) => <li key={l} className="flex gap-2"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warn" aria-hidden />{l}</li>)}</ul>
        <p className="mt-3 text-[11px] text-ink-3">{a.summary.disclaimer}</p>
      </Card>
    </div>
  );
}

// ------------------------------------------------------------------ Checklist
export function Checklist({ app, a, docs, onUploadFor, onStateChange }: { app: Application; a: Assessment | null; docs: Doc[]; onUploadFor: (key: string, type?: string) => void; onStateChange: () => void }) {
  const [filter, setFilter] = useState("all");
  if (!a) return <Empty title="Your checklist is built by the assessment">Run your first assessment to generate a checklist personalised to your profile.</Empty>;
  const state = app.checklist_state ?? {};
  const items = a.checklist.filter((i) => filter === "all" || (filter === "outstanding" ? i.status !== "satisfied" : i.origin === filter));
  const docName = (id: string) => docs.find((d) => d.id === id)?.filename ?? "document";
  async function toggle(i: ChecklistItem, v: boolean) {
    await put(`/applications/${app.id}/checklist/${encodeURIComponent(i.item_key)}`, { collected: v });
    onStateChange();
  }
  function download() {
    const lines = a!.checklist.map((i) => `[${i.status === "satisfied" ? "x" : " "}] ${i.title} — ${i.level}${i.source_url ? ` — ${i.source_url}` : ""}\n    ${i.reason}`);
    const blob = new Blob([`VisaReady AI checklist — ${app.title}\nVersion ${a!.version}\n\n${lines.join("\n\n")}\n`], { type: "text/plain" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "visaready-checklist.txt";
    link.click();
  }
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {[["all", "All"], ["outstanding", "Outstanding"], ["requirement", "Official requirements"], ["evidence_rule", "Supporting evidence"]].map(([k, l]) => (
            <button key={k} onClick={() => setFilter(k)} className={cx("rounded-full px-3 py-1 text-sm", filter === k ? "bg-navy text-white" : "bg-surface text-ink-2 ring-1 ring-line")}>{l}</button>
          ))}
        </div>
        <Button variant="secondary" size="sm" onClick={download}><Download className="h-4 w-4" aria-hidden /> Download</Button>
      </div>
      <Alert tone="info">Only items from official government sources can be <b>mandatory</b>. Items marked “awaiting verification” were recorded from an official source but not yet re-checked by our team — always confirm using the source link.</Alert>
      {items.map((i) => (
        <Card key={i.item_key} className="p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-medium text-ink">{i.title}</p>
                <Badge tone={statusTone[i.status]}>{label(i.status)}</Badge>
              </div>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {i.classifications.map((c) => <Badge key={c} tone={c === "mandatory" ? "info" : c === "missing" ? "bad" : c.startsWith("requires") ? "warn" : "neutral"}>{label(c)}</Badge>)}
                <Badge tone="neutral">{i.origin === "requirement" ? "Official requirement" : "Evidence for your claims"}</Badge>
              </div>
              <p className="mt-2 text-sm text-ink-2"><span className="font-medium text-ink">Why it&apos;s here: </span>{i.reason}</p>
              {i.document_types.length > 0 && <p className="mt-1 text-xs text-ink-3">Accepted: {i.document_types.map(docTypeLabel).join(", ")}</p>}
              {(i.matched_document_ids.length > 0 || i.unconfirmed_document_ids.length > 0) && (
                <p className="mt-1 text-xs text-ink-3">
                  {i.matched_document_ids.map((d) => <span key={d} className="mr-2 inline-flex items-center gap-1 text-ok"><Check className="h-3 w-3" aria-hidden />{docName(d)}</span>)}
                  {i.unconfirmed_document_ids.map((d) => <span key={d} className="mr-2 inline-flex items-center gap-1 text-warn"><CircleDashed className="h-3 w-3" aria-hidden />{docName(d)} (not confirmed)</span>)}
                </p>
              )}
              {i.source_url && (
                <p className="mt-1.5 text-xs"><a href={i.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent">Official source <ExternalLink className="h-3 w-3" aria-hidden /></a>
                  <span className="ml-2 text-ink-3">{i.source_verified ? `verified ${fmtDate(i.last_verified_at)}` : "awaiting verification"}</span></p>
              )}
            </div>
            <div className="flex shrink-0 flex-col items-end gap-2">
              {i.document_types.length > 0 && <Button size="sm" variant="secondary" onClick={() => onUploadFor(i.item_key, i.document_types[0])}><Upload className="h-4 w-4" aria-hidden /> Upload</Button>}
              <label className="flex items-center gap-1.5 text-xs text-ink-2"><input type="checkbox" checked={!!state[i.item_key]?.collected} onChange={(e) => toggle(i, e.target.checked)} /> I have this</label>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ Documents
export function Documents({ app, docs, reload, preset, clearPreset }: { app: Application; docs: Doc[]; reload: () => void; preset: { key?: string; type?: string } | null; clearPreset: () => void }) {
  const type = preset?.type ?? "";
  const [, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Doc | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const replaceRef = useRef<HTMLInputElement>(null);
  const [replacing, setReplacing] = useState<string | null>(null);
  useEffect(() => {
    if (!docs.some((d) => ["uploaded", "processing"].includes(d.status))) return;
    const t = setTimeout(reload, 2000);
    return () => clearTimeout(t);
  }, [docs, reload]);

  async function send(file: File, replaces?: string) {
    setBusy(true);
    setError(null);
    const fd = new FormData();
    fd.append("file", file);
    if (type && !replaces) fd.append("declared_type", type);
    if (preset?.key && !replaces) fd.append("checklist_item_key", preset.key);
    if (replaces) fd.append("replaces_id", replaces);
    try {
      await upload(`/applications/${app.id}/documents`, fd);
      clearPreset();
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }
  async function showDetail(d: Doc) { setOpen(await api<Doc>(`/documents/${d.id}`)); }
  async function download(d: Doc) {
    const r = await post<{ url: string }>(`/documents/${d.id}/download-token`);
    window.location.href = r.url;
  }
  async function remove(d: Doc) {
    if (!confirm(`Permanently delete ${d.filename}? This cannot be undone.`)) return;
    await del(`/documents/${d.id}`);
    reload();
  }

  return (
    <div className="space-y-4">
      <Card>
        <SectionTitle title="Your documents" subtitle={`${docs.length}/${app.limits.max_documents} used · we work out what each document is`} />
        {error && <div className="mb-3"><Alert tone="bad">{error}</Alert></div>}
        <DropZone app={app} onUploaded={reload} compact />
      </Card>
      <input ref={replaceRef} type="file" accept="application/pdf,image/jpeg,image/png" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f && replacing) send(f, replacing); setReplacing(null); }} />
      {!docs.length ? <Empty title="No documents yet">Start with your passport, then the documents on your checklist.</Empty> : (
        <div className="overflow-hidden rounded-xl border border-line bg-surface">
          <ul className="divide-y divide-line">
            {docs.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <FileText className="h-5 w-5 shrink-0 text-ink-3" aria-hidden />
                <div className="min-w-0 flex-1">
                  <button onClick={() => showDetail(d)} className="truncate text-left text-sm font-medium text-ink hover:text-accent">{d.filename}</button>
                  <p className="text-xs text-ink-3">
                    {d.status === "processed" ? <>Detected: <b>{d.detected_type ? docTypeLabel(d.detected_type) : "unrecognised"}</b>{d.classification_confidence != null && ` (${Math.round(d.classification_confidence * 100)}% confidence)`} · {d.page_count} page(s)</> : label(d.status)}
                    {(d.quality.issues?.length ?? 0) > 0 && <span className="ml-2 text-warn">· {d.quality.issues!.length} quality note(s)</span>}
                    {(d.quality.non_latin_scripts?.length ?? 0) > 0 && <span className="ml-2 text-warn">· may need translation</span>}
                  </p>
                </div>
                <Badge tone={statusTone[d.status]}>{d.status}</Badge>
                <div className="flex gap-1">
                  <Button size="sm" variant="ghost" onClick={() => download(d)} aria-label="Download"><Download className="h-4 w-4" /></Button>
                  <Button size="sm" variant="ghost" onClick={() => { setReplacing(d.id); replaceRef.current?.click(); }}>Replace</Button>
                  <Button size="sm" variant="ghost" onClick={() => remove(d)} aria-label="Delete"><Trash2 className="h-4 w-4" /></Button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
      {open && (
        <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal aria-label="Document details">
          <div className="absolute inset-0 bg-black/30" onClick={() => setOpen(null)} />
          <div className="relative h-full w-full max-w-lg overflow-y-auto bg-surface p-6 shadow-xl">
            <div className="flex items-start justify-between gap-3"><h3 className="font-semibold text-ink">{open.filename}</h3><button onClick={() => setOpen(null)} aria-label="Close"><X className="h-5 w-5" /></button></div>
            <p className="mt-1 text-xs text-ink-3">{open.authenticity_note}</p>
            {(open.quality.issues ?? []).map((q) => <div key={q} className="mt-3"><Alert tone="warn">{q}</Alert></div>)}
            <h4 className="mt-5 text-sm font-semibold text-ink">Information we extracted</h4>
            {!open.fields?.length ? <p className="mt-2 text-sm text-ink-3">No structured fields were found.</p> : (
              <ul className="mt-2 divide-y divide-line text-sm">
                {open.fields.map((f, i) => (
                  <li key={i} className="py-2"><div className="flex justify-between gap-3"><span className="text-ink-3">{label(f.name)}</span><span className="text-right font-medium text-ink">{f.normalized ?? f.value}</span></div>
                    <p className="text-xs text-ink-3">Page {f.page ?? "?"} · {f.method === "mrz" ? "passport machine-readable zone" : f.method === "ai" ? "AI extraction" : "pattern match"} · {Math.round(f.confidence * 100)}%</p>
                    {f.snippet && <p className="mt-1 rounded bg-surface-2 px-2 py-1 font-mono text-[11px] text-ink-2">{f.snippet}</p>}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ Findings
function TriggerList({ f, docs }: { f: Finding; docs: Doc[] }) {
  return (
    <ul className="mt-2 space-y-1">
      {f.triggers.filter((t) => t.type !== "checklist").map((t, i) => (
        <li key={i} className="text-xs text-ink-3">
          {t.type === "document" ? <span><FileText className="mr-1 inline h-3 w-3" aria-hidden />{t.filename ?? docs.find((d) => d.id === t.document_id)?.filename}{t.page ? `, page ${t.page}` : ""}</span>
            : <span><Link2 className="mr-1 inline h-3 w-3" aria-hidden />Your profile: {t.path}{t.value ? ` = ${t.value}` : ""}</span>}
          {t.snippet && <span className="mt-0.5 block rounded bg-surface-2 px-2 py-1 font-mono text-[11px] text-ink-2">“{t.snippet}”</span>}
        </li>
      ))}
    </ul>
  );
}

export function FindingCard({ f, docs }: { f: Finding; docs: Doc[] }) {
  const c = CERTAINTY[f.certainty] ?? CERTAINTY.observation;
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={severityTone[f.severity]}>{f.severity}</Badge><Badge tone={c.tone}>{c.label}</Badge>
        <Badge tone="neutral">{f.category}</Badge><span className="text-xs text-ink-3">confidence: {f.confidence}</span>
      </div>
      <p className="mt-2 font-medium text-ink">{f.title}</p>
      <dl className="mt-2 space-y-1.5 text-sm">
        <div><dt className="inline font-medium text-ink">What: </dt><dd className="inline text-ink-2">{f.explanation}</dd></div>
        {f.why_it_matters && <div><dt className="inline font-medium text-ink">Why it matters: </dt><dd className="inline text-ink-2">{f.why_it_matters}</dd></div>}
        {f.suggested_action && <div><dt className="inline font-medium text-ink">What you can do: </dt><dd className="inline text-ink-2">{f.suggested_action}</dd></div>}
      </dl>
      {f.evidence_suggestions.length > 0 && <p className="mt-2 text-xs text-ink-3">Evidence that may help: {f.evidence_suggestions.join(" · ")}</p>}
      <TriggerList f={f} docs={docs} />
      {f.source_url && <a href={f.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-xs text-accent">Official source <ExternalLink className="h-3 w-3" aria-hidden /></a>}
    </Card>
  );
}

export function Findings({ a, docs }: { a: Assessment | null; docs: Doc[] }) {
  if (!a) return <Empty title="No assessment yet" />;
  const groups: [string, string, string[]][] = [
    ["Truth & consistency report", "Differences between your documents and your declarations.", ["inconsistency"]],
    ["Previous refusal analysis", "Reasons stated in earlier decisions and whether your evidence addresses them.", ["refusal_reason"]],
    ["Needs professional advice", "Matters that require the judgement of a qualified adviser.", ["professional_review"]],
    ["Missing evidence", "Evidence that is required or would substantiate your claims.", ["missing_evidence"]],
    ["Potential concerns", "Circumstances a decision-maker may want explained.", ["concern"]],
    ["Document quality", "Readability and completeness of uploaded files.", ["document_quality"]],
  ];
  return (
    <div className="space-y-8">
      {groups.map(([title, sub, kinds]) => {
        const list = a.findings.filter((f) => kinds.includes(f.kind));
        if (!list.length) return null;
        return <section key={title}><SectionTitle title={`${title} (${list.length})`} subtitle={sub} /><div className="space-y-3">{list.map((f) => <FindingCard key={f.id} f={f} docs={docs} />)}</div></section>;
      })}
    </div>
  );
}

// ------------------------------------------------------------------ Proof builder
const slotIcon = { present: <CheckCircle2 className="h-4 w-4 text-ok" aria-label="present" />, unconfirmed: <CircleDashed className="h-4 w-4 text-warn" aria-label="not confirmed" />, missing: <X className="h-4 w-4 text-bad" aria-label="missing" /> };

export function ProofBuilder({ a, docs }: { a: Assessment | null; docs: Doc[] }) {
  if (!a) return <Empty title="No assessment yet" />;
  const byCat = a.claims.reduce<Record<string, Claim[]>>((m, c) => ((m[c.category] ??= []).push(c), m), {});
  return (
    <div className="space-y-6">
      <Alert tone="info">Each claim you make (from your profile) is linked to the evidence that should support it. Green = recognised document, amber = uploaded but not confirmed, red = missing.</Alert>
      {Object.entries(byCat).map(([cat, claims]) => (
        <section key={cat}>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-3">{cat}</h3>
          <div className="space-y-3">
            {claims.map((c) => (
              <Card key={c.claim_key} className="p-4">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-[1fr_auto_1.2fr] md:items-center">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-ink-3">Claim</p>
                    <p className="mt-0.5 text-sm font-medium text-ink">{c.statement}</p>
                    <Badge tone={statusTone[c.status]} className="mt-2">{label(c.status)}</Badge>
                  </div>
                  <ArrowRight className="hidden h-5 w-5 text-ink-3 md:block" aria-hidden />
                  <ul className="space-y-1.5">
                    {c.evidence.map((s, i) => (
                      <li key={i} className="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-1.5 text-sm">
                        {slotIcon[s.state as keyof typeof slotIcon] ?? slotIcon.missing}
                        <span className="text-ink-2">{s.label}</span>
                        {!s.required && <span className="text-[11px] text-ink-3">(supporting)</span>}
                        {s.document_ids.length > 0 && <span className="ml-auto truncate text-[11px] text-ink-3">{s.document_ids.map((id) => docs.find((d) => d.id === id)?.filename).filter(Boolean).join(", ")}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
                <p className="mt-3 text-xs text-ink-3">{c.explanation}</p>
              </Card>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

export function Questions({ a }: { a: Assessment | null }) {
  if (!a) return <Empty title="No assessment yet" />;
  const qs = a.findings.filter((f) => f.kind === "question");
  return (
    <div className="space-y-4">
      <Alert tone="info" title="What questions could your application raise?">These are questions a decision-maker could reasonably want answered. It is a preparation exercise, not a prediction. Always answer truthfully, supported by genuine evidence.</Alert>
      {qs.map((q) => (
        <Card key={q.id} className="p-4">
          <p className="flex gap-2 font-medium text-ink"><HelpCircle className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden />{q.title}</p>
          <p className="mt-1 text-sm text-ink-2">{q.explanation}</p>
          {q.evidence_suggestions.length > 0 && <p className="mt-2 text-xs text-ink-3">Evidence that may help: {q.evidence_suggestions.join(" · ")}</p>}
        </Card>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ Strength simulator (diff)
export function DiffView({ diff }: { diff: Diff }) {
  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center gap-6">
        <div className="text-center"><p className="text-xs text-ink-3">v{diff.before.version}</p><p className="text-3xl font-semibold tabular-nums">{diff.before.score}</p></div>
        <ArrowRight className="h-6 w-6 text-ink-3" aria-hidden />
        <div className="text-center"><p className="text-xs text-ink-3">v{diff.after.version}</p><p className="text-3xl font-semibold tabular-nums">{diff.after.score}</p></div>
        <Badge tone={diff.score_delta > 0 ? "ok" : diff.score_delta < 0 ? "bad" : "neutral"} className="text-sm">{diff.score_delta > 0 ? "+" : ""}{diff.score_delta}</Badge>
        <p className="w-full text-xs text-ink-3 sm:w-auto sm:flex-1">{diff.note}</p>
      </Card>
      {diff.score_explanations.length > 0 && (
        <Card><SectionTitle title="Why the score changed" />
          <ul className="space-y-1.5 text-sm">{diff.score_explanations.map((e) => <li key={e.component}><b className={e.delta > 0 ? "text-ok" : "text-bad"}>{e.delta > 0 ? "+" : ""}{e.delta}</b> {e.component}: <span className="text-ink-2">{e.now}</span></li>)}</ul></Card>
      )}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {([["Issues resolved", diff.issues_resolved, "ok"], ["New issues", diff.new_issues, "bad"], ["Remaining", diff.remaining_issues, "warn"]] as const).map(([t, list, tone]) => (
          <Card key={t}><SectionTitle title={`${t} (${list.length})`} />
            <ul className="space-y-1.5 text-sm">{list.slice(0, 15).map((x) => <li key={x.fingerprint} className="flex gap-2"><Badge tone={tone}>{x.severity}</Badge><span className="text-ink-2">{x.title}</span></li>)}</ul></Card>
        ))}
      </div>
      {diff.checklist_changes.length > 0 && (
        <Card><SectionTitle title="Checklist changes" />
          <ul className="space-y-1.5 text-sm">{diff.checklist_changes.map((c) => <li key={c.item_key} className="text-ink-2">{c.title}: <span className="text-ink-3">{label(c.from)}</span> → <b>{label(c.to)}</b></li>)}</ul></Card>
      )}
    </div>
  );
}

export function Improvements({ appId }: { appId: string }) {
  const [versions, setVersions] = useState<{ id: string; version: number; readiness_score: number | null; created_at: string; status: string }[] | null>(null);
  const [pair, setPair] = useState<[string, string] | null>(null);
  const [diff, setDiff] = useState<Diff | null>(null);
  useEffect(() => {
    api<typeof versions>(`/applications/${appId}/assessments`).then((v) => {
      const done = (v ?? []).filter((x) => x.status === "completed");
      setVersions(done);
      if (done.length >= 2) setPair([done[1].id, done[0].id]);
    });
  }, [appId]);
  useEffect(() => { if (pair) api<Diff>(`/assessments/${pair[0]}/compare/${pair[1]}`).then(setDiff); }, [pair]);
  if (!versions) return <Spinner />;
  if (versions.length < 2) return <Empty title="Improve, then reassess">After you upload better evidence and run a reassessment, this page shows exactly what improved — and what didn&apos;t.</Empty>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        Compare
        <Select className="!w-auto" value={pair?.[0]} onChange={(e) => setPair([e.target.value, pair![1]])}>{versions.map((v) => <option key={v.id} value={v.id}>v{v.version} ({v.readiness_score})</option>)}</Select>
        with
        <Select className="!w-auto" value={pair?.[1]} onChange={(e) => setPair([pair![0], e.target.value])}>{versions.map((v) => <option key={v.id} value={v.id}>v{v.version} ({v.readiness_score})</option>)}</Select>
      </div>
      {diff ? <DiffView diff={diff} /> : <Spinner />}
    </div>
  );
}

// ------------------------------------------------------------------ What-if planner
export function WhatIf({ app, hasAssessment }: { app: Application; hasAssessment: boolean }) {
  const [s, setS] = useState({ funding_source: "", relationship: "", spouse: "", children: "", related: "", refusal: "", course_start: "" });
  const [res, setRes] = useState<{ simulation: Assessment; comparison?: Diff } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const student = app.visa_category.category_type === "student";
  async function run() {
    setBusy(true);
    setError(null);
    const body: Record<string, Record<string, unknown>> = { financial: {}, family: {}, details: {}, immigration: {} };
    if (s.funding_source) body.financial.funding_source = s.funding_source;
    if (s.relationship) body.financial.sponsor = { relationship: s.relationship, name: "Hypothetical sponsor", employment_type: "salaried" };
    if (s.spouse) body.family.accompanying_spouse = s.spouse === "yes";
    if (s.children) body.family.accompanying_children = Number(s.children);
    if (s.related) body.details.course_related_to_previous = s.related;
    if (s.course_start) body.details.course_start = s.course_start;
    if (s.refusal) body.immigration.has_previous_refusals = s.refusal === "yes";
    try {
      setRes(await post(`/applications/${app.id}/what-if`, body));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Simulation failed");
    } finally {
      setBusy(false);
    }
  }
  const sel = (k: keyof typeof s, opts: [string, string][]) => <Select value={s[k]} onChange={(e) => setS({ ...s, [k]: e.target.value })}><option value="">No change</option>{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select>;
  const baseKeys = new Set<string>();
  return (
    <div className="space-y-4">
      <Alert tone="info" title="What-If Application Planner">Explore how your requirements and evidence checklist would change. Simulations are not saved, are not your official report and do not use a reassessment.</Alert>
      {!hasAssessment && <Alert tone="warn">Run your first assessment to compare simulations with your current position.</Alert>}
      <Card className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="What if my funding source changes?">{sel("funding_source", [["self", "My own funds"], ["sponsor", "A sponsor"], ["mixed", "Both"]])}</Field>
        <Field label="What if my sponsor changes?">{sel("relationship", [["father", "Father"], ["mother", "Mother"], ["uncle", "Uncle"], ["sibling", "Sibling"], ["spouse", "Spouse"]])}</Field>
        <Field label="What if I include my spouse?">{sel("spouse", [["yes", "Include spouse"], ["no", "Don't include"]])}</Field>
        <Field label="What if children accompany me?">{sel("children", [["0", "None"], ["1", "1 child"], ["2", "2 children"], ["3", "3 children"]])}</Field>
        {student && <Field label="What if I change course relevance?">{sel("related", [["yes", "Related to my background"], ["partly", "Partly related"], ["no", "Unrelated"]])}</Field>}
        {student && <Field label="What if my course starts later?" hint="YYYY-MM — affects your study gap"><Input value={s.course_start} placeholder="2027-09" onChange={(e) => setS({ ...s, course_start: e.target.value })} /></Field>}
        <Field label="What if I had a previous refusal?">{sel("refusal", [["yes", "Yes"], ["no", "No"]])}</Field>
        <div className="flex items-end"><Button onClick={run} loading={busy}><Scale className="h-4 w-4" aria-hidden /> Simulate</Button></div>
      </Card>
      {error && <Alert tone="bad">{error}</Alert>}
      {res && (
        <div className="space-y-4">
          {res.comparison ? <DiffView diff={res.comparison} /> : <Card>Simulated readiness: <b>{res.simulation.readiness_score}</b></Card>}
          <Card><SectionTitle title="Simulated checklist" subtitle="How your checklist would look in this scenario" />
            <ul className="divide-y divide-line">{res.simulation.checklist.map((i) => { baseKeys.add(i.item_key); return <li key={i.item_key} className="flex items-center justify-between gap-3 py-2 text-sm"><span className="text-ink-2">{i.title}</span><Badge tone={statusTone[i.status]}>{label(i.status)}</Badge></li>; })}</ul>
          </Card>
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ Family map
export function FamilyMap({ app, a, reload }: { app: Application; a: Assessment | null; reload: () => void }) {
  const [f, setF] = useState({ relation: "spouse", full_name: "", date_of_birth: "" });
  const [error, setError] = useState<string | null>(null);
  async function add() {
    try {
      await post(`/applications/${app.id}/family-members`, { ...f, date_of_birth: f.date_of_birth || null });
      setF({ relation: "spouse", full_name: "", date_of_birth: "" });
      reload();
    } catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
  }
  const members = app.family_members ?? [];
  const claimFor = (id: string) => a?.claims.find((c) => c.claim_key === `family.${id}`);
  return (
    <div className="space-y-4">
      <Card>
        <SectionTitle title="Family application connection map" subtitle="Each family member's relationship evidence is assessed individually." />
        <div className="flex flex-col items-center gap-4">
          <div className="rounded-xl bg-navy px-5 py-3 text-center text-white"><p className="text-xs text-white/70">Principal applicant</p><p className="font-medium">You</p></div>
          {members.length > 0 && <div className="h-6 w-px bg-line" />}
          <div className="flex flex-wrap justify-center gap-4">
            {members.map((m) => {
              const c = claimFor(m.id);
              return (
                <div key={m.id} className="w-56 rounded-xl border border-line p-4 text-center">
                  <p className="text-xs uppercase text-ink-3">{m.relation}</p><p className="font-medium text-ink">{m.full_name}</p>
                  {c ? <Badge tone={statusTone[c.status]} className="mt-2">{label(c.status)}</Badge> : <p className="mt-2 text-xs text-ink-3">Reassess to evaluate</p>}
                  {c && <ul className="mt-2 space-y-1 text-left text-xs">{c.evidence.map((s, i) => <li key={i} className="flex items-center gap-1.5">{slotIcon[s.state as keyof typeof slotIcon] ?? slotIcon.missing}{s.label}</li>)}</ul>}
                  <button className="mt-3 text-xs text-bad" onClick={async () => { await del(`/applications/${app.id}/family-members/${m.id}`); reload(); }}>Remove</button>
                </div>
              );
            })}
          </div>
        </div>
      </Card>
      <Card className="grid grid-cols-1 gap-3 sm:grid-cols-4 sm:items-end">
        <Field label="Relationship"><Select value={f.relation} onChange={(e) => setF({ ...f, relation: e.target.value })}>{["spouse", "partner", "child", "parent", "other"].map((r) => <option key={r}>{r}</option>)}</Select></Field>
        <Field label="Full name"><Input value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
        <Field label="Date of birth"><Input type="date" value={f.date_of_birth} onChange={(e) => setF({ ...f, date_of_birth: e.target.value })} /></Field>
        <Button onClick={add} disabled={f.full_name.length < 2}>Add family member</Button>
        {error && <div className="sm:col-span-4"><Alert tone="bad">{error}</Alert></div>}
      </Card>
      <p className="flex items-center gap-2 text-xs text-ink-3"><ShieldAlert className="h-4 w-4" aria-hidden /> Shared evidence (for example, a bank statement used for the whole family) is matched to every member it supports.</p>
    </div>
  );
}

// ------------------------------------------------------------------ Submission file builder
type CaseEntry = { ref: string; title: string; status: string; status_label: string; basis: string; level: string; source_url: string | null;
  source_verified: boolean; documents: { id: string; filename: string; pages: number | null; needs_translation: boolean }[];
  unconfirmed_documents: { filename: string }[]; accepted_types: string[] };
type CaseFileData = {
  application: { title: string; country: string; visa: string }; assessment: { version: number };
  progress: { included: number; total: number }; status: string; status_label: string;
  sections: { code: string; title: string; entries: CaseEntry[] }[];
  before_lodging: { title: string; severity: string; action: string | null }[];
  explanations_to_prepare: { question: string; evidence: string[] }[]; translations_needed: string[]; notes: string[];
};

export function CaseFile({ a, unlocked, onBuyReport, onUploadFor }: { a: Assessment | null; unlocked: boolean; onBuyReport: () => void; onUploadFor: (key: string, type?: string) => void }) {
  const [f, setF] = useState<CaseFileData | null>(null);
  useEffect(() => { if (a) api<CaseFileData>(`/assessments/${a.id}/case-file`).then(setF).catch(() => {}); }, [a]);
  if (!a) return <Empty title="Run an assessment first">Your submission file is assembled from your latest assessment.</Empty>;
  if (!f) return <Spinner label="Assembling your submission file…" />;
  const pct = f.progress.total ? (f.progress.included / f.progress.total) * 100 : 0;
  const ready = f.status === "ready_for_final_review";
  return (
    <div className="space-y-5">
      <Card className="flex flex-wrap items-center gap-5">
        <div className="min-w-0 flex-1">
          <p className="text-xs uppercase tracking-wide text-ink-3">Submission file · {f.application.visa}</p>
          <p className="mt-1 text-lg font-semibold text-ink">{f.progress.included} of {f.progress.total} items in place</p>
          <div className="mt-2 max-w-md"><Progress value={pct} tone={ready ? "ok" : pct > 60 ? "warn" : "bad"} /></div>
        </div>
        <Badge tone={ready ? "ok" : "warn"} className="text-sm">{f.status_label}</Badge>
        {unlocked
          ? <a href={`/api/assessments/${a.id}/case-file/print`} target="_blank" rel="noreferrer"
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-navy px-4 text-sm font-medium text-white hover:bg-navy-2"><Download className="h-4 w-4" aria-hidden /> Print / save as PDF</a>
          : <Button onClick={onBuyReport}><Lock className="h-4 w-4" aria-hidden /> Unlock printable file</Button>}
      </Card>

      {(f.before_lodging.length > 0 || f.translations_needed.length > 0) && (
        <Card className="border-bad/30">
          <SectionTitle title="Resolve before lodging" subtitle="An experienced case officer would expect these to be fixed or explained first." />
          <ul className="space-y-2 text-sm">
            {f.before_lodging.map((b, i) => <li key={i} className="flex gap-2"><Badge tone={severityTone[b.severity]}>{b.severity}</Badge><span><b className="text-ink">{b.title}.</b> <span className="text-ink-2">{b.action}</span></span></li>)}
            {f.translations_needed.map((t) => <li key={t} className="flex gap-2"><Badge tone="warn">translation</Badge><span className="text-ink-2">Certified English translation needed for <b>{t}</b></span></li>)}
          </ul>
        </Card>
      )}

      {f.sections.map((sec) => (
        <Card key={sec.code} className="p-0">
          <div className="flex items-center gap-3 border-b border-line px-5 py-3">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-navy text-sm font-semibold text-white">{sec.code}</span>
            <h3 className="font-semibold text-ink">{sec.title}</h3>
            <span className="ml-auto text-xs text-ink-3">{sec.entries.filter((e) => e.status === "satisfied").length}/{sec.entries.length}</span>
          </div>
          <ul className="divide-y divide-line">
            {sec.entries.map((e) => (
              <li key={e.ref} className="grid grid-cols-1 gap-2 px-5 py-3 sm:grid-cols-[3rem_1fr_auto] sm:items-start">
                <span className="font-mono text-sm font-semibold text-ink-2">{e.ref}</span>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-ink">{e.title}</p>
                  <p className="text-xs text-ink-3">{e.basis}{e.level === "mandatory" ? " · mandatory" : ""}
                    {e.source_url && <> · <a href={e.source_url} target="_blank" rel="noreferrer" className="text-accent">source</a>{!e.source_verified && " (awaiting verification)"}</>}</p>
                  {e.documents.map((d) => <p key={d.id} className="mt-1 flex items-center gap-1.5 text-xs text-ok"><FileText className="h-3.5 w-3.5" aria-hidden />{d.filename}{d.pages ? ` · ${d.pages} page(s)` : ""}{d.needs_translation && <span className="text-warn"> · needs translation</span>}</p>)}
                  {e.unconfirmed_documents.map((d) => <p key={d.filename} className="mt-1 text-xs text-warn">{d.filename} — uploaded but not confirmed as the right document</p>)}
                  {e.status === "missing" && e.accepted_types.length > 0 && <p className="mt-1 text-xs text-ink-3">Accepted: {e.accepted_types.join(", ")}</p>}
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={e.status === "satisfied" ? "ok" : e.status === "missing" ? "bad" : "warn"}>{e.status_label}</Badge>
                  {e.status === "missing" && <Button size="sm" variant="secondary" onClick={() => onUploadFor("", undefined)}><Upload className="h-3.5 w-3.5" aria-hidden /> Add</Button>}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      ))}

      {f.explanations_to_prepare.length > 0 && (
        <Card><SectionTitle title="Explanations to prepare" subtitle="Include truthful answers, supported by evidence, in your cover letter or statement." />
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">{f.explanations_to_prepare.map((x) => <li key={x.question}>{x.question}</li>)}</ul></Card>
      )}
      <ul className="space-y-1 text-xs text-ink-3">{f.notes.map((n) => <li key={n}>• {n}</li>)}</ul>
    </div>
  );
}


// ------------------------------------------------------------------ Suggested drafts (part of the paid report)
type Draft = { key: string; title: string; service_code: string; text?: string };

export function Drafts({ a, onBuyReport, reportPrice }: { a: Assessment | null; onBuyReport: () => void; reportPrice: string }) {
  const [d, setD] = useState<{ unlocked: boolean; drafts: Draft[] } | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  useEffect(() => { if (a) api<{ unlocked: boolean; drafts: Draft[] }>(`/assessments/${a.id}/drafts`).then(setD).catch(() => {}); }, [a]);
  if (!a) return <Empty title="Run an assessment first">Drafts are tailored to the findings of your assessment.</Empty>;
  if (!d) return <Spinner label="Preparing your drafts…" />;
  return (
    <div className="space-y-4">
      <Alert tone="info" title="Suggested drafts tailored to your file">
        Each draft uses only the information you gave us. Replace every [bracketed] prompt with accurate details and check every statement is true.
      </Alert>
      {!d.unlocked && (
        <Card className="flex flex-wrap items-center gap-4 border-accent/40">
          <div className="min-w-0 flex-1">
            <p className="font-semibold text-ink">{d.drafts.length} drafts are ready for your file</p>
            <p className="text-sm text-ink-2">Unlock them with your full assessment report ({reportPrice}).</p>
          </div>
          <Button onClick={onBuyReport}><Lock className="h-4 w-4" aria-hidden /> Unlock drafts</Button>
        </Card>
      )}
      {d.drafts.map((x) => (
        <Card key={x.key}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-semibold text-ink">{x.title}</h3>
            <div className="flex gap-2">
              {x.text && <Button size="sm" variant="secondary" onClick={() => { navigator.clipboard?.writeText(x.text!); setCopied(x.key); }}><Copy className="h-4 w-4" aria-hidden /> {copied === x.key ? "Copied" : "Copy"}</Button>}
              <a href="/services" className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-navy px-3 text-sm text-white hover:bg-navy-2"><PenLine className="h-4 w-4" aria-hidden /> Have us write it</a>
            </div>
          </div>
          {x.text
            ? <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-surface-2 p-4 font-sans text-sm leading-relaxed text-ink-2">{x.text}</pre>
            : <div className="mt-3 rounded-lg bg-surface-2 p-4 text-sm text-ink-3 blur-[1px] select-none" aria-hidden>To the Visa Officer, Re: … [locked — unlock the full report to view this draft]</div>}
        </Card>
      ))}
    </div>
  );
}
