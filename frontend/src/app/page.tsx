import Link from "next/link";
import {
  ArrowRight, Briefcase, CheckCircle2, FileSearch, FileWarning, GitCompare, GraduationCap, HelpCircle, Languages, Lock,
  Network, ScanText, ShieldCheck, Sparkles, UserCheck, Users,
} from "lucide-react";
import { SiteFooter, SiteHeader } from "@/components/shell";
import { Coverage, Pricing } from "@/components/landing-data";

const steps = [
  ["Create your application", "Choose your nationality, destination and visa category. We build your requirement set from our country knowledge base."],
  ["Tell us your story", "Answer guided questions about your studies, work, finances, family and travel history."],
  ["Upload your evidence", "Securely upload passports, certificates, bank statements and letters. Everything is encrypted."],
  ["Get your free readiness assessment", "See how strong your file is: what's missing, what conflicts, what a decision-maker might ask — and how to fix it."],
  ["Improve, or let us help", "Reassess for free as you improve. Get the full report with drafts, or have us write your SOP and letters."],
];

const evidence = [
  { icon: FileSearch, t: "Missing Evidence Detective", d: "Declared that your father is sponsoring you? We identify the bank statements, income evidence and relationship proof that substantiate it — and tell you why each matters." },
  { icon: Network, t: "Proof Builder", d: "Every claim you make is mapped to the documents that support it, with a clear status: supported, partially supported, unsupported or conflicting." },
  { icon: HelpCircle, t: "What questions could your application raise?", d: "Prepare truthful answers to questions a decision-maker could reasonably ask — about study gaps, course choice or the source of funds." },
  { icon: GitCompare, t: "Application Strength Simulator", d: "Compare assessment versions side by side. Scores only rise when new evidence actually resolves an issue." },
];

const faqs = [
  ["Does VisaReady AI guarantee my visa?", "No. Nobody can. Decisions are made by immigration authorities. We help you prepare a complete, consistent application and understand potential weaknesses."],
  ["What does the readiness score mean?", "It measures how complete and consistent your application preparation is — profile answers, required documents, evidence for your claims and consistency between documents. It is not a probability of approval."],
  ["Where do the requirements come from?", "Only from official government and immigration-authority sources. Each requirement shows its source link and the date our team last verified it. Where we have not verified something, we say so."],
  ["Is my data safe?", "Documents are encrypted with a unique key per file, never publicly accessible, and deleted 30 days after you complete your application (or sooner on request). We never sell your data or use it to train AI without your explicit consent."],
  ["Can AI check if my documents are genuine?", "No. We check readability and consistency between documents. We cannot verify authenticity with issuing authorities, and we say so on every document."],
  ["Is this legal advice?", "No. VisaReady AI is not a law firm or a licensed immigration adviser. Where your situation needs professional judgement (for example previous overstays) we tell you."],
];

