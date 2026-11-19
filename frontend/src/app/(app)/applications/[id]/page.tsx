"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ExternalLink, Lock } from "lucide-react";
import { api, ApiError, money, post } from "@/lib/api";
import { useLoad } from "@/lib/auth";
import { startCheckout } from "@/lib/checkout";
import type { Application, Assessment, Doc, Service } from "@/lib/types";
import { PageHeader } from "@/components/shell";
import { Alert, Badge, Button, Card, Spinner, statusTone, Tabs } from "@/components/ui";
import { Checklist, Documents, FamilyMap, Findings, Improvements, Overview, ProofBuilder, Questions, WhatIf } from "@/components/workspace";

async function pollAssessment(assessmentId: string): Promise<Assessment> {
  let r = await api<Assessment>(`/assessments/${assessmentId}`);
  for (let i = 0; i < 80 && (r.status === "queued" || r.status === "running"); i++) {
    await new Promise((res) => setTimeout(res, 1500));
    r = await api<Assessment>(`/assessments/${assessmentId}`);
  }
  return r;
}

export default function Workspace() {
  const { id } = useParams<{ id: string }>();
  const appQ = useLoad<Application>(`/applications/${id}`);
  const docsQ = useLoad<Doc[]>(`/applications/${id}/documents`);
  const { data: services } = useLoad<Service[]>("/services");
  const [a, setA] = useState<Assessment | null>(null);
  const [tab, setTab] = useState("overview");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preset, setPreset] = useState<{ key?: string; type?: string } | null>(null);
  const app = appQ.data;

  const latestId = app?.latest_assessment?.id;
  useEffect(() => {
    if (!latestId) return;
    let cancelled = false;
    pollAssessment(latestId).then((r) => {
      if (cancelled) return;
      setA(r.status === "completed" ? r : null);
      if (r.status === "failed") setError(r.error);
    });
    return () => { cancelled = true; };
  }, [latestId]);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const r = await post<{ id: string }>(`/applications/${id}/assessments`);
      const done = await pollAssessment(r.id);
      if (done.status === "completed") setA(done);
      else setError(done.error ?? "The assessment did not complete.");
      appQ.load();
      setTab("overview");
    } catch (e) {
      setError(e instanceof ApiError && e.status === 402 ? `${e.message}` : e instanceof Error ? e.message : "Failed");
    } finally {
      setRunning(false);
    }
  }

  if (appQ.error) return <Alert tone="bad">{appQ.error}</Alert>;
  if (!app) return <Spinner />;
  const price = services?.find((s) => s.code === "assessment");
  const docs = docsQ.data ?? [];
  const count = (k: string[]) => a?.findings.filter((f) => k.includes(f.kind)).length ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader title={app.title}
        subtitle={<span className="flex flex-wrap items-center gap-2">{app.country_name} · {app.visa_category.name}
          <Badge tone={statusTone[app.status]}>{app.status}</Badge>
          {app.visa_category.official_url && <a href={app.visa_category.official_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent">Official page <ExternalLink className="h-3 w-3" aria-hidden /></a>}</span>}
        actions={app.status === "active" && a ? <Button variant="secondary" size="sm" onClick={async () => { if (confirm("Mark this application as complete? Documents will be deleted after the retention period.")) { await post(`/applications/${id}/complete`); appQ.load(); } }}>Mark as submitted</Button> : undefined} />

      {app.status === "draft" ? (
        <Card className="mx-auto max-w-2xl text-center">
          <Lock className="mx-auto h-8 w-8 text-accent" aria-hidden />
          <h2 className="mt-3 text-lg font-semibold text-ink">Unlock your assessment</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-ink-3">Uploads, AI document analysis, your personalised checklist, Evidence Intelligence and readiness reports are part of the {price ? money(price.price_cents) : ""} assessment package.</p>
          <ul className="mx-auto mt-4 max-w-md space-y-1 text-left text-sm text-ink-2">{price?.inclusions.map((i) => <li key={i}>• {i}</li>)}</ul>
          <Button className="mt-6" onClick={() => startCheckout("assessment", app.id).catch((e) => setError(e.message))}>Pay {price ? money(price.price_cents) : ""} and unlock</Button>
          {error && <div className="mt-4"><Alert tone="bad">{error}</Alert></div>}
          <p className="mt-4 text-xs text-ink-3">{price?.disclaimer}</p>
        </Card>
      ) : (
        <>
          {error && <Alert tone="bad">{error}{error.includes("reassessment") && <> <button className="underline" onClick={() => startCheckout("reassessment", app.id)}>Buy an additional reassessment</button></>}</Alert>}
          {app.status === "completed" && app.retention_delete_after && <Alert tone="info">Marked as submitted. Your documents will be permanently deleted after {new Date(app.retention_delete_after).toLocaleDateString()}. Download anything you need before then.</Alert>}
          <Tabs active={tab} onChange={setTab} tabs={[
            { id: "overview", label: "Overview" },
            { id: "checklist", label: "Checklist", count: a?.checklist.filter((i) => i.status !== "satisfied").length },
            { id: "documents", label: "Documents", count: docs.length },
            { id: "proof", label: "Proof Builder" },
            { id: "findings", label: "Findings", count: count(["inconsistency", "missing_evidence", "concern", "professional_review", "refusal_reason", "document_quality"]) },
            { id: "questions", label: "Questions", count: count(["question"]) },
            { id: "improvements", label: "Improvements" },
            { id: "whatif", label: "What-if" },
            { id: "family", label: "Family", count: app.family_members?.length },
          ]} />
          {tab === "overview" && <Overview app={app} a={a} onRun={run} running={running} />}
          {tab === "checklist" && <Checklist app={app} a={a} docs={docs} onStateChange={appQ.load} onUploadFor={(key, type) => { setPreset({ key, type }); setTab("documents"); }} />}
          {tab === "documents" && <Documents app={app} docs={docs} reload={docsQ.load} preset={preset} clearPreset={() => setPreset(null)} />}
          {tab === "proof" && <ProofBuilder a={a} docs={docs} />}
          {tab === "findings" && <Findings a={a} docs={docs} />}
          {tab === "questions" && <Questions a={a} />}
          {tab === "improvements" && <Improvements appId={app.id} key={a?.id} />}
          {tab === "whatif" && <WhatIf app={app} hasAssessment={!!a} />}
          {tab === "family" && <FamilyMap app={app} a={a} reload={appQ.load} />}
          <p className="text-center text-xs text-ink-3">Need help with a letter? <Link href="/services" className="text-accent">Order a professionally written document</Link> · Readiness is not a probability of approval.</p>
        </>
      )}
    </div>
  );
}
