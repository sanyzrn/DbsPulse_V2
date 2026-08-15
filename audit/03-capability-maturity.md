> **DbsPulse V2 — Product, Architecture, Workflow, Security & UX Audit**  
> Repository: <https://github.com/sanyzrn/DbsPulse_V2> · Branch `main` · Commit `ef0166b091d2d167d808702e084c079e5143e307`  
> Site section: 1.2 · Capability maturity

# Capability maturity — what is actually built, area by area

Every capability a commercial performance-management buyer will ask about, classified as **Complete**, **Partial**, **Missing** or *Not verifiable from the repository*, with the file that proves it. Tier marks whether the capability is table stakes, enterprise-grade, or an optional differentiator — parity with every global HR suite is not treated as mandatory.

**Classification counts:** Partial 8 · Missing 8 · Complete 5 (of 21 areas)

## Matrix

| Capability area | Status | Tier |
|---|---|---|
| Evaluation cycles and templates | Partial | Table stakes |
| KPI / OKR / goal management | Missing | Table stakes |
| Competency frameworks | Missing | Enterprise grade |
| Weighted scoring and calculation | Complete | Table stakes |
| Scoring configurability | Missing | Enterprise grade |
| Calibration and normalization | Missing | Enterprise grade |
| Employee self-assessment | Missing | Table stakes |
| Manager reviews | Complete | Table stakes |
| Multi-stage approvals | Complete | Table stakes |
| 360 / peer / upward feedback | Missing | Optional differentiator |
| Improvement / development plans | Partial | Table stakes |
| Performance history | Partial | Table stakes |
| Contract-renewal decision support | Complete | Differentiator (core use case) |
| Reporting, analytics and exports | Partial | Table stakes |
| Notifications and reminders | Partial | Table stakes |
| Integrations and public API | Missing | Enterprise grade |
| Mobile and employee experience | Partial | Enterprise grade |
| HR administration and configuration | Partial | Table stakes |
| Auditability | Partial | Enterprise grade |
| Document integrity and verification | Complete | Differentiator |
| Multi-tenancy | Missing | Enterprise grade (only if sold as SaaS) |

## Detail

### Evaluation cycles and templates

**Status:** Partial · **Tier:** Table stakes

One hardcoded evaluation template (20 indicators, general + specialized sections). Evaluation periods/campaigns are fully implemented server-side — list, create, close, progress, a one-open-period rule enforced by a partial unique index, and evaluator notification on open — but the UI route renders a DisabledFeature panel because FEATURE_PERIODS_ENABLED is false.

**Repository evidence**

```text
backend/app/api/routers/periods.py · frontend/src/appInfo.ts:13 · frontend/src/App.tsx
```

### KPI / OKR / goal management

**Status:** Missing · **Tier:** Table stakes

No goal, objective, key-result or KPI entity exists. The only goal-like object is ImprovementPlanGoal, which exists solely inside a remedial plan created after a weak evaluation. Nothing forward-looking can be set, cascaded, weighted or measured.

**Repository evidence**

```text
backend/app/models/ — 12 models, none goal-related except improvement_plan_goals
```

### Competency frameworks

**Status:** Missing · **Tier:** Enterprise grade

Indicators are a flat list with a section flag and display order. There is no competency library, no proficiency levels, no job-family or grade differentiation, and no mapping of indicators to roles. Every employee — from a warehouse operator to a deputy — is scored on the identical 20 items.

**Repository evidence**

```text
backend/app/models/indicator.py · backend/app/api/routers/indicators.py
```

### Weighted scoring and calculation

**Status:** Complete · **Tier:** Table stakes

compute_result averages the 1–5 scores within each section, converts to a percentage, then combines 60% general with 40% specialized. Scores are constrained to 1–5 by a database CHECK constraint, and (record, indicator) uniqueness is enforced by a unique constraint. Calculation happens on the server at submit time, never in the browser.

**Repository evidence**

```text
backend/app/services/evaluation.py:60-80 · backend/app/models/evaluation.py CheckConstraint('score BETWEEN 1 AND 5')
```

### Scoring configurability

**Status:** Missing · **Tier:** Enterprise grade

Section weights (0.6 / 0.4), the evidence-required score values (1 and 5), evidence word bounds (≥3, ≤40) and all four renewal thresholds are Python module constants. Changing any of them is a code change, a rebuild and a redeploy. There is a /api/config endpoint, but it only exposes these constants to the UI — it cannot set them.

