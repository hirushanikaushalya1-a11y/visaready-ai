"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Alert, Button, Field, Input } from "@/components/ui";

export default function RegisterPage() {
  const router = useRouter();
  const { reload } = useAuth();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", accept_terms: false, marketing_consent: false });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await post("/auth/register", form);
      await reload();
      router.push("/dashboard?welcome=1");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-ink">Create your account</h1>
        <p className="mt-1 text-sm text-ink-3">Free to create. You only pay when you unlock an assessment.</p>
      </div>
      {error && <Alert tone="bad">{error}</Alert>}
      <Field label="Full name (as in your passport)" htmlFor="name"><Input id="name" autoComplete="name" required value={form.full_name} onChange={set("full_name")} /></Field>
      <Field label="Email" htmlFor="email"><Input id="email" type="email" autoComplete="email" required value={form.email} onChange={set("email")} /></Field>
      <Field label="Password" hint="At least 10 characters, with upper- and lower-case letters and a number." htmlFor="pw">
        <Input id="pw" type="password" autoComplete="new-password" minLength={10} required value={form.password} onChange={set("password")} />
      </Field>
      <label className="flex gap-2 text-sm text-ink-2">
        <input type="checkbox" className="mt-1" checked={form.accept_terms} onChange={set("accept_terms")} required />
        <span>I agree to the <Link href="/legal/terms" className="text-accent underline">Terms of Service</Link> and <Link href="/legal/privacy" className="text-accent underline">Privacy Policy</Link>, and I understand VisaReady AI does not provide legal advice or guarantee visa outcomes.</span>
      </label>
      <label className="flex gap-2 text-sm text-ink-2">
        <input type="checkbox" className="mt-1" checked={form.marketing_consent} onChange={set("marketing_consent")} />
        <span>Send me occasional product updates (optional).</span>
      </label>
      <Button type="submit" className="w-full" loading={busy}>Create account</Button>
      <p className="text-center text-sm text-ink-3">Already registered? <Link href="/login" className="text-accent hover:underline">Sign in</Link></p>
    </form>
  );
}
