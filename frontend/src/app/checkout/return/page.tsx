"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { CheckCircle2, Clock, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { Logo } from "@/components/shell";
import { ButtonLink, Card, Spinner } from "@/components/ui";

type Payment = { id: string; purpose: string; reference_id: string; status: string; invoice_number: string | null; amount: string };

function Return() {
  const { ready } = useRequireAuth();
  const sp = useSearchParams();
  const id = sp.get("payment");
  const [p, setP] = useState<Payment | null>(null);
  const [tries, setTries] = useState(0);
  useEffect(() => {
    if (!ready || !id) return;
    api<Payment>(`/payments/${id}`).then((r) => {
      setP(r);
      // Provider callbacks can arrive a few seconds after the redirect: poll briefly.
      if (r.status === "pending" && tries < 10) setTimeout(() => setTries((t) => t + 1), 2000);
    }).catch(() => {});
  }, [ready, id, tries]);
  if (!p) return <Spinner label="Confirming your payment…" />;
  const next = p.purpose === "writing_order" ? `/orders/${p.reference_id}` : `/applications/${p.reference_id}`;
  return (
    <Card className="w-full max-w-md p-8 text-center">
      {p.status === "succeeded" ? <CheckCircle2 className="mx-auto h-10 w-10 text-ok" /> : p.status === "pending" ? <Clock className="mx-auto h-10 w-10 text-warn" /> : <XCircle className="mx-auto h-10 w-10 text-bad" />}
      <h1 className="mt-4 text-xl font-semibold text-ink">{p.status === "succeeded" ? "Payment confirmed" : p.status === "pending" ? "Waiting for confirmation" : "Payment not completed"}</h1>
      <p className="mt-2 text-sm text-ink-3">
        {p.status === "succeeded" ? `Invoice ${p.invoice_number}. You can continue right away.` : p.status === "pending" ? "We are waiting for the payment provider to confirm. This page updates automatically." : "You have not been charged by us. You can try again."}
      </p>
      <ButtonLink href={next} className="mt-6">{p.status === "succeeded" ? "Continue" : "Back"}</ButtonLink>
      <p className="mt-4 text-xs"><Link href="/payments" className="text-accent">Payment history</Link></p>
    </Card>
  );
}

export default function Page() {
  return <div className="flex min-h-dvh flex-col items-center justify-center gap-8 px-4"><Logo /><Suspense fallback={<Spinner />}><Return /></Suspense></div>;
}
