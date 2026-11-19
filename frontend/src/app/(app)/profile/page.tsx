"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { put } from "@/lib/api";
import { useLoad } from "@/lib/auth";
import type { Country } from "@/lib/types";
import { PageHeader } from "@/components/shell";
import { Alert, Button, Card, Field, Input, Progress, Select, Spinner, Tabs, Textarea } from "@/components/ui";

type Q = { level: string; title: string; institution?: string; country?: string; completion_date?: string; result?: string };
type Job = { employer: string; job_title?: string; start_date?: string; end_date?: string; monthly_salary?: number | null; currency?: string };
type Profile = {
  given_names: string | null; family_name: string | null; date_of_birth: string | null; nationality: string | null; residence_country: string | null;
  marital_status: string | null; passport_number: string | null; passport_expiry: string | null; phone: string | null; completion: number;
  academic: { qualifications?: Q[]; english_test?: { type?: string; overall_score?: number | null; test_date?: string } };
  employment: { status?: string; history?: Job[]; career_change?: boolean | null; regulated_occupation?: boolean | null };
  financial: { funding_source?: string; savings_amount?: number | null; savings_currency?: string; declared_large_deposits?: boolean | null;
    large_deposit_explanation?: string; has_education_loan?: boolean | null; loan_amount?: number | null; liabilities?: string;
    sponsor?: { name?: string; relationship?: string; employment_type?: string; annual_income?: number | null; currency?: string } };
  immigration_history: { has_previous_refusals?: boolean | null; previous_refusals?: { country?: string; year?: number | null; visa_type?: string }[];
    previous_visas?: { country?: string; year?: number | null; visa_type?: string }[]; overstays?: boolean | null; overstay_details?: string };
};

const clean = <T extends object>(o: T): T => JSON.parse(JSON.stringify(o, (_k, v) => (v === "" ? undefined : v)));
const num = (v: string) => (v === "" ? null : Number(v));
const yn = (v: string) => (v === "" ? null : v === "yes");
const ynv = (b?: boolean | null) => (b == null ? "" : b ? "yes" : "no");
const ym = "YYYY-MM";

function YesNo({ value, onChange, id }: { value?: boolean | null; onChange: (v: boolean | null) => void; id?: string }) {
  return <Select id={id} value={ynv(value)} onChange={(e) => onChange(yn(e.target.value))}><option value="">Select…</option><option value="yes">Yes</option><option value="no">No</option></Select>;
}

export default function ProfilePage() {
  const { data } = useLoad<Profile>("/profile");
  const { data: countries } = useLoad<Country[]>("/countries?kind=all");
  if (!data) return <Spinner />;
  return <ProfileForm initial={data} countries={countries ?? []} />;
}

