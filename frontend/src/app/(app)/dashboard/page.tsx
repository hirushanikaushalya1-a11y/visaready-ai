"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle, ArrowRight, Bell, FileText, Megaphone, Plus, TrendingUp } from "lucide-react";
import { api, fmtDate, label } from "@/lib/api";
import { useLoad } from "@/lib/auth";
import type { Application, Assessment, WritingOrder } from "@/lib/types";
import { PageHeader } from "@/components/shell";
import { Countdown } from "@/components/countdown";
import { Badge, ButtonLink, Card, Empty, Progress, ScoreRing, SectionTitle, severityTone, Spinner, statusTone } from "@/components/ui";

type Profile = { completion: number };
type Alert = { id: string; country_code: string; title: string; summary: string; source_url: string; published_at: string };
type History = { id: string; version: number; readiness_score: number | null; created_at: string }[];

export default function Dashboard() {
  const apps = useLoad<Application[]>("/applications");
  const profile = useLoad<Profile>("/profile");
  const orders = useLoad<WritingOrder[]>("/writing-orders");
  const alerts = useLoad<Alert[]>("/policy-alerts");
  const [latest, setLatest] = useState<Assessment | null>(null);
  const [history, setHistory] = useState<History>([]);

  const focus = apps.data?.find((a) => a.latest_assessment?.status === "completed") ?? apps.data?.[0];
  useEffect(() => {
    if (focus?.latest_assessment?.status === "completed") {
      api<Assessment>(`/assessments/${focus.latest_assessment.id}`).then(setLatest).catch(() => {});
      api<History>(`/applications/${focus.id}/assessments`).then(setHistory).catch(() => {});
    }
  }, [focus?.id, focus?.latest_assessment?.id, focus?.latest_assessment?.status]);

  if (apps.loading && !apps.data) return <Spinner />;
  const activeOrders = (orders.data ?? []).filter((o) => !["delivered", "refunded", "cancelled"].includes(o.status));
  const outstanding = latest?.checklist.filter((i) => i.status !== "satisfied") ?? [];
  const issues = latest?.findings.filter((f) => !["strength", "question"].includes(f.kind)).slice(0, 5) ?? [];
  const totalDocs = (apps.data ?? []).reduce((n, a) => n + a.document_count, 0);

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" subtitle="Your application preparation at a glance."
        actions={<ButtonLink href="/applications/new"><Plus className="h-4 w-4" aria-hidden /> New application</ButtonLink>} />

      {(profile.data?.completion ?? 100) < 80 && (
        <Card className="flex flex-wrap items-center justify-between gap-4 border-accent/30 bg-accent-soft/40">
          <div className="min-w-0 flex-1">
            <p className="font-medium text-ink">Complete your profile — {profile.data?.completion ?? 0}%</p>
            <p className="text-sm text-ink-3">Your assessment can only check what you tell us. Unanswered questions lower your readiness score.</p>
            <div className="mt-3 max-w-sm"><Progress value={profile.data?.completion ?? 0} /></div>
          </div>
          <ButtonLink href="/profile" variant="secondary">Continue profile</ButtonLink>
        </Card>
      )}

      {!apps.data?.length ? (
        <Empty title="No applications yet" action={<ButtonLink href="/applications/new">Create your first application</ButtonLink>}>
          Choose your destination and visa type. You can explore requirements for free and unlock the full assessment when ready.
        </Empty>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* 1. Application readiness */}
          <Card className="lg:col-span-1">
            <SectionTitle title="Application readiness" subtitle={focus?.title} />
            <div className="flex flex-col items-center gap-3">
              <ScoreRing score={focus?.latest_assessment?.score ?? null} />
              <p className="text-center text-xs text-ink-3">Preparation quality only — not a probability of approval.</p>
              {focus && <ButtonLink href={`/applications/${focus.id}`} variant="secondary" size="sm">Open workspace <ArrowRight className="h-4 w-4" aria-hidden /></ButtonLink>}
            </div>
          </Card>

          {/* 2. Outstanding evidence */}
          <Card className="lg:col-span-2">
            <SectionTitle title="Outstanding evidence" subtitle={latest ? `${outstanding.length} item(s) still need attention` : "Run an assessment to build your checklist"} />
            {latest ? (
              outstanding.length ? (
                <ul className="divide-y divide-line">
                  {outstanding.slice(0, 6).map((i) => (
                    <li key={i.item_key} className="flex items-center justify-between gap-3 py-2.5">
                      <span className="min-w-0 truncate text-sm text-ink-2">{i.title}</span>
                      <Badge tone={statusTone[i.status]}>{label(i.status)}</Badge>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-ok">Every checklist item has a recognised document.</p>
            ) : <p className="text-sm text-ink-3">No assessment yet.</p>}
          </Card>

          {/* 3. Recent AI findings */}
          <Card className="lg:col-span-2">
            <SectionTitle title="Recent findings" subtitle="Highest-priority issues from your latest assessment" />
            {issues.length ? (
              <ul className="space-y-2">
                {issues.map((f) => (
                  <li key={f.id} className="flex gap-3 rounded-lg bg-surface-2 px-3 py-2.5">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden />
                    <div className="min-w-0"><p className="text-sm font-medium text-ink">{f.title}</p><p className="truncate text-xs text-ink-3">{f.explanation}</p></div>
                    <Badge tone={severityTone[f.severity]} className="ml-auto self-start">{f.severity}</Badge>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-ink-3">No findings yet.</p>}
          </Card>

          {/* 4. Uploaded documents */}
          <Card>
            <SectionTitle title="Documents" />
            <div className="flex items-center gap-3"><FileText className="h-8 w-8 text-accent" aria-hidden /><div><p className="text-2xl font-semibold text-ink">{totalDocs}</p><p className="text-xs text-ink-3">uploaded across {apps.data.length} application(s)</p></div></div>
            <ul className="mt-4 space-y-2">
              {apps.data.map((a) => (
                <li key={a.id}><Link href={`/applications/${a.id}`} className="flex items-center justify-between text-sm text-ink-2 hover:text-ink"><span className="truncate">{a.title}</span><Badge tone={statusTone[a.status]}>{a.status}</Badge></Link></li>
              ))}
            </ul>
          </Card>

          {/* 5/6. Active writing orders + countdown */}
          <Card>
            <SectionTitle title="Writing orders" action={<Link href="/services" className="text-sm text-accent">Order</Link>} />
            {activeOrders.length ? (
              <ul className="space-y-3">
                {activeOrders.map((o) => (
                  <li key={o.id}><Link href={`/orders/${o.id}`} className="block rounded-lg border border-line p-3 hover:bg-surface-2">
                    <div className="flex items-center justify-between gap-2"><span className="text-sm font-medium text-ink">{o.service_name}</span><Badge tone={statusTone[o.status]}>{label(o.status)}</Badge></div>
                    <p className="mt-1 text-xs text-ink-3">{o.reference}</p>
                    {o.deadline_at && o.seconds_remaining != null && <p className="mt-1 text-sm">Delivery in <Countdown deadline={o.deadline_at} /></p>}
                  </Link></li>
                ))}
              </ul>
            ) : <p className="text-sm text-ink-3">No active orders.</p>}
          </Card>

          {/* 7. Improvement history */}
          <Card>
            <SectionTitle title="Improvement history" />
            {history.length ? (
              <ol className="space-y-2">
                {history.map((h, i) => {
                  const prev = history[i + 1]?.readiness_score;
                  const d = prev != null && h.readiness_score != null ? h.readiness_score - prev : null;
                  return (
                    <li key={h.id} className="flex items-center justify-between text-sm">
                      <span className="text-ink-2">v{h.version} · {fmtDate(h.created_at)}</span>
                      <span className="flex items-center gap-2 font-medium tabular-nums text-ink">{h.readiness_score ?? "—"}
                        {d != null && d !== 0 && <span className={d > 0 ? "text-ok" : "text-bad"}><TrendingUp className="inline h-3.5 w-3.5" aria-hidden /> {d > 0 ? `+${d}` : d}</span>}</span>
                    </li>
                  );
                })}
              </ol>
            ) : <p className="text-sm text-ink-3">Assessment versions will appear here.</p>}
          </Card>

          {/* 8. Immigration alerts */}
          <Card>
            <SectionTitle title="Immigration alerts" />
            {alerts.data?.length ? (
              <ul className="space-y-3">
                {alerts.data.slice(0, 4).map((a) => (
                  <li key={a.id} className="text-sm"><p className="flex items-center gap-2 font-medium text-ink"><Megaphone className="h-4 w-4 text-accent" aria-hidden />{a.title}</p>
                    <p className="text-xs text-ink-3">{a.country_code} · {fmtDate(a.published_at)} · <a href={a.source_url} target="_blank" rel="noreferrer" className="text-accent underline">official source</a></p></li>
                ))}
              </ul>
            ) : <p className="flex items-center gap-2 text-sm text-ink-3"><Bell className="h-4 w-4" aria-hidden /> No verified policy changes affecting you.</p>}
          </Card>
        </div>
      )}
    </div>
  );
}