**Repository evidence**

```text
backend/app/core/constants.py · backend/app/api/routers/config.py
```

### Calibration and normalization

**Status:** Missing · **Tier:** Enterprise grade

No calibration session, no cross-manager comparison view, no forced or guided distribution, no rater-leniency detection. HR reporting can display score distributions but nothing can act on them, and no transition exists for adjusting a score after submission other than returning the whole record.

**Repository evidence**

```text
backend/app/api/routers/reports.py · backend/app/services/workflow.py TRANSITIONS
```

### Employee self-assessment

**Status:** Missing · **Tier:** Table stakes

The state machine has no employee-facing stage. The subject of the evaluation cannot enter scores, comments, achievements or context at any point. The employee's only interaction with the process is acknowledging the finished result.

**Repository evidence**

```text
backend/app/services/workflow.py TRANSITIONS (7 transitions, none with an employee actor) · backend/app/api/routers/me.py
```

### Manager reviews

**Status:** Complete · **Tier:** Table stakes

Unit supervisors score their assigned employees indicator by indicator with mandatory evidence text on extreme scores, add an evaluator comment, and submit. A 'manager path' exists for employees who have no supervisor: the deputy becomes the first scorer and the record is created directly at hr_approved with unit_supervisor_user_id = NULL, which is_manager_path() then uses to skip the supervisor stage consistently everywhere.

**Repository evidence**

```text
backend/app/api/routers/evaluations.py:117-235, 421-456 · backend/app/services/workflow.py is_manager_path()
```

### Multi-stage approvals

**Status:** Complete · **Tier:** Table stakes

Four-stage chain: unit supervisor → HR → deputy → CEO → finalized, expressed as an explicit table of seven transitions each carrying from-status, allowed role, assignee field and error semantics. Stage order cannot be skipped because the from_status check fails, and the row is locked FOR UPDATE while a transition is applied.

**Repository evidence**

```text
backend/app/services/workflow.py TRANSITIONS · backend/app/api/routers/evaluations.py:60-78
```

### 360 / peer / upward feedback

**Status:** Missing · **Tier:** Optional differentiator

Explicitly listed as out of scope in the repository README. No peer nomination, no anonymous feedback, no rater-set management, no upward feedback on managers.

**Repository evidence**

```text
README.md — out-of-scope section
```

### Improvement / development plans

**Status:** Partial · **Tier:** Table stakes

A complete plan model with goals, status, review date, and automatic creation prompts for conditional-renewal outcomes, plus a review-due sweep. But all eleven endpoints are gated to the HR role: the plan's owner_user_id receives a notification and then has no API through which to read or update the plan. The employee can see their own open plans read-only. Managers cannot participate at all.

**Repository evidence**

```text
backend/app/api/routers/improvement_plans.py — require_roles(UserRole.hr) on every endpoint · backend/app/api/routers/me.py
```

### Performance history

**Status:** Partial · **Tier:** Table stakes

Finalized evaluations persist a full final_snapshot JSONB plus the three percentage columns, and the employee scorecard lists prior finalized results. There is no year-over-year trend analytic, no comparison of the same indicator across cycles, and — because indicators are mutable and unversioned — historical comparability is not guaranteed.

**Repository evidence**

```text
backend/app/models/evaluation.py final_snapshot · backend/app/services/snapshot.py SNAPSHOT_VERSION = 1 · backend/app/api/routers/me.py
```

### Contract-renewal decision support

**Status:** Complete · **Tier:** Differentiator (core use case)

This is the product's sharpest capability and its real market wedge. Final weighted score maps to one of four Persian renewal recommendations via threshold table; a contract-expiry sweep warns HR ahead of contract_end_date; the CEO finalization writes an immutable snapshot, renders a byte-stable PDF, stores its SHA-256 and mints an unguessable verify token exposed through a public QR-verifiable page.

**Repository evidence**

```text
backend/app/core/constants.py FINAL_RESULT_THRESHOLDS · backend/app/services/scheduled.py · backend/app/services/documents.py archive_final_pdf · backend/app/api/routers/verify.py
```

### Reporting, analytics and exports

**Status:** Partial · **Tier:** Table stakes

