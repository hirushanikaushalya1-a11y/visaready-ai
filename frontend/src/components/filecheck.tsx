"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  AlertOctagon, AlertTriangle, ArrowRight, CheckCircle2, FileSearch, FileText, Gavel, Info, Loader2, PenLine,
  ShieldCheck, Sparkles, Trash2, Upload, XCircle,
} from "lucide-react";
import { api, del, put } from "@/lib/api";
import type { AiReview, Application, Assessment, Doc } from "@/lib/types";
import { DropZone } from "./quickcheck";
import { Badge, Button, Card, cx } from "./ui";

type Flag = { title: string; severity: "high" | "medium" | "low"; explanation: string; fix: string; documents: string[]; kind: "document" | "profile" | "other" };
const PROFILE_FLAGS = ["funding_unknown", "refusal_question_unanswered", "sponsor_details_missing"];
type Verdict = { label: string; tone: "ok" | "accent" | "warn" | "bad"; note: string };

const LETTER_HINT = /deposit|fund|source|gap|explain|sponsor|career|refus|relationship|consent|cover letter|statement of purpose|sop/i;
const COLORS = { ok: "var(--ok)", accent: "var(--accent)", warn: "var(--warn)", bad: "var(--bad)" };

function verdictFor(score: number | null, highs: number): Verdict {
  if (score == null) return { label: "Not checked yet", tone: "accent", note: "Drop your documents to start." };
  if (score >= 85 && highs === 0) return { label: "Ready to submit", tone: "ok", note: "Your file is well prepared. Do a final check against the official requirements." };
  if (score >= 65 && highs <= 1) return { label: "Nearly ready", tone: "accent", note: "A few items need fixing before you submit." };
  if (score >= 40) return { label: "Needs work", tone: "warn", note: "Important problems need fixing before you submit." };
  return { label: "Not ready", tone: "bad", note: "Do not submit yet — serious gaps need fixing first." };
}

function flagsFrom(a: Assessment | null): Flag[] {
  if (!a) return [];
  const review = a.summary.ai_review;
  if (review) {
    return review.problems.map((p) => ({ title: p.title, severity: p.severity, explanation: p.explanation, fix: p.how_to_fix, documents: p.documents, kind: "document" as const }));
  }
  const kinds = ["inconsistency", "professional_review", "refusal_reason", "missing_evidence", "concern"];
  return a.findings
    .filter((f) => kinds.includes(f.kind) && f.severity !== "info")
    .map((f) => {
      const profile = PROFILE_FLAGS.includes(f.fingerprint);
      return {
        title: f.title, severity: f.severity as Flag["severity"], explanation: f.explanation,
        fix: profile ? "Answer the quick question below — one click." : f.suggested_action ?? "",
        documents: f.triggers.filter((t) => t.type === "document" && t.filename).map((t) => t.filename as string),
        kind: profile ? "profile" as const : f.kind === "missing_evidence" || f.kind === "inconsistency" || f.kind === "document_quality" ? "document" as const : "other" as const,
      };
    })
    .sort((x, y) => ["high", "medium", "low"].indexOf(x.severity) - ["high", "medium", "low"].indexOf(y.severity));
}

