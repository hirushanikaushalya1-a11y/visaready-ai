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
import { AiReviewCard, QuickCheck } from "@/components/quickcheck";
import { CaseFile, Checklist, Documents, Drafts, FamilyMap, Findings, Improvements, Overview, ProofBuilder, Questions, WhatIf } from "@/components/workspace";

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
      // One click: wait until every document has been read, then run the check.
      for (let i = 0; i < 120; i++) {
        const list = await api<Doc[]>(`/applications/${id}/documents`);
        if (!list.some((d) => ["uploaded", "processing"].includes(d.status))) break;
        docsQ.load();
        await new Promise((res) => setTimeout(res, 2000));
      }
      docsQ.load();
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
  const report = services?.find((s) => s.code === "assessment_report");
  const docs = docsQ.data ?? [];
  const count = (k: string[]) => a?.findings.filter((f) => k.includes(f.kind)).length ?? 0;
  const buyReport = () => startCheckout("assessment_report", app.id).catch((e) => setError(e.message));

  return (
    <div className="space-y-6">
      <PageHeader title={app.title}
        subtitle={<span className="flex flex-wrap items-center gap-2">{app.country_name} · {app.visa_category.name}
          <Badge tone={statusTone[app.status]}>{app.status}</Badge>
          {app.report_unlocked && <Badge tone="ok">Full report unlocked</Badge>}
          {app.visa_category.official_url && <a href={app.visa_category.official_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent">Official page <ExternalLink className="h-3 w-3" aria-hidden /></a>}</span>}
        actions={app.status === "active" && a ? <Button variant="secondary" size="sm" onClick={async () => { if (confirm("Mark this application as complete? Documents will be deleted after the retention period.")) { await post(`/applications/${id}/complete`); appQ.load(); } }}>Mark as submitted</Button> : undefined} />

      <>
          {error && <Alert tone="bad">{error}</Alert>}
          {app.status === "completed" && app.retention_delete_after && <Alert tone="info">Marked as submitted. Your documents will be permanently deleted after {new Date(app.retention_delete_after).toLocaleDateString()}. Download anything you need before then.</Alert>}
          {a && !app.report_unlocked && report && (
            <Card className="flex flex-wrap items-center gap-4 border-accent/40 bg-accent-soft/30">
              <Lock className="h-6 w-6 shrink-0 text-accent" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-ink">Get your full assessment report — {money(report.price_cents, report.currency)}</p>
                <p className="text-sm text-ink-2">Printable report, lodge-ready submission file and suggested drafts for every letter your file needs. Your assessment stays free.</p>
              </div>
              <Button onClick={buyReport}>Unlock full report</Button>
            </Card>
          )}
          <Tabs active={tab} onChange={setTab} tabs={[
            { id: "overview", label: "Overview" },
            { id: "checklist", label: "Checklist", count: a?.checklist.filter((i) => i.status !== "satisfied").length },
            { id: "documents", label: "Documents", count: docs.length },
            { id: "casefile", label: "Submission file" },
            { id: "drafts", label: "Drafts" },
            { id: "proof", label: "Proof Builder" },
            { id: "findings", label: "Findings", count: count(["inconsistency", "missing_evidence", "concern", "professional_review", "refusal_reason", "document_quality"]) },
            { id: "questions", label: "Questions", count: count(["question"]) },
            { id: "improvements", label: "Improvements" },
            { id: "whatif", label: "What-if" },
            { id: "family", label: "Family", count: app.family_members?.length },
          ]} />
          {tab === "overview" && (
            <div className="space-y-6">
              <QuickCheck app={app} docs={docs} reloadDocs={docsQ.load} onCheck={run} checking={running} hasResult={!!a} />
              {a && <AiReviewCard review={a.summary.ai_review} error={a.summary.ai_review_error} />}
              {a && <Overview app={app} a={a} onRun={run} running={running} onBuyReport={buyReport} />}
            </div>
          )}
          {tab === "checklist" && <Checklist app={app} a={a} docs={docs} onStateChange={appQ.load} onUploadFor={(key, type) => { setPreset({ key, type }); setTab("documents"); }} />}
          {tab === "documents" && <Documents app={app} docs={docs} reload={docsQ.load} preset={preset} clearPreset={() => setPreset(null)} />}
          {tab === "casefile" && <CaseFile a={a} unlocked={app.report_unlocked} onBuyReport={buyReport} onUploadFor={() => setTab("documents")} />}
          {tab === "drafts" && <Drafts a={a} onBuyReport={buyReport} reportPrice={report ? money(report.price_cents, report.currency) : ""} />}
          {tab === "proof" && <ProofBuilder a={a} docs={docs} />}
          {tab === "findings" && <Findings a={a} docs={docs} />}
          {tab === "questions" && <Questions a={a} />}
          {tab === "improvements" && <Improvements appId={app.id} key={a?.id} />}
          {tab === "whatif" && <WhatIf app={app} hasAssessment={!!a} />}
          {tab === "family" && <FamilyMap app={app} a={a} reload={appQ.load} />}
          <p className="text-center text-xs text-ink-3">Want us to write it for you? <Link href="/services" className="text-accent">SOP, letters, relationship portfolio and more — delivered within 24 hours</Link> · Readiness is not a probability of approval.</p>
      </>
    </div>
  );
}
