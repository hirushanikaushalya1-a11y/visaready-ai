"use client";

import Link from "next/link";
import { money } from "@/lib/api";
import { useAuth, useLoad } from "@/lib/auth";
import { PageHeader } from "@/components/shell";
import { Alert, Card, SectionTitle, Spinner, Stat } from "@/components/ui";

type Overview = {
  users: number; applications: Record<string, number>; assessments_7d: number; documents: Record<string, number>;
  writing_orders_open: number; writing_orders_due_6h: number; refund_eligible: number; revenue_30d_cents: number; sandbox_payments_30d: number;
  deletion_requests_open: number; requirements_pending_review: number; jobs: Record<string, number>; support_open: number;
};
type Health = { integrations: Record<string, string> };

export default function AdminHome() {
  const { me } = useAuth();
  const { data } = useLoad<Overview>("/admin/overview");
  const { data: health } = useLoad<Health>("/health");
  if (!data) return <Spinner />;
  return (
    <div className="space-y-6">
      <PageHeader title="Operations overview" subtitle={`Signed in as ${me?.full_name} · ${me?.role.replace("_", " ")}`} />
      {data.writing_orders_due_6h > 0 && <Alert tone="warn" title={`${data.writing_orders_due_6h} writing order(s) due within 6 hours`}><Link href="/admin/orders" className="underline">Open the order queue</Link></Alert>}
      {data.refund_eligible > 0 && <Alert tone="bad" title={`${data.refund_eligible} order(s) missed the 24-hour guarantee`}>Process refunds from the order page.</Alert>}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card><Stat label="Applicants" value={data.users} /></Card>
        <Card><Stat label="Active applications" value={data.applications.active} hint={`${data.applications.draft} drafts · ${data.applications.completed} completed`} /></Card>
        <Card><Stat label="Assessments (7 days)" value={data.assessments_7d} /></Card>
        <Card><Stat label="Revenue (30 days)" value={money(data.revenue_30d_cents, "EUR")} hint={`${data.sandbox_payments_30d} test-mode payments excluded`} /></Card>
        <Card><Stat label="Open writing orders" value={data.writing_orders_open} /></Card>
        <Card><Stat label="Requirements awaiting verification" value={data.requirements_pending_review} hint={<Link href="/admin/knowledge" className="text-accent">Review</Link>} /></Card>
        <Card><Stat label="Deletion requests" value={data.deletion_requests_open} /></Card>
        <Card><Stat label="Open support tickets" value={data.support_open} /></Card>
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card><SectionTitle title="Document processing" />
          <ul className="grid grid-cols-2 gap-2 text-sm">{Object.entries(data.documents).map(([k, v]) => <li key={k} className="flex justify-between rounded bg-surface-2 px-3 py-2"><span className="text-ink-3">{k}</span><b>{v}</b></li>)}
            {Object.entries(data.jobs).map(([k, v]) => <li key={k} className="flex justify-between rounded bg-surface-2 px-3 py-2"><span className="text-ink-3">jobs {k}</span><b className={k === "failed" && v ? "text-bad" : ""}>{v}</b></li>)}</ul></Card>
        <Card><SectionTitle title="Integrations" subtitle="Features awaiting credentials are clearly labelled to users." />
          <ul className="space-y-1.5 text-sm">{Object.entries(health?.integrations ?? {}).map(([k, v]) => <li key={k} className="flex justify-between"><span className="text-ink-3">{k.replace("_", " ")}</span><b>{v}</b></li>)}</ul></Card>
      </div>
    </div>
  );
}
