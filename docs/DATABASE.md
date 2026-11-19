# Database schema

Generated from the SQLAlchemy models (`backend/app/models/`). Migrations: `backend/migrations/` (Alembic).

Key integrity rules enforced **in the database**, not just in code:

- `uq_payment_success_per_target` — partial unique index: at most one successful payment per (purpose, target) → duplicate-payment protection.
- `payment_events (provider, provider_event_id)` unique → webhook replay protection (only validly-signed events occupy the key).
- `immigration_requirements` CHECK: `review_status <> 'verified' OR last_verified_at IS NOT NULL`.
- `requirement_versions (requirement_id, version)` unique → immutable version history.
- `uq_assessment_version` — partial unique (application_id, version) for non-simulation assessments.
- Level/status CHECK constraints on requirements, evidence rules (never `mandatory`), payments, applications, countries.

## `applicant_profiles`

| Column | Type | Notes |
|---|---|---|
| user_id | UUID | FK → users.id, unique, not null |
| given_names | VARCHAR |  |
| family_name | VARCHAR |  |
| date_of_birth | DATE |  |
| nationality | VARCHAR |  |
| residence_country | VARCHAR |  |
| marital_status | VARCHAR |  |
| passport_number | VARCHAR |  |
| passport_expiry | DATE |  |
| phone | VARCHAR |  |
| academic | JSONB | not null |
| employment | JSONB | not null |
| financial | JSONB | not null |
| immigration_history | JSONB | not null |
| family | JSONB | not null |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `applications`

| Column | Type | Notes |
|---|---|---|
| user_id | UUID | FK → users.id, not null |
| country_code | VARCHAR | FK → countries.code, not null |
| visa_category_id | UUID | FK → visa_categories.id, not null |
| title | VARCHAR | not null |
| status | VARCHAR | not null |
| details | JSONB | not null |
| unlocked_at | DATETIME |  |
| completed_at | DATETIME |  |
| reassessments_allowed | INTEGER | not null |
| assessments_run | INTEGER | not null |
| retention_delete_after | DATETIME |  |
| deleted_at | DATETIME |  |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `assessment_checklist_items`

| Column | Type | Notes |
|---|---|---|
| assessment_id | UUID | FK → assessments.id, not null |
| item_key | VARCHAR | not null |
| title | VARCHAR | not null |
| reason | TEXT | not null |
| origin | VARCHAR | not null |
| level | VARCHAR | not null |
| classifications | JSONB | not null |
| status | VARCHAR | not null |
| document_types | JSONB | not null |
| matched_document_ids | JSONB | not null |
| family_member_id | UUID |  |
| requirement_id | UUID | FK → immigration_requirements.id |
| evidence_rule_id | UUID | FK → evidence_rules.id |
| source_url | VARCHAR |  |
| source_verified | BOOLEAN | not null |
| last_verified_at | DATETIME |  |
| sort_order | INTEGER | not null |
| id | UUID | PK |

## `assessment_claims`

| Column | Type | Notes |
|---|---|---|
| assessment_id | UUID | FK → assessments.id, not null |
| claim_key | VARCHAR | not null |
| category | VARCHAR | not null |
| statement | TEXT | not null |
| source | VARCHAR | not null |
| status | VARCHAR | not null |
| evidence | JSONB | not null |
| related_finding_fingerprints | JSONB | not null |
| explanation | TEXT | not null |
| id | UUID | PK |

## `assessment_findings`

| Column | Type | Notes |
|---|---|---|
| assessment_id | UUID | FK → assessments.id, not null |
| fingerprint | VARCHAR | not null |
| kind | VARCHAR | not null |
| category | VARCHAR | not null |
| severity | VARCHAR | not null |
| certainty | VARCHAR | not null |
| title | VARCHAR | not null |
| explanation | TEXT | not null |
| why_it_matters | TEXT |  |
| triggers | JSONB | not null |
| requirement_id | UUID | FK → immigration_requirements.id |
| source_url | VARCHAR |  |
| suggested_action | TEXT |  |
| evidence_suggestions | JSONB | not null |
| confidence | VARCHAR | not null |
| id | UUID | PK |

## `assessments`