function ProfileForm({ initial, countries }: { initial: Profile; countries: Country[] }) {
  const [tab, setTab] = useState("personal");
  const [p, setP] = useState<Profile>(() => structuredClone(initial));
  const [msg, setMsg] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const up = (patch: Partial<Profile>) => setP({ ...p, ...patch });
  async function save(section: string) {
    setBusy(true);
    setMsg(null);
    const body: Record<string, unknown> =
      section === "personal"
        ? { given_names: p!.given_names, family_name: p!.family_name, date_of_birth: p!.date_of_birth || null, nationality: p!.nationality || null,
            residence_country: p!.residence_country || null, marital_status: p!.marital_status || null, passport_number: p!.passport_number || null,
            passport_expiry: p!.passport_expiry || null, phone: p!.phone || null }
        : { [section]: clean((p as Record<string, unknown>)[section] as object) };
    try {
      const r = await put<Profile>("/profile", body);
      setP(r);
      setMsg({ tone: "ok", text: "Saved. Re-run your assessment to reflect these changes." });
    } catch (e) {
      setMsg({ tone: "bad", text: e instanceof Error ? e.message : "Save failed" });
    } finally {
      setBusy(false);
    }
  }

  const countryOpts = countries.map((c) => <option key={c.code} value={c.code}>{c.name}</option>);
  const quals = p.academic.qualifications ?? [];
  const jobs = p.employment.history ?? [];
  const sp = p.financial.sponsor ?? {};
  const refusals = p.immigration_history.previous_refusals ?? [];

  return (
    <div className="space-y-6">
      <PageHeader title="My profile" subtitle="Tell us about yourself truthfully and completely. We compare this with your documents." />
      <Card><div className="flex items-center gap-4"><span className="text-sm text-ink-2">Profile completion</span><div className="flex-1"><Progress value={p.completion} /></div><span className="text-sm font-medium tabular-nums">{p.completion}%</span></div></Card>
      <Tabs active={tab} onChange={(t) => { setTab(t); setMsg(null); }} tabs={[
        { id: "personal", label: "Personal" }, { id: "academic", label: "Education" }, { id: "employment", label: "Employment" },
        { id: "financial", label: "Finances" }, { id: "immigration_history", label: "Immigration history" }]} />
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}

      {tab === "personal" && (
        <Card className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Given names (as in passport)" htmlFor="gn"><Input id="gn" value={p.given_names ?? ""} onChange={(e) => up({ given_names: e.target.value })} /></Field>
          <Field label="Family name / surname" htmlFor="fn"><Input id="fn" value={p.family_name ?? ""} onChange={(e) => up({ family_name: e.target.value })} /></Field>
          <Field label="Date of birth" htmlFor="dob"><Input id="dob" type="date" value={p.date_of_birth ?? ""} onChange={(e) => up({ date_of_birth: e.target.value })} /></Field>
          <Field label="Marital status" htmlFor="ms"><Select id="ms" value={p.marital_status ?? ""} onChange={(e) => up({ marital_status: e.target.value })}>
            <option value="">Select…</option>{["single", "married", "partnered", "divorced", "widowed", "separated"].map((m) => <option key={m} value={m}>{m}</option>)}</Select></Field>
          <Field label="Nationality" htmlFor="nat"><Select id="nat" value={p.nationality ?? ""} onChange={(e) => up({ nationality: e.target.value })}><option value="">Select…</option>{countryOpts}</Select></Field>
          <Field label="Country of residence" htmlFor="res"><Select id="res" value={p.residence_country ?? ""} onChange={(e) => up({ residence_country: e.target.value })}><option value="">Select…</option>{countryOpts}</Select></Field>
          <Field label="Passport number" htmlFor="pp"><Input id="pp" value={p.passport_number ?? ""} onChange={(e) => up({ passport_number: e.target.value.toUpperCase() })} /></Field>
          <Field label="Passport expiry date" htmlFor="ppe"><Input id="ppe" type="date" value={p.passport_expiry ?? ""} onChange={(e) => up({ passport_expiry: e.target.value })} /></Field>
          <Field label="Phone (optional)" htmlFor="ph"><Input id="ph" value={p.phone ?? ""} onChange={(e) => up({ phone: e.target.value })} /></Field>
          <div className="sm:col-span-2"><Button onClick={() => save("personal")} loading={busy}>Save personal details</Button></div>
        </Card>
      )}

      {tab === "academic" && (
        <Card className="space-y-6">
          <div className="space-y-4">
            <h3 className="font-semibold text-ink">Qualifications</h3>
            {quals.map((q, i) => {
              const setQ = (patch: Partial<Q>) => { const n = [...quals]; n[i] = { ...q, ...patch }; up({ academic: { ...p.academic, qualifications: n } }); };
              return (
                <div key={i} className="grid grid-cols-1 gap-3 rounded-lg border border-line p-4 sm:grid-cols-3">
                  <Field label="Level"><Select value={q.level} onChange={(e) => setQ({ level: e.target.value })}>{["secondary", "diploma", "bachelor", "master", "doctorate", "professional", "other"].map((l) => <option key={l}>{l}</option>)}</Select></Field>
                  <Field label="Title"><Input value={q.title} placeholder="BSc Computer Science" onChange={(e) => setQ({ title: e.target.value })} /></Field>
                  <Field label="Institution"><Input value={q.institution ?? ""} onChange={(e) => setQ({ institution: e.target.value })} /></Field>
                  <Field label="Completion (year-month)" hint={ym}><Input value={q.completion_date ?? ""} placeholder="2021-12" onChange={(e) => setQ({ completion_date: e.target.value })} /></Field>
                  <Field label="Result / grade"><Input value={q.result ?? ""} onChange={(e) => setQ({ result: e.target.value })} /></Field>
                  <div className="flex items-end"><Button variant="ghost" onClick={() => up({ academic: { ...p.academic, qualifications: quals.filter((_, j) => j !== i) } })}><Trash2 className="h-4 w-4" aria-hidden /> Remove</Button></div>
                </div>
              );
            })}
            <Button variant="secondary" onClick={() => up({ academic: { ...p.academic, qualifications: [...quals, { level: "bachelor", title: "" }] } })}><Plus className="h-4 w-4" aria-hidden /> Add qualification</Button>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <h3 className="font-semibold text-ink sm:col-span-3">English language test</h3>
            <Field label="Test"><Select value={p.academic.english_test?.type ?? ""} onChange={(e) => up({ academic: { ...p.academic, english_test: { ...p.academic.english_test, type: e.target.value } } })}>
              <option value="">None / not yet</option>{["IELTS Academic", "IELTS General", "IELTS UKVI", "TOEFL iBT", "PTE Academic", "Duolingo", "Cambridge", "Other"].map((t) => <option key={t}>{t}</option>)}</Select></Field>
            <Field label="Overall score"><Input type="number" step="0.5" value={p.academic.english_test?.overall_score ?? ""} onChange={(e) => up({ academic: { ...p.academic, english_test: { ...p.academic.english_test, overall_score: num(e.target.value) } } })} /></Field>
            <Field label="Test date" hint={ym}><Input value={p.academic.english_test?.test_date ?? ""} placeholder="2025-11" onChange={(e) => up({ academic: { ...p.academic, english_test: { ...p.academic.english_test, test_date: e.target.value } } })} /></Field>
          </div>
          <Button onClick={() => save("academic")} loading={busy}>Save education</Button>
        </Card>
      )}

      {tab === "employment" && (
        <Card className="space-y-6">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Field label="Current status"><Select value={p.employment.status ?? ""} onChange={(e) => up({ employment: { ...p.employment, status: e.target.value } })}>
              <option value="">Select…</option>{["employed", "self_employed", "unemployed", "student", "retired", "other"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</Select></Field>
            <Field label="Are you changing career direction?"><YesNo value={p.employment.career_change} onChange={(v) => up({ employment: { ...p.employment, career_change: v } })} /></Field>
            <Field label="Is your occupation regulated / licensed?"><YesNo value={p.employment.regulated_occupation} onChange={(v) => up({ employment: { ...p.employment, regulated_occupation: v } })} /></Field>
          </div>
          <div className="space-y-4">
            <h3 className="font-semibold text-ink">Employment history</h3>
            {jobs.map((j, i) => {
              const setJ = (patch: Partial<Job>) => { const n = [...jobs]; n[i] = { ...j, ...patch }; up({ employment: { ...p.employment, history: n } }); };
              return (
                <div key={i} className="grid grid-cols-1 gap-3 rounded-lg border border-line p-4 sm:grid-cols-3">
                  <Field label="Employer"><Input value={j.employer} onChange={(e) => setJ({ employer: e.target.value })} /></Field>
                  <Field label="Job title"><Input value={j.job_title ?? ""} onChange={(e) => setJ({ job_title: e.target.value })} /></Field>
                  <Field label="Monthly salary"><Input type="number" value={j.monthly_salary ?? ""} onChange={(e) => setJ({ monthly_salary: num(e.target.value) })} /></Field>
                  <Field label="Start (year-month)" hint={ym}><Input value={j.start_date ?? ""} placeholder="2022-03" onChange={(e) => setJ({ start_date: e.target.value })} /></Field>
                  <Field label="End (blank if current)" hint={ym}><Input value={j.end_date ?? ""} onChange={(e) => setJ({ end_date: e.target.value })} /></Field>
                  <div className="flex items-end"><Button variant="ghost" onClick={() => up({ employment: { ...p.employment, history: jobs.filter((_, k) => k !== i) } })}><Trash2 className="h-4 w-4" aria-hidden /> Remove</Button></div>
                </div>
              );
            })}
            <Button variant="secondary" onClick={() => up({ employment: { ...p.employment, history: [...jobs, { employer: "" }] } })}><Plus className="h-4 w-4" aria-hidden /> Add job</Button>
          </div>
          <Button onClick={() => save("employment")} loading={busy}>Save employment</Button>
        </Card>
      )}

      {tab === "financial" && (
        <Card className="space-y-6">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Field label="How will you fund this?"><Select value={p.financial.funding_source ?? ""} onChange={(e) => up({ financial: { ...p.financial, funding_source: e.target.value } })}>
              <option value="">Select…</option><option value="self">My own funds</option><option value="sponsor">A sponsor (e.g. parent)</option><option value="mixed">Both</option><option value="scholarship">Scholarship</option><option value="employer">Employer</option></Select></Field>
            <Field label="Your savings"><Input type="number" value={p.financial.savings_amount ?? ""} onChange={(e) => up({ financial: { ...p.financial, savings_amount: num(e.target.value) } })} /></Field>
            <Field label="Currency"><Input maxLength={3} placeholder="LKR" value={p.financial.savings_currency ?? ""} onChange={(e) => up({ financial: { ...p.financial, savings_currency: e.target.value.toUpperCase() } })} /></Field>
          </div>
          {["sponsor", "mixed"].includes(p.financial.funding_source ?? "") && (
            <div className="grid grid-cols-1 gap-3 rounded-lg bg-surface-2 p-4 sm:grid-cols-2">
              <h3 className="font-semibold text-ink sm:col-span-2">Sponsor</h3>
              <Field label="Sponsor's full name (as on their bank account)"><Input value={sp.name ?? ""} onChange={(e) => up({ financial: { ...p.financial, sponsor: { ...sp, name: e.target.value } } })} /></Field>
              <Field label="Relationship to you"><Select value={sp.relationship ?? ""} onChange={(e) => up({ financial: { ...p.financial, sponsor: { ...sp, relationship: e.target.value } } })}>
                <option value="">Select…</option>{["father", "mother", "parent", "spouse", "sibling", "uncle", "aunt", "grandparent", "relative", "employer", "other"].map((r) => <option key={r}>{r}</option>)}</Select></Field>
              <Field label="Sponsor's income type"><Select value={sp.employment_type ?? ""} onChange={(e) => up({ financial: { ...p.financial, sponsor: { ...sp, employment_type: e.target.value } } })}>
                <option value="">Select…</option><option value="salaried">Salaried employee</option><option value="self_employed">Self-employed</option><option value="business_owner">Business owner</option><option value="retired">Retired</option><option value="other">Other</option></Select></Field>
              <Field label="Sponsor's annual income"><Input type="number" value={sp.annual_income ?? ""} onChange={(e) => up({ financial: { ...p.financial, sponsor: { ...sp, annual_income: num(e.target.value) } } })} /></Field>
            </div>
          )}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Any large recent deposits in the accounts you'll use?"><YesNo value={p.financial.declared_large_deposits} onChange={(v) => up({ financial: { ...p.financial, declared_large_deposits: v } })} /></Field>
            <Field label="Education loan?"><YesNo value={p.financial.has_education_loan} onChange={(v) => up({ financial: { ...p.financial, has_education_loan: v } })} /></Field>
            {p.financial.declared_large_deposits && <div className="sm:col-span-2"><Field label="Where did the large deposits come from?" hint="Be specific and truthful (e.g. 'sale of land in March 2026, deed attached')."><Textarea value={p.financial.large_deposit_explanation ?? ""} onChange={(e) => up({ financial: { ...p.financial, large_deposit_explanation: e.target.value } })} /></Field></div>}
          </div>
          <Button onClick={() => save("financial")} loading={busy}>Save finances</Button>
        </Card>
      )}

      {tab === "immigration_history" && (
        <Card className="space-y-6">
          <Alert tone="info">Answer honestly. Previous refusals usually must be disclosed, and failing to disclose them can be far more serious than the refusal itself.</Alert>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Have you ever been refused a visa for any country?"><YesNo value={p.immigration_history.has_previous_refusals} onChange={(v) => up({ immigration_history: { ...p.immigration_history, has_previous_refusals: v } })} /></Field>
            <Field label="Have you ever overstayed or breached visa conditions?"><YesNo value={p.immigration_history.overstays} onChange={(v) => up({ immigration_history: { ...p.immigration_history, overstays: v } })} /></Field>
          </div>
          {p.immigration_history.has_previous_refusals && (
            <div className="space-y-3">
              {refusals.map((r, i) => {
                const setR = (patch: object) => { const n = [...refusals]; n[i] = { ...r, ...patch }; up({ immigration_history: { ...p.immigration_history, previous_refusals: n } }); };
                return (
                  <div key={i} className="grid grid-cols-1 gap-3 rounded-lg border border-line p-4 sm:grid-cols-4">
                    <Field label="Country"><Select value={r.country ?? ""} onChange={(e) => setR({ country: e.target.value })}><option value="">Select…</option>{countryOpts}</Select></Field>
                    <Field label="Year"><Input type="number" value={r.year ?? ""} onChange={(e) => setR({ year: num(e.target.value) })} /></Field>
                    <Field label="Visa type"><Input value={r.visa_type ?? ""} onChange={(e) => setR({ visa_type: e.target.value })} /></Field>
                    <div className="flex items-end"><Button variant="ghost" onClick={() => up({ immigration_history: { ...p.immigration_history, previous_refusals: refusals.filter((_, j) => j !== i) } })}><Trash2 className="h-4 w-4" aria-hidden /></Button></div>
                  </div>
                );
              })}
              <Button variant="secondary" onClick={() => up({ immigration_history: { ...p.immigration_history, previous_refusals: [...refusals, {}] } })}><Plus className="h-4 w-4" aria-hidden /> Add refusal</Button>
            </div>
          )}
          {p.immigration_history.overstays && <Field label="Details of the overstay or breach"><Textarea value={p.immigration_history.overstay_details ?? ""} onChange={(e) => up({ immigration_history: { ...p.immigration_history, overstay_details: e.target.value } })} /></Field>}
          <Button onClick={() => save("immigration_history")} loading={busy}>Save immigration history</Button>
        </Card>
      )}
    </div>
  );
}
