"use client";

import Link from "next/link";
import { useEffect } from "react";
import { fmtDate, post } from "@/lib/api";
import { useLoad } from "@/lib/auth";
import type { Notification } from "@/lib/types";
import { PageHeader } from "@/components/shell";
import { Badge, Card, cx, Empty, Spinner } from "@/components/ui";

export default function NotificationsPage() {
  const { data } = useLoad<{ unread: number; items: Notification[] }>("/notifications");
  useEffect(() => { if (data?.unread) post("/notifications/read-all").catch(() => {}); }, [data?.unread]);
  if (!data) return <Spinner />;
  return (
    <div>
      <PageHeader title="Notifications" />
      {!data.items.length ? <Empty title="You're all caught up" /> : (
        <div className="space-y-3">
          {data.items.map((n) => (
            <Card key={n.id} className={cx("p-4", !n.read && "border-accent/40")}>
              <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-medium text-ink">{n.title}</p><span className="text-xs text-ink-3">{fmtDate(n.created_at, true)}</span></div>
              <p className="mt-1 whitespace-pre-line text-sm text-ink-2">{n.body}</p>
              <div className="mt-2 flex items-center gap-3">
                {n.link && <Link href={n.link} className="text-sm text-accent">View</Link>}
                {n.email_status === "outbox_only" && <Badge tone="neutral">Email not sent — email delivery not configured</Badge>}
                {n.email_status === "failed" && <Badge tone="bad">Email delivery failed</Badge>}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