| Column | Type | Notes |
|---|---|---|
| application_id | UUID | FK → applications.id, not null |
| version | INTEGER | not null |
| status | VARCHAR | not null |
| readiness_score | INTEGER |  |
| score_breakdown | JSONB | not null |
| summary | JSONB | not null |
| knowledge_snapshot | JSONB | not null |
| engine_version | VARCHAR | not null |
| ai_provider | VARCHAR | not null |
| triggered_by_id | UUID | FK → users.id |
| scenario | JSONB |  |
| is_simulation | BOOLEAN | not null |
| error | TEXT |  |
| created_at | DATETIME | not null |
| completed_at | DATETIME |  |
| id | UUID | PK |

## `audit_logs`

| Column | Type | Notes |
|---|---|---|
| actor_id | UUID | FK → users.id |
| actor_role | VARCHAR |  |
| action | VARCHAR | not null |
| target_type | VARCHAR |  |
| target_id | VARCHAR |  |
| ip_address | VARCHAR |  |
| user_agent | VARCHAR |  |
| details | JSONB | not null |
| created_at | DATETIME | not null |
| id | UUID | PK |

## `checklist_item_states`

| Column | Type | Notes |
|---|---|---|
| application_id | UUID | FK → applications.id, not null |
| item_key | VARCHAR | not null |
| collected | BOOLEAN | not null |
| note | TEXT |  |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `consent_records`

| Column | Type | Notes |
|---|---|---|
| user_id | UUID | FK → users.id, not null |
| consent_type | VARCHAR | not null |
| granted | BOOLEAN | not null |
| policy_version | VARCHAR | not null |
| created_at | DATETIME | not null |
| id | UUID | PK |

## `countries`

| Column | Type | Notes |
|---|---|---|
| code | VARCHAR | PK |
| name | VARCHAR | not null |
| region | VARCHAR |  |
| is_destination | BOOLEAN | not null |
| is_source_market | BOOLEAN | not null |
| module_status | VARCHAR | not null |
| sort_order | INTEGER | not null |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `data_deletion_requests`

| Column | Type | Notes |
|---|---|---|
| user_id | UUID | FK → users.id, not null |
| scope | VARCHAR | not null |
| application_id | UUID |  |
| reason | TEXT |  |
| status | VARCHAR | not null |
| processed_by_id | UUID | FK → users.id |
| completed_at | DATETIME |  |
| result | JSONB | not null |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `deliverables`

| Column | Type | Notes |
|---|---|---|
| order_type | VARCHAR | not null |
| order_id | UUID | not null |
| filename | VARCHAR | not null |
| content_type | VARCHAR | not null |
| size_bytes | BIGINT | not null |
| storage_key | VARCHAR | not null |
| wrapped_key | BLOB | not null |
| uploaded_by_id | UUID | FK → users.id, not null |
| created_at | DATETIME | not null |
| id | UUID | PK |

## `document_pages`

| Column | Type | Notes |
|---|---|---|
| document_id | UUID | FK → documents.id, not null |
| page_number | INTEGER | not null |
| text | TEXT | not null |
| method | VARCHAR | not null |
| ocr_confidence | FLOAT |  |
| id | UUID | PK |

## `documents`

| Column | Type | Notes |
|---|---|---|
| application_id | UUID | FK → applications.id, not null |
| family_member_id | UUID | FK → family_members.id |
| uploaded_by_id | UUID | FK → users.id, not null |
| original_filename | VARCHAR | not null |
| content_type | VARCHAR | not null |
| size_bytes | BIGINT | not null |
| sha256 | VARCHAR | not null |
| storage_key | VARCHAR | not null |
| wrapped_key | BLOB | not null |
| declared_type | VARCHAR |  |
| detected_type | VARCHAR |  |
| classification_confidence | FLOAT |  |
| classification_method | VARCHAR |  |
| checklist_item_key | VARCHAR |  |
| status | VARCHAR | not null |
| processing_error | TEXT |  |
| page_count | INTEGER |  |
| language_hint | VARCHAR |  |
| quality | JSONB | not null |
| replaces_id | UUID | FK → documents.id |
| is_current | BOOLEAN | not null |
| processed_at | DATETIME |  |
| deleted_at | DATETIME |  |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `evidence_rules`

| Column | Type | Notes |
|---|---|---|
| key | VARCHAR | unique, not null |
| title | VARCHAR | not null |
| category_types | JSONB | not null |
| applies_when | JSONB | not null |
| level | VARCHAR | not null |
| document_types | JSONB | not null |
| explanation | TEXT | not null |
| claim_key | VARCHAR |  |
| is_active | BOOLEAN | not null |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `extracted_fields`

