"""Canonical value sets. Stored as strings (with CHECK constraints on key columns) so that
new values can be added by migration without enum-type rewrites."""

ROLES = {
    "applicant": "Applicant",
    "super_admin": "Super Admin",
    "admin": "Administrator",
    "document_team": "Document Preparation Team",
    "translator": "Translator",
    "reviewer": "Professional Reviewer",
    "support": "Customer Support",
}
STAFF_ROLES = set(ROLES) - {"applicant"}

# permission -> roles granted by default (seeded into role_permissions; editable later)
DEFAULT_PERMISSIONS: dict[str, list[str]] = {
    "admin.access": ["super_admin", "admin", "document_team", "translator", "reviewer", "support"],
    "users.read": ["super_admin", "admin", "support"],
    "users.manage": ["super_admin", "admin"],
    "roles.manage": ["super_admin"],
    "applications.read_all": ["super_admin", "admin", "support"],
    "documents.read_all": ["super_admin", "admin"],
    "knowledge.read": ["super_admin", "admin", "reviewer"],
    "knowledge.manage": ["super_admin", "admin"],
    "knowledge.verify": ["super_admin", "admin"],
    "writing_orders.read": ["super_admin", "admin", "document_team", "support"],
    "writing_orders.manage": ["super_admin", "admin", "document_team"],
    "translation_orders.read_assigned": ["translator"],
    "translation_orders.manage": ["super_admin", "admin"],
    "reviews.perform": ["reviewer"],
    "payments.read": ["super_admin", "admin", "support"],
    "refunds.manage": ["super_admin", "admin"],
    "audit.read": ["super_admin", "admin"],
    "privacy.manage": ["super_admin", "admin"],
    "support.manage": ["super_admin", "admin", "support"],
    "analytics.read": ["super_admin", "admin"],
}

CATEGORY_TYPES = ("student", "work", "family")

DOCUMENT_TYPES = {
    "passport": "Passport",
    "birth_certificate": "Birth certificate",
    "marriage_certificate": "Marriage certificate",
    "academic_certificate": "Academic certificate",
    "academic_transcript": "Academic transcript",
    "bank_statement": "Bank statement",
    "salary_slip": "Salary slip",
    "employment_letter": "Employment confirmation letter",
    "experience_certificate": "Experience certificate",
    "tax_record": "Tax record",
    "business_registration": "Business registration",
    "affidavit": "Affidavit",
    "offer_letter": "University / college offer or acceptance letter",
    "employment_contract": "Employment contract / job offer",
    "english_test_result": "English language test result",
    "travel_document": "Previous visas / travel history",
    "visa_refusal": "Visa refusal decision",
    "sponsorship_letter": "Sponsorship letter",
    "relationship_evidence": "Relationship evidence",
    "cv": "CV / résumé",
    "sop": "Statement of purpose",
    "police_certificate": "Police clearance certificate",
    "medical_report": "Medical examination report",
    "photo": "Photograph",
    "national_id": "National identity card",
    "travel_ticket": "Flight ticket / itinerary",
    "application_form": "Visa application form",
    "fee_receipt": "Tuition / fee payment receipt",
    "financial_document": "Savings, deposits or source of funds",
    "professional_registration": "Professional registration / licence",
    "skills_assessment": "Skills assessment outcome",
    "other": "Other supporting document",
}

REQUIREMENT_LEVELS = ("mandatory", "conditional", "supplementary")
REVIEW_STATUSES = ("draft", "pending_review", "verified", "superseded", "retired")

CHECKLIST_CLASSIFICATIONS = (
    "mandatory",
    "conditionally_required",
    "additional_supporting",
    "missing",
    "requires_clarification",
    "requires_certified_translation",
    "requires_verification",
    "human_review_recommended",
)

EVIDENCE_STATUSES = (
    "supported",
    "partially_supported",
    "unsupported",
    "conflicting",
    "requires_clarification",
    "human_review_recommended",
)

WRITING_ORDER_STATUSES = (
    "payment_pending",
    "payment_successful",
    "awaiting_documents",
    "information_incomplete",
    "submission_complete",
    "processing",
    "quality_review",
    "delivered",
    "refund_eligible",
    "refund_processing",
    "refunded",
    "cancelled",
)

PAYMENT_STATUSES = ("pending", "succeeded", "failed", "cancelled", "refunded", "partially_refunded")
PAYMENT_PURPOSES = ("assessment", "reassessment", "writing_order", "translation_order", "human_review")
