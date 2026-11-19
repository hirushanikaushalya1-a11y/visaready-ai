import { notFound } from "next/navigation";
import { SiteFooter, SiteHeader } from "@/components/shell";

// DRAFT STRUCTURES ONLY — must be reviewed and completed by qualified legal professionals
// (Sri Lanka PDPA 2022, GDPR/UK GDPR for EU/UK users, India DPDP Act 2023, and payment-provider terms) before launch.
const DOCS: Record<string, { title: string; sections: [string, string][] }> = {
  terms: {
    title: "Terms of Service (draft)",
    sections: [
      ["1. Who we are", "VisaReady AI is an independent visa application preparation service. [Legal entity name, registration number and address to be inserted.] We are not affiliated with any government or immigration authority."],
      ["2. What the service is — and is not", "We help you organise evidence and identify potential weaknesses. We do not provide legal or immigration advice, do not submit applications, and cannot guarantee or predict any visa decision. The readiness score measures preparation quality, not the probability of approval."],
      ["3. Your responsibilities", "You must provide truthful information and genuine documents. You remain responsible for everything you submit to any authority. We will not prepare content we know or suspect to be false."],
      ["4. Packages, limits and pricing", "Prices, inclusions, upload limits and reassessment allowances are shown before payment. [Insert tax treatment.]"],
      ["5. Document writing service and 24-hour guarantee", "The 24-hour period starts when we confirm receipt of all required information. If we fail to deliver within that period you are entitled to a full refund of the relevant document fee. Affidavit drafts are not certified, notarised or legally approved. [Insert exclusions and complaint process.]"],
      ["6. Refunds", "Refunds are returned to the original payment method. Processing times depend on your bank or card issuer. [Insert general refund policy for assessments.]"],
      ["7. Professional review", "Reviewers' roles and credentials are disclosed. Unless explicitly stated, reviewers are not licensed immigration advisers."],
      ["8. Liability", "[To be drafted by counsel.]"],
      ["9. Governing law and disputes", "[To be drafted by counsel.]"],
    ],
  },
  privacy: {
    title: "Privacy Policy (draft)",
    sections: [
      ["1. Data we collect", "Account details, profile information you enter, documents you upload, information extracted from them, payment records (not card numbers), and technical logs."],
      ["2. Why we use it", "To provide the assessment and services you request, to secure the platform, to meet legal obligations, and — only with your separate opt-in consent — to improve our models."],
      ["3. Processors", "Hosting/database, object storage, payment provider, email provider and (if enabled) an AI provider under terms that prohibit training on your data. [List named processors and transfer mechanisms.]"],
      ["4. Retention", "Documents are deleted 30 days after you mark an application as submitted (configurable, disclosed in your settings), or earlier on request. Payment records are retained as required by law."],
      ["5. Security", "Per-file AES-256-GCM encryption, role-based staff access, audit logging, short-lived download links."],
      ["6. Your rights", "Access, export, correction and deletion via Privacy & security settings or by contacting support. [Insert regulator contact details per jurisdiction.]"],
      ["7. We never sell your data", "We do not sell or rent personal information or documents."],
    ],
  },
};

export function generateStaticParams() {
  return Object.keys(DOCS).map((doc) => ({ doc }));
}

export default async function LegalPage({ params }: { params: Promise<{ doc: string }> }) {
  const { doc } = await params;
  const d = DOCS[doc];
  if (!d) notFound();
  return (
    <>
      <SiteHeader />
      <main className="mx-auto max-w-3xl px-4 py-12">
        <p className="rounded-lg bg-warn-soft px-4 py-2 text-sm text-warn">Draft structure for legal review — not yet in force.</p>
        <h1 className="mt-6 text-3xl font-semibold text-ink">{d.title}</h1>
        <div className="mt-8 space-y-6">{d.sections.map(([h, b]) => <section key={h}><h2 className="font-semibold text-ink">{h}</h2><p className="mt-1 text-sm leading-relaxed text-ink-2">{b}</p></section>)}</div>
      </main>
      <SiteFooter />
    </>
  );
}
