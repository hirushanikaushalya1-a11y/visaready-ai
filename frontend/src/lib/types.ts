export type Me = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_staff: boolean;
  mfa_enabled: boolean;
  permissions: string[];
  ai_training_consent: boolean;
  marketing_consent: boolean;
};

export type Country = { code: string; name: string; region: string | null; module_status: "live" | "pilot" | "planned"; is_source_market: boolean };
export type VisaCategory = {
  id: string; code: string; name: string; category_type: "student" | "work" | "family";
  description: string | null; official_url: string | null; requirement_count: number;
};
export type Service = {
  code: string; kind: string; name: string; description: string; price_cents: number | null; currency: string;
  sla_hours: number | null; required_information: string[]; inclusions: string[]; exclusions: string[]; disclaimer: string | null;
  restricted_countries: string[];
};

export type Application = {
  id: string; title: string; status: "draft" | "active" | "completed" | "archived";
  country_code: string; country_name: string; country_module_status: string;
  visa_category: { id: string; name: string; category_type: string; official_url: string | null };
  details: Record<string, unknown>; created_at: string; unlocked_at: string | null;
  reassessments: { included: number; assessments_run: number; remaining: number };
  latest_assessment: { id: string; version: number; status: string; score: number | null; created_at: string } | null;
  document_count: number; limits: { max_documents: number; max_file_size_mb: number };
  retention_delete_after: string | null;
  report_unlocked: boolean;
  family_members?: { id: string; relation: string; full_name: string; date_of_birth: string | null; included_in_application: boolean }[];
  checklist_state?: Record<string, { collected: boolean; note: string | null }>;
  payment?: { id: string; status: string } | null;
};

export type Trigger = { type: string; document_id?: string; filename?: string; page?: number | null; snippet?: string | null; path?: string; value?: string | null; item_key?: string };
export type Finding = {
  id: string; fingerprint: string; kind: string; category: string; severity: "high" | "medium" | "low" | "info";
  certainty: string; title: string; explanation: string; why_it_matters: string | null; triggers: Trigger[];
  source_url: string | null; suggested_action: string | null; evidence_suggestions: string[]; confidence: string;
};
export type ChecklistItem = {
  item_key: string; title: string; reason: string; origin: "requirement" | "evidence_rule"; level: string;
  classifications: string[]; status: string; document_types: string[]; matched_document_ids: string[];
  unconfirmed_document_ids: string[]; source_url: string | null; source_verified: boolean; last_verified_at: string | null;
};
export type Claim = {
  claim_key: string; category: string; statement: string; source: string; status: string; explanation: string; related: string[];
  evidence: { document_type: string; label: string; required: boolean; owner: string | null; document_ids: string[]; state: string }[];
};
export type ScoreComponent = { ratio: number | null; points: number | null; max_points: number; explanation: string; deductions?: { title: string; points: number }[] };
export type Assessment = {
  id: string; application_id: string; version: number; status: string; readiness_score: number | null;
  score_breakdown: { components: Record<string, ScoreComponent>; note: string };
  summary: { counts: Record<string, number>; limitations: string[]; disclaimer: string; country_module_status: string };
  ai_provider: string; created_at: string; completed_at: string | null; error: string | null;
  findings: Finding[]; checklist: ChecklistItem[]; claims: Claim[];
};
export type Doc = {
  id: string; filename: string; content_type: string; size_bytes: number; declared_type: string | null; detected_type: string | null;
  detected_type_label: string | null; classification_confidence: number | null; status: string; page_count: number | null;
  checklist_item_key: string | null; quality: { issues?: string[]; non_latin_scripts?: string[] }; processing_error: string | null;
  created_at: string; authenticity_note: string;
  fields?: { name: string; value: string; normalized: string | null; page: number | null; snippet: string | null; confidence: number; method: string }[];
};
export type Diff = {
  before: { version: number; score: number }; after: { version: number; score: number }; score_delta: number;
  score_explanations: { component: string; delta: number; now: string }[];
  issues_resolved: { fingerprint: string; title: string; severity: string }[];
  new_issues: { fingerprint: string; title: string; severity: string }[];
  remaining_issues: { fingerprint: string; title: string; severity: string }[];
  checklist_changes: { item_key: string; title: string; from: string | null; to: string }[];
  claim_changes: { claim_key: string; statement: string; from: string; to: string }[];
  note: string;
};
export type WritingOrder = {
  id: string; reference: string; service_code: string; service_name: string; price: string; currency: string; quantity: number; status: string;
  customer_notes: string | null; missing_information_note: string | null; submission_email: string; required_information: string[];
  disclaimer: string | null; paid_at: string | null; info_complete_at: string | null; deadline_at: string | null;
  seconds_remaining: number | null; delivered_at: string | null; refund_eligible: boolean; created_at: string;
  deliverables: { id: string; filename: string; created_at: string }[];
  events?: { from: string | null; to: string; note: string | null; at: string }[];
  customer?: { name: string; email: string };
};
export type Notification = { id: string; kind: string; title: string; body: string; link: string | null; read: boolean; email_status: string; created_at: string };
