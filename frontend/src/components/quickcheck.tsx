"use client";

import { useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, FileText, Loader2, Sparkles, UploadCloud, XCircle } from "lucide-react";
import { ApiError, upload } from "@/lib/api";
import type { AiReview, Application, Doc } from "@/lib/types";
import { Alert, Badge, Button, Card, cx, SectionTitle, severityTone } from "./ui";

const ACCEPT = ["application/pdf", "image/jpeg", "image/png"];
type Item = { key: string; name: string; state: "uploading" | "done" | "error"; error?: string; file?: File };

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Uploads one file, retrying automatically when the server is busy, restarting or the connection drops. */
async function uploadWithRetry(appId: string, f: File, onRetry: (n: number) => void) {
  for (let attempt = 1; ; attempt++) {
    const fd = new FormData();
    fd.append("file", f);
    try {
      return await upload(`/applications/${appId}/documents`, fd);
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0; // 0 = network error / server restarting
      const transient = status === 0 || status === 429 || status >= 500;
      if (!transient || attempt >= 5) throw e;
      onRetry(attempt);
      await sleep(Math.min(30_000, 4_000 * attempt));
    }
  }
}

function friendly(e: unknown) {
  if (e instanceof ApiError) return e.status >= 500 ? "The server was busy — press Try again" : e.message;
  return "Connection lost — press Try again";
}

/** Big drag-and-drop area: drop every document at once. No document types to choose. */
export function DropZone({ app, onUploaded, compact = false, onBatchDone }: { app: Application; onUploaded: () => void; compact?: boolean; onBatchDone?: () => void }) {
  const [over, setOver] = useState(false);
  const [items, setItems] = useState<Item[]>([]);
  const input = useRef<HTMLInputElement>(null);

  async function run(batch: Item[]) {
    const set = (key: string, patch: Partial<Item>) => setItems((cur) => cur.map((x) => (x.key === key ? { ...x, ...patch } : x)));
    // Two at a time: quick for large batches, gentle on the server while it reads earlier documents.
    let next = 0;
    async function worker() {
      while (next < batch.length) {
        const it = batch[next++];
        const f = it.file!;
        if (!ACCEPT.includes(f.type) && !/\.(pdf|jpe?g|png)$/i.test(f.name)) { set(it.key, { state: "error", error: "Only PDF, JPG or PNG", file: undefined }); continue; }
        if (f.size > app.limits.max_file_size_mb * 1024 * 1024) { set(it.key, { state: "error", error: `Larger than ${app.limits.max_file_size_mb} MB — please compress or split it`, file: undefined }); continue; }
        try {
          await uploadWithRetry(app.id, f, (n) => set(it.key, { state: "uploading", error: `Retrying (${n})…` }));
          set(it.key, { state: "done", error: undefined, file: undefined });
          onUploaded();
        } catch (e) { set(it.key, { state: "error", error: friendly(e) }); }
      }
    }
    await Promise.all([worker(), worker()]);
    onUploaded();
    onBatchDone?.();
  }

  function handle(files: FileList | File[]) {
    const list = Array.from(files);
    const fresh: Item[] = list.map((f, i) => ({ key: `${Date.now()}-${i}-${f.name}`, name: f.name, state: "uploading", file: f }));
    setItems((cur) => [...fresh, ...cur].slice(0, 60));
    void run(fresh);
  }

  const retryable = items.filter((x) => x.state === "error" && x.file);
  function retryFailed() {
    const batch = retryable.map((x) => ({ ...x, state: "uploading" as const, error: undefined }));
    setItems((cur) => cur.map((x) => batch.find((b) => b.key === x.key) ?? x));
    void run(batch);
  }

  return (
    <div>
      <div
        role="button" tabIndex={0} aria-label="Drop documents here or press to choose files"
        onClick={() => input.current?.click()}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") input.current?.click(); }}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); if (e.dataTransfer.files.length) handle(e.dataTransfer.files); }}
        className={cx("flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed text-center transition",
          compact ? "px-4 py-6" : "px-6 py-12",
          over ? "border-accent bg-accent-soft/60" : "border-line bg-surface-2/50 hover:border-accent/60 hover:bg-accent-soft/30")}>
        <UploadCloud className={cx("text-accent", compact ? "h-8 w-8" : "h-12 w-12")} aria-hidden />
        <p className={cx("mt-3 font-semibold text-ink", compact ? "text-base" : "text-lg")}>Drop all your documents here</p>
        <p className="mt-1 max-w-md text-sm text-ink-3">Passport, bank statements, certificates, letters — everything at once. Or <span className="font-medium text-accent underline">choose files</span>. We work out what each document is.</p>
        <p className="mt-2 text-xs text-ink-3">PDF, JPG or PNG · up to {app.limits.max_file_size_mb} MB each · encrypted immediately</p>
        <input ref={input} type="file" multiple accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" className="hidden"
          onChange={(e) => { if (e.target.files?.length) handle(e.target.files); e.target.value = ""; }} />
      </div>
      {items.some((x) => x.state !== "done") && (
        <ul className="mt-3 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
          {items.filter((x) => x.state !== "done").map((x) => (
            <li key={x.key} className="flex min-w-0 items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm">
              {x.state === "uploading" ? <Loader2 className="h-4 w-4 shrink-0 animate-spin text-accent" aria-hidden />
                : x.state === "done" ? <CheckCircle2 className="h-4 w-4 shrink-0 text-ok" aria-hidden /> : <XCircle className="h-4 w-4 shrink-0 text-bad" aria-hidden />}
              <span className="min-w-0 flex-1">
                <span className="block truncate text-ink-2">{x.name}</span>
                <span className={cx("block text-xs", x.state === "error" ? "text-bad" : "text-ink-3")}>{x.state === "uploading" ? (x.error ?? "Uploading…") : x.state === "done" ? "Uploaded" : x.error}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
      {retryable.length > 0 && !items.some((x) => x.state === "uploading") && (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button onClick={retryFailed}>Try again ({retryable.length} {retryable.length === 1 ? "file" : "files"})</Button>
          <span className="text-sm text-ink-3">Files that uploaded are safe — only the failed ones are sent again.</span>
        </div>
      )}
    </div>
  );
}

/** The one-step flow: drop documents, press one button, get the result. */
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