| Column | Type | Notes |
|---|---|---|
| document_id | UUID | FK → documents.id, not null |
| field_name | VARCHAR | not null |
| value | TEXT | not null |
| normalized_value | TEXT |  |
| page_number | INTEGER |  |
| snippet | TEXT |  |
| confidence | FLOAT | not null |
| method | VARCHAR | not null |
| id | UUID | PK |

## `family_members`

| Column | Type | Notes |
|---|---|---|
| application_id | UUID | FK → applications.id, not null |
| relation | VARCHAR | not null |
| full_name | VARCHAR | not null |
| date_of_birth | DATE |  |
| included_in_application | BOOLEAN | not null |
| data | JSONB | not null |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `human_review_requests`

| Column | Type | Notes |
|---|---|---|
| application_id | UUID | FK → applications.id, not null |
| assessment_id | UUID | FK → assessments.id |
| reviewer_id | UUID | FK → professional_reviewers.id |
| status | VARCHAR | not null |
| comments | JSONB | not null |
| requires_legal_advice | BOOLEAN | not null |
| payment_id | UUID | FK → payments.id |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `immigration_requirements`

| Column | Type | Notes |
|---|---|---|
| visa_category_id | UUID | FK → visa_categories.id, not null |
| key | VARCHAR | not null |
| title | VARCHAR | not null |
| description | TEXT | not null |
| requirement_level | VARCHAR | not null |
| applies_when | JSONB |  |
| applies_to_member | VARCHAR | not null |
| eligibility_conditions | TEXT |  |
| document_types | JSONB | not null |
| financial_requirement | JSONB |  |
| exceptions | TEXT |  |
| translation_required_if_not_english | BOOLEAN | not null |
| official_source_id | UUID | FK → official_sources.id |
| source_url | VARCHAR | not null |
| source_excerpt | TEXT |  |
| effective_date | DATE |  |
| last_verified_at | DATETIME |  |
| verified_by_id | UUID | FK → users.id |
| review_status | VARCHAR | not null |
| version | INTEGER | not null |
| sort_order | INTEGER | not null |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `jobs`

| Column | Type | Notes |
|---|---|---|
| kind | VARCHAR | not null |
| payload | JSONB | not null |
| status | VARCHAR | not null |
| run_at | DATETIME | not null |
| attempts | INTEGER | not null |
| max_attempts | INTEGER | not null |
| last_error | TEXT |  |
| locked_at | DATETIME |  |
| locked_by | VARCHAR |  |
| created_at | DATETIME | not null |
| finished_at | DATETIME |  |
| id | UUID | PK |

## `notifications`

| Column | Type | Notes |
|---|---|---|
| user_id | UUID | FK → users.id, not null |
| kind | VARCHAR | not null |
| title | VARCHAR | not null |
| body | TEXT | not null |
| link | VARCHAR |  |
| read_at | DATETIME |  |
| email_status | VARCHAR | not null |
| email_error | TEXT |  |
| created_at | DATETIME | not null |
| id | UUID | PK |

## `official_sources`

| Column | Type | Notes |
|---|---|---|
| country_code | VARCHAR | FK → countries.code, not null |
| title | VARCHAR | not null |
| url | VARCHAR | unique, not null |
| publisher | VARCHAR | not null |
| is_official | BOOLEAN | not null |
| monitoring_enabled | BOOLEAN | not null |
| last_checked_at | DATETIME |  |
| last_content_hash | VARCHAR |  |
| last_changed_at | DATETIME |  |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `order_events`

| Column | Type | Notes |
|---|---|---|
| order_type | VARCHAR | not null |
| order_id | UUID | not null |
| from_status | VARCHAR |  |
| to_status | VARCHAR | not null |
| actor_id | UUID | FK → users.id |
| note | TEXT |  |
| created_at | DATETIME | not null |
| id | UUID | PK |

## `password_reset_tokens`

| Column | Type | Notes |
|---|---|---|
| user_id | UUID | FK → users.id, not null |
| token_hash | VARCHAR | unique, not null |
| created_at | DATETIME | not null |
| expires_at | DATETIME | not null |
| used_at | DATETIME |  |
| id | UUID | PK |