Four HR-only report endpoints with composable filters, seven dashboard endpoints including a per-role overview, and five Excel exports (evaluations, personnel, improvement plans, audit log, reports). Weaknesses: HR-only (managers and executives get no analytics surface of their own), no minimum-cohort suppression, no saved views, no scheduled delivery, and the report export is the only export that is not audit-logged.

**Repository evidence**

```text
backend/app/api/routers/reports.py:300-321 (no log_event) · backend/app/api/routers/dashboard.py · backend/app/services/excel.py
```

### Notifications and reminders

**Status:** Partial · **Tier:** Table stakes

In-app notifications are well built: per-user rows, read/read-all, a dedup key so sweeps cannot spam, and notify_for_workflow_action wired into every transition. But there is no email, SMS, push or messenger channel — the README states this explicitly — so a pending approval is invisible until the approver decides to log in, and the SLA sweep can only add another in-app row.

**Repository evidence**

```text
backend/app/services/notifications.py · backend/app/api/routers/notifications.py · README.md out-of-scope
```

### Integrations and public API

**Status:** Missing · **Tier:** Enterprise grade

No SSO/OIDC/SAML/LDAP, no HRIS or payroll connector, no webhooks, no API keys or service accounts, no versioned or documented public API surface (OpenAPI docs are deliberately disabled in production). Personnel data must be entered by hand or imported through the UI.

**Repository evidence**

```text
backend/app/main.py (docs disabled in production) · backend/app/api/deps.py (only user-bearer auth) · README.md out-of-scope
```

### Mobile and employee experience

**Status:** Partial · **Tier:** Enterprise grade

A responsive RTL web app with a viewport meta tag and flex-wrap navigation, but no PWA manifest, no service worker, no offline capability, no native app, and no push notification path. The employee surface itself is thin: scorecard, acknowledgment, own open improvement plans.

**Repository evidence**

```text
frontend/index.html (no manifest link) · frontend/src/pages/ · backend/app/api/routers/me.py
```

### HR administration and configuration

**Status:** Partial · **Tier:** Table stakes

HR can manage users, personnel, indicators (CRUD + reorder, with deletion blocked once scored), evaluation access assignments, improvement plans, and can trigger sweeps manually. What HR cannot configure without a developer: weights, thresholds, evidence rules, stage composition, deadlines, notification templates, or report definitions.

**Repository evidence**

```text
backend/app/api/routers/{users,personnel,indicators,evaluation_access,admin}.py · backend/app/core/constants.py
```

### Auditability

**Status:** Partial · **Tier:** Enterprise grade

An audit_log table records actor, event type, old and new JSONB values and timestamp for roughly 35 event types, with an HR-only viewer and Excel export. Gaps: writes are append-only by application convention only (no hash chain, no WORM, no independent store), improvement-plan goal mutations are not logged, and the report export is not logged.

**Repository evidence**

```text
backend/app/models/audit_log.py · backend/app/services/audit.py log_event · backend/app/api/routers/audit_log.py _EVENT_LABELS
```

### Document integrity and verification

**Status:** Complete · **Tier:** Differentiator

A real strength that most competitors of this size lack. Finalization renders a deterministic PDF from an immutable snapshot, stores the bytes plus SHA-256 in evaluation_documents, is idempotent on re-run, embeds a QR code pointing at a public verification page keyed by a random 24-byte token, and degrades gracefully if WeasyPrint's native libraries are absent. The PDF template escapes output and restricts URL fetching to the local templates directory.

**Repository evidence**

```text
backend/app/services/documents.py · backend/app/services/pdf.py _local_templates_only_url_fetcher · backend/app/api/routers/verify.py
```

### Multi-tenancy

**Status:** Missing · **Tier:** Enterprise grade (only if sold as SaaS)

Single-organization by design — no tenant discriminator anywhere in the schema. This is a legitimate choice for an internal tool and should not be scored as a defect for that use case, but it is an absolute blocker for selling DbsPulse as a hosted product to multiple companies.

**Repository evidence**

```text
backend/app/models/*.py — no organization_id / tenant_id column on any of the 12 models
```

---

Audit of `sanyzrn/DbsPulse_V2` — branch `main`, commit `ef0166b091d2d167d808702e084c079e5143e307`. Findings derive from static inspection of source files in that commit. No application code was modified. Items that cannot be confirmed from the repository are labelled *Not verifiable from the repository*.