function Gauge({ value, tone }: { value: number | null; tone: Verdict["tone"] }) {
  const [shown, setShown] = useState(0);
  useEffect(() => { const t = setTimeout(() => setShown(value ?? 0), 80); return () => clearTimeout(t); }, [value]);
  const r = 64, c = 2 * Math.PI * r;
  return (
    <div className="relative mx-auto h-44 w-44">
      <svg viewBox="0 0 160 160" className="h-full w-full -rotate-90" aria-hidden>
        <circle cx="80" cy="80" r={r} fill="none" stroke="var(--surface-2)" strokeWidth="14" />
        <circle cx="80" cy="80" r={r} fill="none" stroke={COLORS[tone]} strokeWidth="14" strokeLinecap="round"
          strokeDasharray={`${(shown / 100) * c} ${c}`} style={{ transition: "stroke-dasharray 1.2s ease-out" }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-5xl font-semibold tabular-nums text-ink">{value == null ? "—" : `${value}%`}</span>
        <span className="mt-1 text-[11px] font-medium uppercase tracking-wider text-ink-3">File readiness</span>
      </div>
    </div>
  );
}

function DocCard({ d, review, onDelete }: { d: Doc; review?: AiReview; onDelete: () => void }) {
  const ai = review?.documents.find((x) => x.filename === d.filename);
  const reading = ["uploaded", "processing"].includes(d.status);
  const failed = d.status === "failed" || (ai && !ai.readable);
  const concern = ai?.concerns[0];
  // Before the full check, nothing is shown as a warning: the card simply confirms the file arrived.
  // Problems are reported once, clearly, in the file check below — not as alarming labels on every card.
  const state = reading ? "reading" : failed ? "bad" : !ai ? "received" : concern ? "warn" : "ok";
  const title = ai?.what_it_is ?? d.detected_type_label ?? (reading ? "Reading…" : "Document received");
  const style = { reading: "border-accent/40", received: "border-line", ok: "border-ok/30", warn: "border-warn/40", bad: "border-bad/40" }[state];
  return (
    <div className={cx("group relative flex min-w-0 flex-col rounded-xl border bg-surface p-4 shadow-sm transition", style)}>
      <div className="flex items-start gap-3">
        <span className={cx("flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
          { reading: "bg-accent-soft text-accent", received: "bg-ok-soft text-ok", ok: "bg-ok-soft text-ok", warn: "bg-warn-soft text-warn", bad: "bg-bad-soft text-bad" }[state])}>
          {state === "reading" ? <Loader2 className="h-5 w-5 animate-spin" aria-hidden /> : state === "ok" || state === "received" ? <CheckCircle2 className="h-5 w-5" aria-hidden />
            : state === "warn" ? <AlertTriangle className="h-5 w-5" aria-hidden /> : <XCircle className="h-5 w-5" aria-hidden />}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-ink" title={title}>{title}</p>
          <p className="truncate text-xs text-ink-3" title={d.filename}>{d.filename}</p>
        </div>
        <button onClick={onDelete} className="rounded p-1 text-ink-3 opacity-60 hover:bg-surface-2 hover:text-bad hover:opacity-100" aria-label={`Remove ${d.filename}`}><Trash2 className="h-4 w-4" /></button>
      </div>
      <p className={cx("mt-3 text-xs leading-relaxed", state === "warn" ? "text-warn" : state === "bad" ? "text-bad" : "text-ink-2")}>
        {state === "reading" ? "Received safely. Reading the pages…"
          : state === "bad" ? "We could not read this file. Upload a clearer, complete scan."
          : state === "received" ? `Received${d.quality.pages ? ` · ${d.quality.pages} ${d.quality.pages === 1 ? "page" : "pages"}` : ""}. Checked in full in your file check.`
          : concern ? concern
          : ai?.key_facts[0] ?? "Read successfully."}
      </p>
    </div>
  );
}

function QuickQuestions({ onChanged }: { onChanged: () => void }) {
  type P = { financial: Record<string, unknown>; immigration_history: Record<string, unknown> };
  const [p, setP] = useState<P | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => { api<P>("/profile").then(setP).catch(() => {}); }, []);
  if (!p) return null;
  const funding = (p.financial?.funding_source as string) ?? "";
  const rel = ((p.financial?.sponsor as Record<string, unknown>)?.relationship as string) ?? "";
  const refused = p.immigration_history?.has_previous_refusals as boolean | undefined;
  async function save(section: "financial" | "immigration_history", patch: Record<string, unknown>) {
    const next = { ...p!, [section]: { ...(p![section] ?? {}), ...patch } };
    setP(next);
    await put("/profile", { [section]: next[section] }).catch(() => {});
    setSaved(true);
    onChanged();
  }
  const chip = (active: boolean, label: string, onClick: () => void) => (
    <button key={label} onClick={onClick} className={cx("rounded-full px-4 py-2 text-sm font-medium transition",
      active ? "bg-navy text-white" : "bg-surface-2 text-ink-2 hover:bg-accent-soft hover:text-ink")}>{label}</button>
  );
  const fundingChoice = funding === "sponsor" && ["father", "mother", "parent"].includes(rel) ? "parents" : funding === "sponsor" ? "sponsor" : funding;
  return (
    <Card className="space-y-4">
      <div><h3 className="font-semibold text-ink">Two quick questions</h3><p className="text-sm text-ink-3">One click each — it makes the check more precise.</p></div>
      <div>
        <p className="mb-2 text-sm font-medium text-ink">Who is paying for this?</p>
        <div className="flex flex-wrap gap-2">
          {chip(fundingChoice === "self", "Me", () => save("financial", { funding_source: "self" }))}
          {chip(fundingChoice === "parents", "My parents", () => save("financial", { funding_source: "sponsor", sponsor: { ...((p.financial?.sponsor as object) ?? {}), relationship: "parent" } }))}
          {chip(fundingChoice === "sponsor", "Another sponsor", () => save("financial", { funding_source: "sponsor", sponsor: { ...((p.financial?.sponsor as object) ?? {}), relationship: "relative" } }))}
          {chip(fundingChoice === "scholarship", "Scholarship", () => save("financial", { funding_source: "scholarship" }))}
          {chip(fundingChoice === "employer", "My employer", () => save("financial", { funding_source: "employer" }))}
        </div>
      </div>
      <div>
        <p className="mb-2 text-sm font-medium text-ink">Have you ever been refused a visa for any country?</p>
        <div className="flex flex-wrap gap-2">
          {chip(refused === false, "No, never", () => save("immigration_history", { has_previous_refusals: false }))}
          {chip(refused === true, "Yes", () => save("immigration_history", { has_previous_refusals: true }))}
        </div>
        {refused === true && <p className="mt-2 text-xs text-ink-3">Please include the refusal letter with your documents — it must be declared, and we will check how your file addresses it.</p>}
      </div>
      {saved && <p className="text-xs text-ok">Saved. Press “Check my file again” to update your result.</p>}
    </Card>
  );
}

