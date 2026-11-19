"use client";

import Link from "next/link";
import { useState } from "react";
import { post } from "@/lib/api";
import { Alert, Button, Field, Input } from "@/components/ui";

export default function ForgotPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await post("/auth/forgot-password", { email });
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="space-y-5">
      <h1 className="text-xl font-semibold text-ink">Reset your password</h1>
      {sent ? (
        <Alert tone="ok" title="Check your email">If an account exists for {email}, we have sent a reset link. It expires in 30 minutes.</Alert>
      ) : (
        <>
          {error && <Alert tone="bad">{error}</Alert>}
          <Field label="Email" htmlFor="email"><Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          <Button type="submit" className="w-full" loading={busy}>Send reset link</Button>
        </>
      )}
      <p className="text-center text-sm"><Link href="/login" className="text-accent hover:underline">Back to sign in</Link></p>
    </form>
  );
}