## `payment_events`

| Column | Type | Notes |
|---|---|---|
| payment_id | UUID | FK → payments.id |
| provider | VARCHAR | not null |
| provider_event_id | VARCHAR | not null |
| event_type | VARCHAR | not null |
| signature_valid | BOOLEAN | not null |
| payload | JSONB | not null |
| received_at | DATETIME | not null |
| id | UUID | PK |

## `payments`

| Column | Type | Notes |
|---|---|---|
| user_id | UUID | FK → users.id, not null |
| purpose | VARCHAR | not null |
| reference_id | UUID | not null |
| service_code | VARCHAR | FK → service_catalog.code, not null |
| amount_cents | INTEGER | not null |
| currency | VARCHAR | not null |
| provider | VARCHAR | not null |
| provider_order_id | VARCHAR | unique, not null |
| provider_payment_id | VARCHAR |  |
| status | VARCHAR | not null |
| paid_at | DATETIME |  |
| failure_reason | TEXT |  |
| invoice_number | VARCHAR | unique |
| refunded_cents | INTEGER | not null |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `permissions`

| Column | Type | Notes |
|---|---|---|
| code | VARCHAR | PK |
| description | TEXT |  |

## `policy_alerts`

| Column | Type | Notes |
|---|---|---|
| country_code | VARCHAR | FK → countries.code, not null |
| visa_category_id | UUID | FK → visa_categories.id |
| requirement_id | UUID | FK → immigration_requirements.id |
| official_source_id | UUID | FK → official_sources.id |
| title | VARCHAR | not null |
| summary | TEXT | not null |
| source_url | VARCHAR | not null |
| effective_date | DATE |  |
| status | VARCHAR | not null |
| verified_by_id | UUID | FK → users.id |
| published_at | DATETIME |  |
| affected_application_count | INTEGER | not null |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `professional_reviewers`

| Column | Type | Notes |
|---|---|---|
| user_id | UUID | FK → users.id, unique, not null |
| display_title | VARCHAR | not null |
| credential_type | VARCHAR |  |
| credential_number | VARCHAR |  |
| regulator | VARCHAR |  |
| is_licensed_adviser | BOOLEAN | not null |
| credentials_verified_at | DATETIME |  |
| countries | JSONB | not null |
| bio | TEXT |  |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `refunds`

| Column | Type | Notes |
|---|---|---|
| payment_id | UUID | FK → payments.id, not null |
| amount_cents | INTEGER | not null |
| reason | TEXT | not null |
| status | VARCHAR | not null |
| provider_refund_id | VARCHAR |  |
| requested_by_id | UUID | FK → users.id |
| processed_at | DATETIME |  |
| failure_reason | TEXT |  |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `refusal_analyses`

| Column | Type | Notes |
|---|---|---|
| application_id | UUID | FK → applications.id, not null |
| document_id | UUID | FK → documents.id, not null |
| reasons | JSONB | not null |
| method | VARCHAR | not null |
| status | VARCHAR | not null |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `requirement_versions`

| Column | Type | Notes |
|---|---|---|
| requirement_id | UUID | FK → immigration_requirements.id, not null |
| version | INTEGER | not null |
| snapshot | JSONB | not null |
| change_note | TEXT |  |
| changed_by_id | UUID | FK → users.id |
| created_at | DATETIME | not null |
| id | UUID | PK |

## `role_permissions`

| Column | Type | Notes |
|---|---|---|
| role_name | VARCHAR | PK, FK → roles.name |
| permission_code | VARCHAR | PK, FK → permissions.code |

## `roles`

| Column | Type | Notes |
|---|---|---|
| name | VARCHAR | PK |
| label | VARCHAR | not null |
| description | TEXT |  |
| is_staff | BOOLEAN | not null |

## `service_catalog`

| Column | Type | Notes |
|---|---|---|
| code | VARCHAR | PK |
| kind | VARCHAR | not null |
| name | VARCHAR | not null |
| description | TEXT | not null |
| price_cents | INTEGER |  |
| currency | VARCHAR | not null |
| sla_hours | INTEGER |  |
| required_information | JSONB | not null |
| inclusions | JSONB | not null |
| exclusions | JSONB | not null |
| disclaimer | TEXT |  |
| is_active | BOOLEAN | not null |
| sort_order | INTEGER | not null |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `support_tickets`

