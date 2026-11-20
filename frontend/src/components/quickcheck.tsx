"use client";

import { useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, FileText, Loader2, Sparkles, UploadCloud } from "lucide-react";
import { ApiError, upload } from "@/lib/api";
import type { AiReview, Application, Doc } from "@/lib/types";
import { Alert, Badge, Button, Card, cx, SectionTitle, severityTone } from "./ui";

const ACCEPT = ["application/pdf", "image/jpeg", "image/png"];
type Item = { key: string; name: string; state: "waiting" | "sending" | "done" | "error"; problem?: string; file?: File };

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const BIG = 10 * 1024 * 1024;

/** Uploads one file. Busy server, restart or a dropped connection: waits and tries again quietly. */
async function uploadQuietly(appId: string, f: File) {
  for (let attempt = 1; ; attempt++) {
    const fd = new FormData();
    fd.append("file", f);
    try {
      return await upload(`/applications/${appId}/documents`, fd);
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0; // 0 = connection dropped / server restarting
      const transient = status === 0 || status === 429 || status >= 500;
      if (!transient || attempt >= 6) throw e;
      await sleep(Math.min(30_000, 5_000 * attempt)); // about 75 seconds of patience in total
    }
  }
}

/** One plain-language sentence for anything that still fails after retrying. */
function plainProblem(f: File, e?: unknown): string {
  if (/\.(docx?|odt|pages)$/i.test(f.name)) return "This is a Word file — open it and choose Save as PDF, then add it again.";
  if (/\.(heic|heif)$/i.test(f.name)) return "This is an iPhone photo format — take a screenshot of it or export it as JPG, then add it again.";
  if (e instanceof ApiError && e.status === 413) return "This file is too large. Scan it at a lower quality or split it into two files.";
  if (e instanceof ApiError && e.status < 500 && e.status !== 429) return e.message;
  return "The connection dropped. Press Send again.";
}

