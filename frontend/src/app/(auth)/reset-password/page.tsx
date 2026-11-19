"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { post } from "@/lib/api";
import { Alert, Button, Field, Input } from "@/components/ui";

function ResetForm() {
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await post("/auth/reset-password", { token, password });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setBusy(false);
    }
  }
  if (done) return <div className="space-y-4"><Alert tone="ok" title="Password updated">All other sessions have been signed out.</Alert><Link href="/login" className="block text-center text-sm text-accent">Sign in</Link></div>;
  return (
    <form onSubmit={submit} className="space-y-5">
      <h1 className="text-xl font-semibold text-ink">Choose a new password</h1>
      {!token && <Alert tone="bad">This reset link is missing its token. Please request a new one.</Alert>}
      {error && <Alert tone="bad">{error}</Alert>}
      <Field label="New password" hint="At least 10 characters, with upper- and lower-case letters and a number." htmlFor="pw">
        <Input id="pw" type="password" autoComplete="new-password" minLength={10} required value={password} onChange={(e) => setPassword(e.target.value)} />
      </Field>
      <Button type="submit" className="w-full" loading={busy} disabled={!token}>Update password</Button>
    </form>
  );
}

export default function ResetPage() {
  return <Suspense><ResetForm /></Suspense>;
}
