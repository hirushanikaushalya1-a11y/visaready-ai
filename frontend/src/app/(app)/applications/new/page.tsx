"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, Briefcase, ExternalLink, GraduationCap, Lock, Users } from "lucide-react";
import { api, money, post } from "@/lib/api";
import { useLoad } from "@/lib/auth";
import { startCheckout } from "@/lib/checkout";
import type { Application, Country, Service, VisaCategory } from "@/lib/types";
import { PageHeader } from "@/components/shell";
import { Alert, Badge, Button, Card, cx, Field, Input, Select, Spinner, Textarea } from "@/components/ui";

type Req = { id: string; title: string; description: string; level: string; source_url: string; review_status: string; last_verified_at: string | null };
const icons = { student: GraduationCap, work: Briefcase, family: Users };
const moduleLabel: Record<string, string> = { live: "Verified", pilot: "Pending verification", planned: "Requirements coming" };

export default function NewApplication() {
  const router = useRouter();
  const { data: countries } = useLoad<Country[]>("/countries?kind=destination");
  const { data: services } = useLoad<Service[]>("/services");
  const [country, setCountry] = useState<Country | null>(null);
  const [catsFor, setCatsFor] = useState<{ code: string; list: VisaCategory[] } | null>(null);
  const cats = country && catsFor?.code === country.code ? catsFor.list : null;
  const [cat, setCat] = useState<VisaCategory | null>(null);
  const [reqs, setReqs] = useState<{ requirements: Req[]; note: string | null } | null>(null);
  const [details, setDetails] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const price = services?.find((s) => s.code === "assessment");

  useEffect(() => {
    if (country) api<VisaCategory[]>(`/countries/${country.code}/visa-categories`).then((list) => setCatsFor({ code: country.code, list }));
  }, [country]);
  useEffect(() => {
    if (cat) api<{ requirements: Req[]; note: string | null }>(`/visa-categories/${cat.id}/requirements`).then(setReqs);
  }, [cat]);

  async function create(pay: boolean) {
    setBusy(true);
    setError(null);
    try {
      const body = Object.fromEntries(Object.entries(details).filter(([, v]) => v !== "").map(([k, v]) => [k, ["tuition_fee", "salary"].includes(k) ? Number(v) : v]));
      const app = await post<Application>("/applications", { country_code: country!.code, visa_category_id: cat!.id, details: body });
      if (pay) await startCheckout("assessment", app.id);
      else router.push(`/applications/${app.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create application");
      setBusy(false);
    }
  }

  const d = (k: string) => ({ value: details[k] ?? "", onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setDetails({ ...details, [k]: e.target.value }) });

  if (!countries) return <Spinner />;
  return (
    <div className="space-y-6">
      <PageHeader title="New application" subtitle="Step-by-step: destination → visa type → your plans → review & unlock." />
      {error && <Alert tone="bad">{error}</Alert>}

      {!country && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {countries.map((c) => (
            <button key={c.code} onClick={() => setCountry(c)} className="flex items-center justify-between rounded-xl border border-line bg-surface p-4 text-left transition hover:border-accent">
              <span className="font-medium text-ink">{c.name}</span>
              <Badge tone={c.module_status === "live" ? "ok" : c.module_status === "pilot" ? "accent" : "neutral"}>{moduleLabel[c.module_status]}</Badge>
            </button>
          ))}
        </div>
      )}

      {country && !cat && (
        <div className="space-y-4">
          <Button variant="ghost" size="sm" onClick={() => setCountry(null)}><ArrowLeft className="h-4 w-4" aria-hidden /> {country.name}</Button>
          {!cats ? <Spinner /> : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {cats.map((c) => {
                const Icon = icons[c.category_type];
                return (
                  <button key={c.id} onClick={() => setCat(c)} className="rounded-xl border border-line bg-surface p-5 text-left transition hover:border-accent">
                    <Icon className="h-6 w-6 text-accent" aria-hidden />
                    <p className="mt-3 font-semibold text-ink">{c.name}</p>
                    <p className="mt-1 text-sm text-ink-3">{c.description}</p>
                    <p className="mt-3 text-xs text-ink-3">{c.requirement_count ? `${c.requirement_count} requirements recorded` : "Detailed requirements not loaded yet"}</p>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {cat && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
          <div className="space-y-6 lg:col-span-3">
            <Button variant="ghost" size="sm" onClick={() => { setCat(null); setReqs(null); }}><ArrowLeft className="h-4 w-4" aria-hidden /> {country!.name} · {cat.name}</Button>
            <Card className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <h2 className="font-semibold text-ink sm:col-span-2">Your plans</h2>
              {cat.category_type === "student" && (<>
                <Field label="Course name"><Input {...d("course_name")} placeholder="MSc Data Science" /></Field>
                <Field label="Institution"><Input {...d("institution")} placeholder="University of Leeds" /></Field>
                <Field label="Course level"><Select {...d("course_level")}><option value="">Select…</option>{["foundation", "diploma", "bachelor", "master", "doctorate", "language", "other"].map((x) => <option key={x}>{x}</option>)}</Select></Field>
                <Field label="Course start" hint="YYYY-MM"><Input {...d("course_start")} placeholder="2026-09" /></Field>
                <Field label="Related to your previous studies or work?"><Select {...d("course_related_to_previous")}><option value="">Select…</option><option value="yes">Yes</option><option value="partly">Partly</option><option value="no">No</option></Select></Field>
                <Field label="Annual tuition fee"><Input type="number" {...d("tuition_fee")} /></Field>
                <div className="sm:col-span-2"><Field label="Career goal after the course"><Textarea {...d("career_goal")} /></Field></div>
              </>)}
              {cat.category_type === "work" && (<>
                <Field label="Employer"><Input {...d("employer")} /></Field>
                <Field label="Job title"><Input {...d("job_title")} /></Field>
                <Field label="Annual salary"><Input type="number" {...d("salary")} /></Field>
                <Field label="Sector"><Select {...d("job_offer_sector")}><option value="">Select…</option>{["education", "health", "social_care", "it", "engineering", "hospitality", "other"].map((x) => <option key={x} value={x}>{x.replace("_", " ")}</option>)}</Select></Field>
                <Field label="Start date" hint="YYYY-MM"><Input {...d("start_date")} /></Field>
              </>)}
              {cat.category_type === "family" && (<>
                <Field label="Your relationship to the main applicant"><Select {...d("relation_to_principal")}><option value="">Select…</option>{["spouse", "partner", "child", "parent", "other"].map((x) => <option key={x}>{x}</option>)}</Select></Field>
                <Field label="Main applicant's full name"><Input {...d("principal_name")} /></Field>
                <div className="sm:col-span-2"><Field label="Main applicant's status (e.g. Skilled Worker visa holder)"><Input {...d("principal_status")} /></Field></div>
              </>)}
            </Card>
          </div>
          <div className="space-y-4 lg:col-span-2">
            <Card>
              <h2 className="font-semibold text-ink">What this visa requires</h2>
              <p className="mt-1 text-xs text-ink-3">Free preview from our knowledge base. Your personalised checklist is built after you unlock.</p>
              {!reqs ? <Spinner /> : reqs.requirements.length ? (
                <ul className="mt-3 space-y-2.5">
                  {reqs.requirements.map((r) => (
                    <li key={r.id} className="text-sm"><div className="flex items-start justify-between gap-2"><span className="text-ink-2">{r.title}</span><Badge tone={r.level === "mandatory" ? "info" : "neutral"}>{r.level}</Badge></div>
                      <a href={r.source_url} target="_blank" rel="noreferrer" className="mt-0.5 inline-flex items-center gap-1 text-xs text-accent">Official source <ExternalLink className="h-3 w-3" aria-hidden /></a>
                      {r.review_status !== "verified" && <span className="ml-2 text-xs text-warn">awaiting verification</span>}</li>
                  ))}
                </ul>
              ) : <Alert tone="warn">{reqs.note}</Alert>}
              {cat.official_url && <a href={cat.official_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs text-accent">Official page for this visa <ExternalLink className="h-3 w-3" aria-hidden /></a>}
            </Card>
            <Card className="border-navy/20">
              <p className="text-sm text-ink-2">Full assessment</p>
              <p className="text-3xl font-semibold text-ink">{price ? money(price.price_cents) : "—"}</p>
              <ul className="mt-2 space-y-1 text-xs text-ink-3">{price?.inclusions.slice(2, 3).concat(price.inclusions.slice(-2)).map((i) => <li key={i}>• {i}</li>)}</ul>
              <Button className={cx("mt-4 w-full")} loading={busy} onClick={() => create(true)}><Lock className="h-4 w-4" aria-hidden /> Create & unlock assessment</Button>
              <Button variant="ghost" className="mt-2 w-full" disabled={busy} onClick={() => create(false)}>Save as draft (pay later)</Button>
              <p className="mt-3 text-[11px] leading-relaxed text-ink-3">{price?.disclaimer}</p>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