export default function Home() {
  return (
    <>
      <SiteHeader />
      <main>
        {/* 1. Hero */}
        <section className="relative overflow-hidden bg-navy text-white">
          <div className="absolute inset-0 opacity-[0.07]" style={{ backgroundImage: "radial-gradient(circle at 1px 1px, white 1px, transparent 0)", backgroundSize: "28px 28px" }} />
          <div className="relative mx-auto grid grid-cols-1 max-w-6xl gap-12 px-4 py-16 md:py-24 lg:grid-cols-2 lg:items-center">
            <div>
              <p className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-white/80"><Sparkles className="h-3.5 w-3.5" aria-hidden /> Evidence Intelligence for visa applicants</p>
              <h1 className="mt-5 text-4xl font-semibold leading-tight tracking-tight md:text-5xl">Prepare Your Visa Application With Confidence.</h1>
              <p className="mt-5 max-w-xl text-lg text-white/75">An intelligent visa preparation platform that helps you understand your requirements, organise your evidence and identify potential application weaknesses before submission.</p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link href="/register" className="inline-flex h-12 items-center gap-2 rounded-lg bg-white px-6 text-sm font-semibold text-navy hover:bg-white/90">Check my file for free <ArrowRight className="h-4 w-4" aria-hidden /></Link>
                <Link href="/#how" className="inline-flex h-12 items-center rounded-lg border border-white/25 px-6 text-sm font-medium text-white hover:bg-white/10">See how it works</Link>
              </div>
              <p className="mt-6 text-xs text-white/55">Independent service · Not affiliated with any government · No approval guarantees</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-5 shadow-2xl">
              <div className="flex items-center justify-between"><p className="text-xs uppercase tracking-wide text-white/60">Illustrative example report</p><span className="rounded-full bg-white/10 px-2 py-0.5 text-[11px] text-white/70">Sample data</span></div>
              <div className="mt-4 space-y-3">
                {[
                  ["Sponsor's salary evidence", "Missing", "bg-red-400/20 text-red-200"],
                  ["Date of birth on birth certificate", "Differs from passport · page 1", "bg-amber-400/20 text-amber-100"],
                  ["Confirmation of Acceptance for Studies", "Recognised", "bg-emerald-400/20 text-emerald-100"],
                  ["Large deposit on 18 Mar", "Prepare source-of-funds evidence", "bg-amber-400/20 text-amber-100"],
                ].map(([a, b, c]) => (
                  <div key={a} className="flex items-center justify-between gap-3 rounded-lg bg-white/[0.06] px-4 py-3">
                    <span className="text-sm text-white/90">{a}</span><span className={`rounded-full px-2 py-0.5 text-[11px] ${c}`}>{b}</span>
                  </div>
                ))}
              </div>
              <p className="mt-4 text-xs text-white/50">Every finding cites the document and page it came from.</p>
            </div>
          </div>
        </section>

        {/* 2. How it works */}
        <section id="how" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20">
          <h2 className="text-3xl font-semibold tracking-tight text-ink">How it works</h2>
          <ol className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-5">
            {steps.map(([t, d], i) => (
              <li key={t} className="relative">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-navy text-sm font-semibold text-white">{i + 1}</span>
                <h3 className="mt-4 font-semibold text-ink">{t}</h3>
                <p className="mt-1.5 text-sm text-ink-3">{d}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* 3. AI-powered assessment */}
        <section className="border-y border-line bg-surface">
          <div className="mx-auto grid grid-cols-1 max-w-6xl gap-10 px-4 py-20 lg:grid-cols-2">
            <div>
              <h2 className="text-3xl font-semibold tracking-tight text-ink">An assessment that explains itself</h2>
              <p className="mt-4 text-ink-2">Your readiness report separates confirmed missing requirements from potential concerns and matters that need professional judgement. For every concern you see what the issue is, why it matters, which document triggered it, and how to address it.</p>
              <ul className="mt-6 space-y-3 text-sm text-ink-2">
                {["Profile assessment across academic, employment, financial and immigration history", "Personalised country-specific checklist, with the official source for every requirement", "Previous refusal analysis that compares stated reasons with your current evidence", "Readiness score with a component-by-component breakdown"].map((x) => (
                  <li key={x} className="flex gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-hidden />{x}</li>
                ))}
              </ul>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-1">
              {[[GraduationCap, "Student visas", "Academic progression, study gaps, English, financial capacity, genuine study plans."],
                [Briefcase, "Work visas", "Job offers, sponsorship, occupation, experience evidence, registration and skills assessments."],
                [Users, "Family & dependants", "Relationship evidence, dependants, principal's status and shared financial evidence."]].map(([Icon, t, d]) => {
                const I = Icon as typeof GraduationCap;
                return (
                  <div key={t as string} className="flex gap-4 rounded-xl border border-line p-5">
                    <I className="h-6 w-6 shrink-0 text-accent" aria-hidden />
                    <div><h3 className="font-semibold text-ink">{t as string}</h3><p className="mt-1 text-sm text-ink-3">{d as string}</p></div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* 4. Evidence Intelligence */}
        <section id="evidence" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20">
          <h2 className="text-3xl font-semibold tracking-tight text-ink">Evidence Intelligence — not just a checklist</h2>
          <p className="mt-3 max-w-2xl text-ink-2">VisaReady AI understands what your documents are meant to demonstrate, and whether your evidence actually supports what you say.</p>
          <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-2">
            {evidence.map(({ icon: Icon, t, d }) => (
              <div key={t} className="rounded-xl border border-line bg-surface p-6">
                <Icon className="h-6 w-6 text-accent" aria-hidden />
                <h3 className="mt-4 font-semibold text-ink">{t}</h3>
                <p className="mt-2 text-sm text-ink-3">{d}</p>
              </div>
            ))}
          </div>
        </section>

        {/* 5. Document consistency */}
        <section className="border-y border-line bg-surface">
          <div className="mx-auto grid grid-cols-1 max-w-6xl gap-10 px-4 py-20 lg:grid-cols-2 lg:items-center">
            <div>
              <ScanText className="h-7 w-7 text-accent" aria-hidden />
              <h2 className="mt-4 text-3xl font-semibold tracking-tight text-ink">Cross-document consistency checking</h2>
              <p className="mt-4 text-ink-2">We read every page (including scanned documents), extract names, dates, passport numbers, balances and employment dates, and compare them with each other and with your declarations.</p>
            </div>
            <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {["Name spelling and initials", "Date-of-birth discrepancies", "Passport numbers & expiry", "Employment dates and titles", "Declared savings vs statements", "Significant deposits", "Undisclosed previous refusals", "Missing pages & poor scans"].map((x) => (
                <li key={x} className="flex items-center gap-2 rounded-lg bg-surface-2 px-4 py-3 text-sm text-ink-2"><FileWarning className="h-4 w-4 text-warn" aria-hidden />{x}</li>
              ))}
            </ul>
          </div>
        </section>

        {/* 6/7. Coverage & categories */}
        <section className="mx-auto max-w-6xl px-4 py-20">
          <h2 className="text-3xl font-semibold tracking-tight text-ink">Country coverage</h2>
          <p className="mt-3 max-w-2xl text-ink-2">Built for applicants from Sri Lanka, India, Bangladesh and Nepal — and open to applicants of any nationality. We are honest about the status of each country module.</p>
          <div className="mt-8"><Coverage /></div>
        </section>

        {/* 8/9. Pricing + writing */}
        <section id="pricing" className="scroll-mt-20 border-y border-line bg-surface">
          <div className="mx-auto max-w-6xl px-4 py-20">
            <h2 className="text-3xl font-semibold tracking-tight text-ink">Free assessment. Pay only for what you need.</h2>
            <p className="mt-3 text-ink-2">No subscriptions. Every price and limit is shown before you pay.</p>
            <div className="mt-10"><Pricing /></div>
          </div>
        </section>

        {/* 10/11. Translation + human review */}
        <section className="mx-auto grid grid-cols-1 max-w-6xl gap-6 px-4 py-20 md:grid-cols-2">
          <div className="rounded-xl border border-line bg-surface p-7">
            <Languages className="h-6 w-6 text-accent" aria-hidden />
            <h3 className="mt-4 text-lg font-semibold text-ink">Sworn translations</h3>
            <p className="mt-2 text-sm text-ink-3">Sinhala → English and Tamil → English by Sri Lankan sworn translators, priced per document after review. We automatically flag documents that appear to need translation. AI translations are never presented as certified.</p>
            <p className="mt-3 text-xs font-medium text-warn">Coming soon — translator onboarding in progress.</p>
          </div>
          <div className="rounded-xl border border-line bg-surface p-7">
            <UserCheck className="h-6 w-6 text-accent" aria-hidden />
            <h3 className="mt-4 text-lg font-semibold text-ink">Optional human review</h3>
            <p className="mt-2 text-sm text-ink-3">A trained reviewer checks your AI findings and documents. Each reviewer&apos;s role and credentials are shown — not every reviewer is a licensed immigration adviser, and we never imply otherwise.</p>
            <p className="mt-3 text-xs font-medium text-warn">Coming soon.</p>
          </div>
        </section>

        {/* 12. Privacy */}
        <section className="bg-navy text-white">
          <div className="mx-auto grid grid-cols-1 max-w-6xl gap-8 px-4 py-16 md:grid-cols-3">
            <div className="md:col-span-1"><Lock className="h-7 w-7" aria-hidden /><h2 className="mt-4 text-2xl font-semibold">Privacy and security by design</h2></div>
            <ul className="grid grid-cols-1 gap-4 text-sm text-white/80 sm:grid-cols-2 md:col-span-2">
              {["Each document encrypted with its own AES-256 key", "Downloads only via short-lived links tied to your session", "Staff see only what their role requires — every access is logged", "Documents deleted 30 days after completion, or on request", "Never sold. Never used to train AI without your explicit opt-in", "Card details handled by the payment provider — never stored by us"].map((x) => (
                <li key={x} className="flex gap-2"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden />{x}</li>
              ))}
            </ul>
          </div>
        </section>

        {/* 13. FAQ */}
        <section className="mx-auto max-w-3xl px-4 py-20">
          <h2 className="text-3xl font-semibold tracking-tight text-ink">Frequently asked questions</h2>
          <div className="mt-8 divide-y divide-line rounded-xl border border-line bg-surface">
            {faqs.map(([q, a]) => (
              <details key={q} className="group px-5 py-4">
                <summary className="cursor-pointer list-none font-medium text-ink marker:hidden">{q}</summary>
                <p className="mt-2 text-sm text-ink-2">{a}</p>
              </details>
            ))}
          </div>
        </section>

        {/* 14. CTA */}
        <section className="mx-auto max-w-6xl px-4 pb-20">
          <div className="rounded-2xl bg-surface p-10 text-center ring-1 ring-line">
            <h2 className="text-2xl font-semibold text-ink">Know what your application needs — before you submit it.</h2>
            <p className="mx-auto mt-3 max-w-xl text-ink-3">Create a free account and find out how strong your visa file is — free. Get the full report or professional writing only if you need it.</p>
            <Link href="/register" className="mt-6 inline-flex h-12 items-center gap-2 rounded-lg bg-navy px-6 text-sm font-semibold text-white hover:bg-navy-2">Create your free account <ArrowRight className="h-4 w-4" aria-hidden /></Link>
            <p className="mt-4 text-xs text-ink-3">VisaReady AI is independent and is not affiliated with any government or immigration authority.</p>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