| Column | Type | Notes |
|---|---|---|
| user_id | UUID | FK → users.id, not null |
| subject | VARCHAR | not null |
| body | TEXT | not null |
| status | VARCHAR | not null |
| assigned_to_id | UUID | FK → users.id |
| related_type | VARCHAR |  |
| related_id | UUID |  |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `system_settings`

| Column | Type | Notes |
|---|---|---|
| key | VARCHAR | PK |
| value | JSONB | not null |
| updated_by_id | UUID | FK → users.id |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `translation_orders`

| Column | Type | Notes |
|---|---|---|
| reference | VARCHAR | unique, not null |
| user_id | UUID | FK → users.id, not null |
| source_document_id | UUID | FK → documents.id |
| language_pair | VARCHAR | not null |
| page_count | INTEGER |  |
| quote_cents | INTEGER |  |
| currency | VARCHAR | not null |
| translation_type | VARCHAR | not null |
| status | VARCHAR | not null |
| translator_id | UUID | FK → translators.id |
| payment_id | UUID | FK → payments.id |
| delivered_at | DATETIME |  |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `translators`

| Column | Type | Notes |
|---|---|---|
| user_id | UUID | FK → users.id, unique, not null |
| language_pairs | JSONB | not null |
| sworn_registration | VARCHAR |  |
| jurisdiction | VARCHAR |  |
| verified_at | DATETIME |  |
| is_active | BOOLEAN | not null |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `user_sessions`

| Column | Type | Notes |
|---|---|---|
| user_id | UUID | FK → users.id, not null |
| refresh_token_hash | VARCHAR | unique, not null |
| created_at | DATETIME | not null |
| expires_at | DATETIME | not null |
| last_used_at | DATETIME |  |
| revoked_at | DATETIME |  |
| mfa_passed | BOOLEAN | not null |
| ip_address | VARCHAR |  |
| user_agent | VARCHAR |  |
| id | UUID | PK |

## `users`

| Column | Type | Notes |
|---|---|---|
| email | VARCHAR | unique, not null |
| password_hash | VARCHAR | not null |
| full_name | VARCHAR | not null |
| role | VARCHAR | FK → roles.name, not null |
| is_active | BOOLEAN | not null |
| email_verified_at | DATETIME |  |
| mfa_enabled | BOOLEAN | not null |
| mfa_secret_enc | BLOB |  |
| mfa_secret_key | BLOB |  |
| failed_login_count | INTEGER | not null |
| locked_until | DATETIME |  |
| last_login_at | DATETIME |  |
| ai_training_consent | BOOLEAN | not null |
| marketing_consent | BOOLEAN | not null |
| terms_accepted_at | DATETIME |  |
| deleted_at | DATETIME |  |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `visa_categories`

| Column | Type | Notes |
|---|---|---|
| country_code | VARCHAR | FK → countries.code, not null |
| category_type | VARCHAR | not null |
| code | VARCHAR | not null |
| name | VARCHAR | not null |
| description | TEXT |  |
| official_url | VARCHAR |  |
| is_active | BOOLEAN | not null |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

## `writing_orders`

| Column | Type | Notes |
|---|---|---|
| reference | VARCHAR | unique, not null |
| user_id | UUID | FK → users.id, not null |
| application_id | UUID | FK → applications.id |
| service_code | VARCHAR | FK → service_catalog.code, not null |
| price_cents | INTEGER | not null |
| currency | VARCHAR | not null |
| status | VARCHAR | not null |
| customer_notes | TEXT |  |
| missing_information_note | TEXT |  |
| assigned_to_id | UUID | FK → users.id |
| paid_at | DATETIME |  |
| instructions_sent_at | DATETIME |  |
| info_requested_at | DATETIME |  |
| info_complete_at | DATETIME |  |
| deadline_at | DATETIME |  |
| processing_started_at | DATETIME |  |
| quality_review_at | DATETIME |  |
| delivered_at | DATETIME |  |
| deadline_warning_sent_at | DATETIME |  |
| refund_eligible_at | DATETIME |  |
| refund_id | UUID | FK → refunds.id |
| payment_id | UUID | FK → payments.id |
| id | UUID | PK |
| created_at | DATETIME | not null |
| updated_at | DATETIME | not null |

