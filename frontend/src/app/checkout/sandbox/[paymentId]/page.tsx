"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { FlaskConical } from "lucide-react";
import { api, post, amount } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { Alert, Button, Card, Spinner } from "@/components/ui";
import { Logo } from "@/components/shell";

type Payment = { id: string; purpose: string; reference_id: string; amount: string; currency: string; status: string };

function SandboxCheckout() {
  const { ready } = useRequireAuth();
  const { paymentId } = useParams<{ paymentId: string }>();
  const token = useSearchParams().get("t") ?? "";
  const router = useRouter();
  const [p, setP] = useState<Payment | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (ready) api<Payment>(`/payments/${paymentId}`).then(setP).catch((e) => setError(e.message)); }, [ready, paymentId]);

  async function complete(outcome: string) {
    setBusy(true);
    try {
      await post("/payments/sandbox/complete", { payment_id: paymentId, token, outcome });
      router.push(`/checkout/return?payment=${paymentId}${outcome !== "succeeded" ? "&cancelled=1" : ""}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
      setBusy(false);
    }
  }
  if (!p && !error) return <Spinner />;
  return (
    <Card className="w-full max-w-md space-y-5 p-7">
      <Alert tone="warn" title="Test mode — no real payment">This is the sandbox payment provider used for development. No card is charged. A real provider (PayHere) is enabled in production.</Alert>
      {error && <Alert tone="bad">{error}</Alert>}
      {p && (<>
        <div className="flex items-center gap-3"><FlaskConical className="h-6 w-6 text-accent" aria-hidden /><div><p className="text-sm text-ink-3">Amount</p><p className="text-2xl font-semibold text-ink">{amount(p.amount, p.currency)}</p></div></div>
        <p className="text-sm text-ink-2">Purpose: {p.purpose.replace("_", " ")}</p>
        {p.status !== "pending" ? <Alert tone="info">This payment is already {p.status}.</Alert> : (
          <div className="grid gap-2">
            <Button onClick={() => complete("succeeded")} loading={busy}>Simulate successful payment</Button>
            <Button variant="secondary" onClick={() => complete("failed")} disabled={busy}>Simulate declined card</Button>
            <Button variant="ghost" onClick={() => complete("cancelled")} disabled={busy}>Cancel</Button>
          </div>
        )}
      </>)}
    </Card>
  );
}

export default function Page() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-8 px-4">
      <Logo />
      <Suspense fallback={<Spinner />}><SandboxCheckout /></Suspense>
    </div>
  );
}
