"use client";

import Link from "next/link";
import { Plus } from "lucide-react";
import { fmtDate } from "@/lib/api";
import { useLoad } from "@/lib/auth";
import type { Application } from "@/lib/types";
import { PageHeader } from "@/components/shell";
import { Badge, ButtonLink, Card, Empty, Spinner, statusTone } from "@/components/ui";

export default function ApplicationsPage() {
  const { data } = useLoad<Application[]>("/applications");
  if (!data) return <Spinner />;
  return (
    <div>
      <PageHeader title="Applications" subtitle="One assessment package per visa application."
        actions={<ButtonLink href="/applications/new"><Plus className="h-4 w-4" aria-hidden /> New application</ButtonLink>} />
      {!data.length ? <Empty title="No applications yet" action={<ButtonLink href="/applications/new">Create application</ButtonLink>} /> : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {data.map((a) => (
            <Link key={a.id} href={`/applications/${a.id}`}>
              <Card className="h-full transition hover:border-accent/40">
                <div className="flex items-start justify-between gap-3">
                  <div><p className="font-semibold text-ink">{a.title}</p><p className="text-sm text-ink-3">{a.country_name} · {a.visa_category.name}</p></div>
                  <Badge tone={statusTone[a.status]}>{a.status === "draft" ? "Awaiting payment" : a.status}</Badge>
                </div>
                <div className="mt-4 flex gap-6 text-sm text-ink-2">
                  <span>Readiness <b className="tabular-nums text-ink">{a.latest_assessment?.score ?? "—"}</b></span>
                  <span>Documents <b className="text-ink">{a.document_count}</b></span>
                  <span>Created {fmtDate(a.created_at)}</span>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