export function FileCheckDashboard({ app, docs, a, reloadDocs, onCheck, checking, onBatchDone }: {
  app: Application; docs: Doc[]; a: Assessment | null; reloadDocs: () => void; onCheck: () => void; checking: boolean; onBatchDone: () => void;
}) {
  const review = a?.summary.ai_review;
  const flags = flagsFrom(a);
  const count = (s: Flag["severity"]) => flags.filter((f) => f.severity === s).length;
  const verdict = verdictFor(a?.readiness_score ?? null, count("high"));
  const reading = docs.filter((d) => ["uploaded", "processing"].includes(d.status)).length;
  const ifNow: string[] = review?.if_submitted_now?.length ? review.if_submitted_now
    : [...flags.filter((f) => f.severity === "high" && f.kind !== "profile").slice(0, 3).map((f) => `A visa officer would notice: ${f.title.replace(/^Missing: /, "missing ")}. This alone could lead to questions or a refusal.`),
       ...flags.filter((f) => f.severity === "medium" && f.kind !== "profile").slice(0, 2).map((f) => `The officer would likely ask about: ${f.title.replace(/^Missing: /, "missing ")}.`)];
  const stepDone = [docs.length > 0, docs.length > 0 && reading === 0, !!a];

  return (
    <div className="space-y-6">
      {/* Header with progress steps */}
      <div className="overflow-hidden rounded-2xl bg-navy text-white shadow-lg">
        <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-white/60"><ShieldCheck className="h-4 w-4" aria-hidden /> Visa file check</p>
            <h2 className="mt-1 text-xl font-semibold">{app.visa_category.name} · {app.country_name}</h2>
          </div>
          <Button variant="accent" size="lg" onClick={onCheck} loading={checking} disabled={!docs.length || app.reassessments.remaining <= 0}>
            <Sparkles className="h-5 w-5" aria-hidden /> {checking ? (reading ? "Reading documents…" : "Checking your file…") : a ? "Check my file again" : "Check my file"}
          </Button>
        </div>
        <ol className="grid grid-cols-3 border-t border-white/10 text-xs sm:text-sm">
          {["Drop your documents", "We read every page", "Your file report"].map((s, i) => (
            <li key={s} className={cx("flex items-center gap-2 px-4 py-3", i > 0 && "border-l border-white/10", stepDone[i] ? "text-white" : "text-white/50")}>
              <span className={cx("flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold", stepDone[i] ? "bg-accent text-white" : "bg-white/10")}>
                {stepDone[i] ? "✓" : i + 1}</span>
              <span className="truncate">{s}</span>
            </li>
          ))}
        </ol>
      </div>

      {/* Drop zone + documents */}
      <div id="drop" className="scroll-mt-24">
        <DropZone app={app} onUploaded={reloadDocs} compact={docs.length > 0} onBatchDone={onBatchDone} />
      </div>
      {docs.length > 0 && (
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-semibold text-ink">Your documents ({docs.length})</h3>
            {reading > 0 && <span className="flex items-center gap-2 text-sm text-accent"><Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Reading {reading}…</span>}
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {docs.map((d) => <DocCard key={d.id} d={d} review={review} onDelete={async () => { if (confirm(`Remove ${d.filename}?`)) { await del(`/documents/${d.id}`); reloadDocs(); } }} />)}
          </div>
        </section>
      )}

      {checking && !a && (
        <Card className="flex items-center gap-4"><Loader2 className="h-6 w-6 animate-spin text-accent" aria-hidden />
          <div><p className="font-medium text-ink">Your file is being checked</p><p className="text-sm text-ink-3">Every document is read word for word and compared with the others and with the visa requirements. This usually takes under a minute.</p></div></Card>
      )}

      {a && (
        <>
          {/* Result headline */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
            <Card className="flex flex-col items-center justify-center gap-3 text-center lg:col-span-2">
              <Gauge value={a.readiness_score} tone={verdict.tone} />
              <Badge tone={verdict.tone === "accent" ? "info" : verdict.tone} className="px-4 py-1.5 text-sm">{verdict.label}</Badge>
              <p className="max-w-xs text-sm text-ink-2">{review?.headline ?? verdict.note}</p>
              <p className="max-w-xs text-[11px] text-ink-3">Readiness shows how complete and consistent your file is. It is not a prediction of the visa decision — only the immigration authority decides.</p>
            </Card>
            <Card className="space-y-4 lg:col-span-3">
              <div className="flex items-center gap-2"><Gavel className="h-5 w-5 text-navy-2" aria-hidden /><h3 className="font-semibold text-ink">If you submitted this file today</h3></div>
              {ifNow.length ? (
                <ul className="space-y-2.5">{ifNow.map((x, i) => <li key={i} className="flex gap-2.5 text-sm text-ink-2"><AlertOctagon className="mt-0.5 h-4 w-4 shrink-0 text-bad" aria-hidden />{x}</li>)}</ul>
              ) : <p className="flex gap-2 text-sm text-ink-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-hidden />No serious problems were found in the documents provided. An officer will still check every document against the official requirements.</p>}
              <div className="grid grid-cols-3 gap-2 pt-1">
                {([["high", "Serious", "bg-bad-soft text-bad"], ["medium", "Needs attention", "bg-warn-soft text-warn"], ["low", "Minor", "bg-info-soft text-info"]] as const).map(([s, l, c]) => (
                  <div key={s} className={cx("rounded-xl px-3 py-3 text-center", c)}><p className="text-2xl font-semibold tabular-nums">{count(s)}</p><p className="text-xs font-medium">{l}</p></div>
                ))}
              </div>
              {review?.summary && <p className="border-t border-line pt-3 text-sm leading-relaxed text-ink-2">{review.summary}</p>}
            </Card>
          </div>

          <div id="quick" className="scroll-mt-24"><QuickQuestions onChanged={() => {}} /></div>

          {/* Red flags with fixes */}
          {flags.length > 0 && (
            <Card className="space-y-3">
              <div className="flex items-center gap-2"><FileSearch className="h-5 w-5 text-bad" aria-hidden /><h3 className="font-semibold text-ink">Red flags and how to fix them</h3></div>
              <ol className="space-y-3">
                {flags.slice(0, 12).map((f, i) => (
                  <li key={i} className={cx("rounded-xl border-l-4 bg-surface-2 p-4", f.severity === "high" ? "border-bad" : f.severity === "medium" ? "border-warn" : "border-info")}>
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <p className="font-medium text-ink">{i + 1}. {f.title}</p>
                      <Badge tone={f.severity === "high" ? "bad" : f.severity === "medium" ? "warn" : "info"}>{f.severity === "high" ? "Serious" : f.severity === "medium" ? "Needs attention" : "Minor"}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-ink-2">{f.explanation}</p>
                    {f.fix && <p className="mt-2 flex gap-2 text-sm text-ink"><ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden /><span><b>How to fix:</b> {f.fix}</span></p>}
                    <div className="mt-3 flex flex-wrap gap-2">
                      {f.kind === "profile" && <a href="#quick" className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-accent px-3 text-xs font-medium text-white hover:opacity-90"><Sparkles className="h-3.5 w-3.5" aria-hidden /> Answer in one click</a>}
                      {f.kind !== "profile" && <a href="#drop" className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-line bg-surface px-3 text-xs font-medium text-ink hover:bg-surface-2"><Upload className="h-3.5 w-3.5" aria-hidden /> Upload document</a>}
                      {f.kind !== "profile" && LETTER_HINT.test(`${f.title} ${f.fix}`) && <Link href="/services" className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-navy px-3 text-xs font-medium text-white hover:bg-navy-2"><PenLine className="h-3.5 w-3.5" aria-hidden /> Have us write the letter — €10</Link>}
                    </div>
                  </li>
                ))}
              </ol>
            </Card>
          )}

          {review && (review.missing_documents.length > 0 || review.strengths.length > 0) && (
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              {review.missing_documents.length > 0 && (
                <Card><h3 className="mb-3 font-semibold text-ink">Documents still needed</h3>
                  <ul className="space-y-2 text-sm">{review.missing_documents.map((m, i) => <li key={i} className="flex gap-2"><FileText className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden /><span><b className="text-ink">{m.document}</b><span className="block text-ink-3">{m.why_needed}</span></span></li>)}</ul></Card>
              )}
              {review.strengths.length > 0 && (
                <Card><h3 className="mb-3 font-semibold text-ink">What is already strong</h3>
                  <ul className="space-y-2 text-sm">{review.strengths.map((x, i) => <li key={i} className="flex gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-hidden /><span className="text-ink-2">{x}</span></li>)}</ul></Card>
              )}
            </div>
          )}
          {review?.next_steps?.length ? (
            <Card><h3 className="mb-3 font-semibold text-ink">Your plan for this week</h3>
              <ol className="space-y-2">{review.next_steps.map((x, i) => <li key={i} className="flex gap-3 text-sm text-ink-2"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent">{i + 1}</span>{x}</li>)}</ol></Card>
          ) : null}
          {review?.professional_advice_recommended && (
            <Card className="flex gap-3 border-info/40 bg-info-soft/40"><Info className="mt-0.5 h-5 w-5 shrink-0 text-info" aria-hidden />
              <p className="text-sm text-ink-2">Parts of your situation need professional judgement. We recommend speaking to a qualified, licensed immigration adviser before you submit.</p></Card>
          )}
          {a.summary.ai_review_error && !review && <p className="text-xs text-ink-3">{a.summary.ai_review_error}</p>}
        </>
      )}

      {!a && docs.length > 0 && <div id="quick" className="scroll-mt-24"><QuickQuestions onChanged={() => {}} /></div>}
    </div>
  );
}
