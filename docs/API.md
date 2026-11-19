# API reference

Interactive OpenAPI docs: run the backend and open `/api/docs` (disabled in production). All routes are under `/api`. State-changing requests require the header `X-Requested-With: visaready` (CSRF protection); payment webhooks are exempt and authenticated by signature instead.

| Method | Path | Summary |
|---|---|---|
| GET | `/api/admin/applications` | Applications |
| GET | `/api/admin/audit-logs` | Audit Logs |
| GET | `/api/admin/deletion-requests` | Deletion Requests |
| POST | `/api/admin/deletion-requests/{request_id}/process` | Process Deletion |
| GET | `/api/admin/documents/{document_id}/download` | Staff Download |
| GET | `/api/admin/jobs` | Jobs |
| GET | `/api/admin/knowledge/categories` | Admin Categories |
| POST | `/api/admin/knowledge/categories` | Create Category |
| PATCH | `/api/admin/knowledge/countries/{code}` | Patch Country |
| GET | `/api/admin/knowledge/evidence-rules` | Evidence Rules |
| GET | `/api/admin/knowledge/requirements` | Admin Requirements |
| POST | `/api/admin/knowledge/requirements` | Create Requirement |
| PATCH | `/api/admin/knowledge/requirements/{req_id}` | Patch Requirement |
| POST | `/api/admin/knowledge/requirements/{req_id}/retire` | Retire |
| POST | `/api/admin/knowledge/requirements/{req_id}/verify` | Verify |
| GET | `/api/admin/knowledge/requirements/{req_id}/versions` | Versions |
| GET | `/api/admin/knowledge/sources` | Sources |
| POST | `/api/admin/knowledge/sources/{source_id}/check` | Check Source |
| GET | `/api/admin/overview` | Overview |
| GET | `/api/admin/payments` | Payments |
| POST | `/api/admin/payments/{payment_id}/refund` | Refund Payment |
| GET | `/api/admin/policy-alerts` | Alerts |
| POST | `/api/admin/policy-alerts` | Create Alert |
| POST | `/api/admin/policy-alerts/{alert_id}/publish` | Publish Alert |
| GET | `/api/admin/refunds` | Refunds |
| GET | `/api/admin/settings/retention` | Get Retention |
| PUT | `/api/admin/settings/retention` | Set Retention |
| GET | `/api/admin/support-tickets` | Tickets |
| PATCH | `/api/admin/support-tickets/{ticket_id}` | Patch Ticket |
| GET | `/api/admin/users` | Users |
| PATCH | `/api/admin/users/{user_id}` | Patch User |
| GET | `/api/admin/writing-orders` | Writing Orders |
| POST | `/api/admin/writing-orders/sla-sweep` | Run Sla Sweep |
| GET | `/api/admin/writing-orders/{order_id}` | Writing Order |
| POST | `/api/admin/writing-orders/{order_id}/action` | Order Action |
| POST | `/api/admin/writing-orders/{order_id}/deliver` | Deliver |
| POST | `/api/admin/writing-orders/{order_id}/refund` | Refund Order |
| GET | `/api/applications` | List Applications |
| POST | `/api/applications` | Create Application |
| GET | `/api/applications/{application_id}` | Get Application |
| PATCH | `/api/applications/{application_id}` | Update Application |
| POST | `/api/applications/{application_id}/assessments` | Request Assessment |
| GET | `/api/applications/{application_id}/assessments` | List Assessments |
| PUT | `/api/applications/{application_id}/checklist/{item_key}` | Set Checklist State |
| POST | `/api/applications/{application_id}/complete` | Mark Complete |
| GET | `/api/applications/{application_id}/documents` | List Documents |
| POST | `/api/applications/{application_id}/documents` | Upload Document |
| POST | `/api/applications/{application_id}/family-members` | Add Family Member |
| DELETE | `/api/applications/{application_id}/family-members/{member_id}` | Remove Family Member |
| GET | `/api/applications/{application_id}/refusal-analyses` | Refusal Analyses |
| POST | `/api/applications/{application_id}/what-if` | What If |
| GET | `/api/assessments/{assessment_id}` | Get Assessment |
| GET | `/api/assessments/{assessment_id}/compare/{other_id}` | Compare Assessments |
| GET | `/api/assessments/{assessment_id}/report` | Printable Report |
| POST | `/api/auth/forgot-password` | Forgot Password |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/logout` | Logout |
| POST | `/api/auth/logout-all` | Logout All |
| GET | `/api/auth/me` | Me |
| POST | `/api/auth/mfa/disable` | Mfa Disable |
| POST | `/api/auth/mfa/enable` | Mfa Enable |
| POST | `/api/auth/mfa/setup` | Mfa Setup |
| POST | `/api/auth/refresh` | Refresh |
| POST | `/api/auth/register` | Register |
| POST | `/api/auth/reset-password` | Reset Password |
| GET | `/api/countries` | Countries |
| GET | `/api/countries/{code}/visa-categories` | Categories |
| GET | `/api/document-types` | Document Types |
| GET | `/api/documents/download/{token}` | Download |
| GET | `/api/documents/{document_id}` | Get Document |
| PATCH | `/api/documents/{document_id}` | Update Document |
| DELETE | `/api/documents/{document_id}` | Delete Document |
| POST | `/api/documents/{document_id}/download-token` | Download Token |
| GET | `/api/health` | Health |
| GET | `/api/knowledge/search` | Knowledge Search |
| GET | `/api/notifications` | Notifications |
| POST | `/api/notifications/read-all` | Read All |
| GET | `/api/official-sources` | Official Sources |
| GET | `/api/payments` | My Payments |
| POST | `/api/payments/checkout` | Checkout |
| GET | `/api/payments/config` | Payment Config |
| POST | `/api/payments/sandbox/complete` | Sandbox Complete |
| POST | `/api/payments/webhook/payhere` | Payhere Webhook |
| GET | `/api/payments/{payment_id}` | Get Payment |
| GET | `/api/payments/{payment_id}/invoice` | Invoice |
| GET | `/api/policy-alerts` | Policy Alerts |
| GET | `/api/privacy` | Privacy |
| PUT | `/api/privacy` | Update Privacy |
| POST | `/api/privacy/deletion-requests` | Request Deletion |
| GET | `/api/privacy/export` | Export Data |
| GET | `/api/profile` | Get Profile |
| PUT | `/api/profile` | Update Profile |
| GET | `/api/services` | Services |
| GET | `/api/support/tickets` | My Tickets |
| POST | `/api/support/tickets` | Create Ticket |
| GET | `/api/visa-categories/{category_id}/requirements` | Requirements |
| GET | `/api/writing-orders` | List Orders |
| POST | `/api/writing-orders` | Create |
| GET | `/api/writing-orders/{order_id}` | Get Order |
| GET | `/api/writing-orders/{order_id}/deliverables/{deliverable_id}` | Download Deliverable |
