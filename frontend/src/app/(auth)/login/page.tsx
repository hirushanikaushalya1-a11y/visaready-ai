"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { ApiError, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Me } from "@/lib/types";
import { Alert, Button, Field, Input } from "@/components/ui";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { reload } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfa, setMfa] = useState("");
  const [needMfa, setNeedMfa] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const me = await post<Me>("/auth/login", { email, password, mfa_code: needMfa ? mfa : undefined });
      await reload();
      const next = params.get("next");
      router.push(next && next.startsWith("/") && !next.startsWith("//") ? next : me.is_staff ? "/admin" : "/dashboard");
    } catch (err) {
      if (err instanceof ApiError && err.message === "mfa_required") setNeedMfa(true);
      else setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-ink">Sign in</h1>
        <p className="mt-1 text-sm text-ink-3">Welcome back. Continue preparing your application.</p>
      </div>
      {error && <Alert tone="bad">{error}</Alert>}
      {!needMfa ? (
        <>
          <Field label="Email" htmlFor="email"><Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          <Field label="Password" htmlFor="password"><Input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        </>
      ) : (
        <Field label="Authentication code" hint="Enter the 6-digit code from your authenticator app." htmlFor="mfa">
          <Input id="mfa" inputMode="numeric" autoComplete="one-time-code" autoFocus required value={mfa} onChange={(e) => setMfa(e.target.value)} />
        </Field>
      )}
      <Button type="submit" className="w-full" loading={busy}>{needMfa ? "Verify" : "Sign in"}</Button>
      <div className="flex justify-between text-sm">
        <Link href="/forgot-password" className="text-accent hover:underline">Forgot password?</Link>
        <Link href="/register" className="text-ink-2 hover:text-ink">Create account</Link>
      </div>
    </form>
  );
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}
