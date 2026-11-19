"use client";

import Link from "next/link";
import { fmtDate, label } from "@/lib/api";
import { useLoad } from "@/lib/auth";
import type { WritingOrder } from "@/lib/types";
import { PageHeader } from "@/components/shell";
import { Countdown } from "@/components/countdown";
import { Badge, ButtonLink, Card, Empty, Spinner, statusTone } from "@/components/ui";

export default function OrdersPage() {
  const { data } = useLoad<WritingOrder[]>("/writing-orders");
  if (!data) return <Spinner />;
  return (
    <div>
      <PageHeader title="My orders" actions={<ButtonLink href="/services">New order</ButtonLink>} />
      {!data.length ? <Empty title="No orders yet" action={<ButtonLink href="/services">Browse writing services</ButtonLink>} /> : (
        <div className="space-y-3">
          {data.map((o) => (
            <Link key={o.id} href={`/orders/${o.id}`}>
              <Card className="flex flex-wrap items-center justify-between gap-3 p-4 hover:border-accent/40">
                <div><p className="font-medium text-ink">{o.service_name}</p><p className="text-xs text-ink-3">{o.reference} · ${o.price} · {fmtDate(o.created_at)}</p></div>
                <div className="flex items-center gap-3">
                  {o.deadline_at && o.seconds_remaining != null && <span className="text-sm">⏱ <Countdown deadline={o.deadline_at} /></span>}
                  <Badge tone={statusTone[o.status]}>{label(o.status)}</Badge>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