/** Big drag-and-drop area. Drop everything at once — no types to choose, no forms, no error lists. */
export function DropZone({ app, onUploaded, compact = false, onBatchDone }: { app: Application; onUploaded: () => void; compact?: boolean; onBatchDone?: () => void }) {
  const [over, setOver] = useState(false);
  const [items, setItems] = useState<Item[]>([]);
  const input = useRef<HTMLInputElement>(null);
  const maxBytes = app.limits.max_file_size_mb * 1024 * 1024;

  async function run(batch: Item[]) {
    const set = (key: string, patch: Partial<Item>) => setItems((cur) => cur.map((x) => (x.key === key ? { ...x, ...patch } : x)));
    let next = 0;
    let bigLock: Promise<unknown> = Promise.resolve();
    async function worker() {
      while (next < batch.length) {
        const it = batch[next++];
        const f = it.file!;
        if (!ACCEPT.includes(f.type) && !/\.(pdf|jpe?g|png)$/i.test(f.name)) { set(it.key, { state: "error", problem: plainProblem(f), file: undefined }); continue; }
        if (f.size > maxBytes) { set(it.key, { state: "error", problem: plainProblem(f, new ApiError(413, "")), file: undefined }); continue; }
        set(it.key, { state: "sending" });
        try {
          if (f.size > BIG) {
            // Large scans go one at a time so the server never runs short of memory.
            const prev = bigLock;
            let release!: () => void;
            bigLock = new Promise<void>((r) => (release = r));
            await prev;
            try { await uploadQuietly(app.id, f); } finally { release(); }
          } else {
            await uploadQuietly(app.id, f);
          }
          set(it.key, { state: "done", file: undefined, problem: undefined });
          onUploaded();
        } catch (e) { set(it.key, { state: "error", problem: plainProblem(f, e) }); }
      }
    }
    await Promise.all([worker(), worker()]);
    onUploaded();
    onBatchDone?.();
  }

  function handle(files: FileList | File[]) {
    const list = Array.from(files);
    const fresh: Item[] = list.map((f, i) => ({ key: `${Date.now()}-${i}-${f.name}`, name: f.name, state: "waiting", file: f }));
    setItems((cur) => [...cur.filter((x) => x.state !== "done"), ...fresh]);
    void run(fresh);
  }

  const busy = items.some((x) => x.state === "waiting" || x.state === "sending");
  const done = items.filter((x) => x.state === "done").length;
  const failed = items.filter((x) => x.state === "error");
  const retryable = failed.filter((x) => x.file);
  const pct = items.length ? Math.round(((done + failed.length) / items.length) * 100) : 0;

  function sendAgain() {
    const batch = retryable.map((x) => ({ ...x, state: "waiting" as const, problem: undefined }));
    setItems((cur) => cur.map((x) => batch.find((b) => b.key === x.key) ?? x));
    void run(batch);
  }

  return (
    <div>
      <div
        role="button" tabIndex={0} aria-label="Add documents: drop them here or press to choose files"
        onClick={() => input.current?.click()}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") input.current?.click(); }}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); if (e.dataTransfer.files.length) handle(e.dataTransfer.files); }}
        className={cx("flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed text-center transition",
          compact ? "px-4 py-6" : "px-6 py-12",
          over ? "border-accent bg-accent-soft/60" : "border-line bg-surface-2/50 hover:border-accent/60 hover:bg-accent-soft/30")}>
        <UploadCloud className={cx("text-accent", compact ? "h-8 w-8" : "h-12 w-12")} aria-hidden />
        <p className={cx("mt-3 font-semibold text-ink", compact ? "text-base" : "text-lg")}>{compact ? "Add more documents" : "Drop all your documents here"}</p>
        <p className="mt-1 max-w-md text-sm text-ink-3">Select everything at once — passport, certificates, bank papers, letters. On a phone, tap here and pick photos or files. We work out what each one is.</p>
        <span className="mt-4 inline-flex items-center rounded-full bg-navy px-5 py-2.5 text-sm font-semibold text-white">Choose files</span>
        <p className="mt-3 text-xs text-ink-3">PDF or photos (JPG, PNG) · up to {app.limits.max_file_size_mb} MB each · private and encrypted</p>
        <input ref={input} type="file" multiple accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" className="hidden"
          onChange={(e) => { if (e.target.files?.length) handle(e.target.files); e.target.value = ""; }} />
      </div>

      {items.length > 0 && (
        <div className="mt-3 rounded-xl border border-line bg-surface p-4" aria-live="polite">
          {busy ? (
            <>
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="flex items-center gap-2 font-medium text-ink"><Loader2 className="h-4 w-4 animate-spin text-accent" aria-hidden />Sending your documents… {done} of {items.length}</span>
                <span className="text-ink-3">Please keep this page open</span>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-2"><div className="h-full rounded-full bg-accent transition-all duration-500" style={{ width: `${pct}%` }} /></div>
            </>
          ) : (
            <p className="flex items-center gap-2 text-sm font-medium text-ink">
              <CheckCircle2 className="h-5 w-5 text-ok" aria-hidden />
              {done} {done === 1 ? "document" : "documents"} received safely{failed.length === 0 ? ". We are reading them now." : "."}
            </p>
          )}
          {!busy && failed.length > 0 && (
            <div className="mt-3 rounded-lg bg-surface-2 p-3">
              <p className="text-sm font-medium text-ink">{failed.length === 1 ? "1 file needs your attention" : `${failed.length} files need your attention`}</p>
              <ul className="mt-2 space-y-1.5">
                {failed.map((x) => (
                  <li key={x.key} className="text-sm"><span className="font-medium text-ink-2">{x.name}</span><span className="block text-ink-3">{x.problem}</span></li>
                ))}
              </ul>
              {retryable.length > 0 && <Button className="mt-3" onClick={sendAgain}>Send again</Button>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function QuickCheck({ app, docs, reloadDocs, onCheck, checking, hasResult }:
  { app: Application; docs: Doc[]; reloadDocs: () => void; onCheck: () => void; checking: boolean; hasResult: boolean }) {
  const reading = docs.filter((d) => ["uploaded", "processing"].includes(d.status)).length;
  const ready = docs.filter((d) => d.status === "processed").length;
  return (
    <Card className="space-y-4">
      <SectionTitle title={hasResult ? "Add more documents and check again" : "Check your file in one step"}
        subtitle="1. Drop your documents   2. Press “Check my file”   3. Read your results" />
      <DropZone app={app} onUploaded={reloadDocs} compact={hasResult} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="flex items-center gap-2 text-sm text-ink-2">
          <FileText className="h-4 w-4 text-ink-3" aria-hidden />
          {docs.length === 0 ? "No documents yet" : <>{docs.length} document{docs.length > 1 ? "s" : ""}{reading > 0 ? <> · reading {reading}…</> : <> · all read</>}</>}
          {reading > 0 && <Loader2 className="h-4 w-4 animate-spin text-accent" aria-hidden />}
        </p>
        <Button size="lg" onClick={onCheck} loading={checking} disabled={docs.length === 0 || app.reassessments.remaining <= 0}>
          <Sparkles className="h-5 w-5" aria-hidden /> {checking ? (reading > 0 ? "Reading documents…" : "Checking your file…") : hasResult ? "Check my file again" : "Check my file"}
        </Button>
      </div>
      {checking && <p className="text-xs text-ink-3">Every document is being read word for word. This usually takes under a minute; larger files can take a little longer.</p>}
      {ready === 0 && docs.length === 0 && <p className="text-xs text-ink-3">Tip: you can also fill in <a href="/profile" className="text-accent underline">your profile</a> — the more we know, the more precise the check.</p>}
    </Card>
  );
}

const STRENGTH: Record<string, { label: string; tone: "ok" | "warn" | "bad"; note: string }> = {
  strong: { label: "Strong file", tone: "ok", note: "Your file looks well prepared." },
  fair: { label: "Fair file — needs work", tone: "warn", note: "Some important things need fixing before you apply." },
  weak: { label: "Weak file — not ready", tone: "bad", note: "Several important problems need fixing before you apply." },
};

/** Claude's full case review, written in plain language. */
export function AiReviewCard({ review, error }: { review?: AiReview; error?: string }) {
  if (error && !review) return <Alert tone="warn" title="AI case review unavailable">{error}</Alert>;
  if (!review) return null;
  const s = STRENGTH[review.file_strength] ?? STRENGTH.fair;
  return (
    <Card className="space-y-5 border-accent/30">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-accent"><Sparkles className="h-4 w-4" aria-hidden /> Case review — every document read in full</p>
          <h2 className="mt-1 text-xl font-semibold text-ink">{review.headline}</h2>
        </div>
        <Badge tone={s.tone} className="px-3 py-1 text-sm">{s.label}</Badge>
      </div>
      <p className="text-sm leading-relaxed text-ink-2">{review.summary}</p>
      {review.professional_advice_recommended && <Alert tone="info">Parts of your situation need professional judgement. We recommend speaking to a qualified immigration adviser before you apply.</Alert>}

      {review.problems.length > 0 && (
        <section>
          <h3 className="mb-2 font-semibold text-ink">What to fix ({review.problems.length})</h3>
          <ul className="space-y-2">
            {review.problems.map((p, i) => (
              <li key={i} className="rounded-lg bg-surface-2 p-3">
                <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink"><Badge tone={severityTone[p.severity]}>{p.severity}</Badge>{p.title}</p>
                <p className="mt-1 text-sm text-ink-2">{p.explanation}</p>
                <p className="mt-1 text-sm text-ink"><b>How to fix:</b> {p.how_to_fix}</p>
                {p.documents.length > 0 && <p className="mt-1 text-xs text-ink-3">Documents: {p.documents.join(", ")}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        {review.missing_documents.length > 0 && (
          <section>
            <h3 className="mb-2 font-semibold text-ink">Documents still needed</h3>
            <ul className="space-y-1.5 text-sm">{review.missing_documents.map((m, i) => <li key={i} className="flex gap-2"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden /><span><b className="text-ink">{m.document}</b> — <span className="text-ink-2">{m.why_needed}</span></span></li>)}</ul>
          </section>
        )}
        {review.strengths.length > 0 && (
          <section>
            <h3 className="mb-2 font-semibold text-ink">What is already strong</h3>
            <ul className="space-y-1.5 text-sm">{review.strengths.map((x, i) => <li key={i} className="flex gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-hidden /><span className="text-ink-2">{x}</span></li>)}</ul>
          </section>
        )}
      </div>

      {review.next_steps.length > 0 && (
        <section>
          <h3 className="mb-2 font-semibold text-ink">Your next steps</h3>
          <ol className="list-decimal space-y-1 pl-5 text-sm text-ink-2">{review.next_steps.map((x, i) => <li key={i}>{x}</li>)}</ol>
        </section>
      )}

      <details className="rounded-lg border border-line">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-ink">What we read in each document ({review.documents.length})</summary>
        <ul className="divide-y divide-line">
          {review.documents.map((d, i) => (
            <li key={i} className="px-4 py-3 text-sm">
              <p className="font-medium text-ink">{d.filename} <span className="font-normal text-ink-3">— {d.what_it_is}{!d.readable && " (hard to read)"}</span></p>
              {d.key_facts.length > 0 && <ul className="mt-1 list-disc pl-5 text-ink-2">{d.key_facts.map((f, j) => <li key={j}>{f}</li>)}</ul>}
              {d.concerns.length > 0 && <ul className="mt-1 list-disc pl-5 text-warn">{d.concerns.map((f, j) => <li key={j}>{f}</li>)}</ul>}
            </li>
          ))}
        </ul>
      </details>
      {review.questions_to_prepare.length > 0 && (
        <details className="rounded-lg border border-line">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-ink">Questions an officer might ask ({review.questions_to_prepare.length})</summary>
          <ul className="list-disc space-y-1 px-9 pb-3 text-sm text-ink-2">{review.questions_to_prepare.map((q, i) => <li key={i}>{q}</li>)}</ul>
        </details>
      )}
      <p className="text-xs text-ink-3">{s.note} This rates how well your file is prepared — it is not a prediction of the visa decision. AI can make mistakes: check every point against your documents.</p>
    </Card>
  );
}
