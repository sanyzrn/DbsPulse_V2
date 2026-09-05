> **DbsPulse V2 — Product, Architecture, Workflow, Security & UX Audit**  
> Repository: <https://github.com/sanyzrn/DbsPulse_V2> · Branch `main` · Commit `ef0166b091d2d167d808702e084c079e5143e307`  
> Site section: 2. Gap Analysis + Fixes

# Gap analysis and fixes — every finding, with evidence and a recommended fix

41 findings. Each carries a finding ID, priority, category, current state, exact repository evidence with file path and line location where available, the gap or risk, a recommended fix, product and business impact, implementation difficulty, dependencies and a confidence level. Polished UI, hidden buttons, frontend-only validation and unused code are never counted as working functionality.

**Priority counts:** P0 8 · P1 14 · P2 8 · P3 8 · Moonshot 3 (total 41)

## Finding index

| ID | Priority | Category | Area | Title | Difficulty | Impact | Effort | Confidence |
|---|---|---|---|---|---|---|---|---|
| P0-01 | P0 | Security | Security & access control | Demo accounts with a published shared password are seeded by a migration that runs on every production boot | Low | 10/10 | 1.5/10 | High |
| P0-02 | P0 | Workflow integrity | Workflow realism | No cancel, void or reassign transition — a single departed approver permanently blocks an employee from ever being evaluated again | Low | 9/10 | 2.5/10 | High |
| P0-03 | P0 | Authorization | Security & access control | Any HR user can approve or return any evaluation, and the HR role is also the super-admin — no separation of duties | Medium | 9/10 | 5/10 | High |
| P0-04 | P0 | Security | Security & access control | Login rate limiting can be bypassed with a spoofed header, and there is no per-account lockout | Medium | 9/10 | 3.5/10 | Medium |
| P0-05 | P0 | Workflow integrity | Workflow realism | Score and comment writes bypass the row lock used by transitions, leaving a lost-update and write-after-submit window | Low | 8/10 | 2/10 | Medium |
| P0-06 | P0 | Trust and fairness | Workflow realism | The employee has no voice: no self-assessment, no visibility before the decision, no objection path, and no access to the signed document about them | Medium | 10/10 | 5.5/10 | High |
| P0-07 | P0 | Deployment | Testing & deployment | Migrations run automatically on every container start, and the backend process runs as root | Low | 7/10 | 2/10 | High |
| P0-08 | P0 | Enterprise readiness | Enterprise readiness | Reminders and escalation are effectively off in production: the scheduler is in-process, defaults to disabled, and is unsafe with more than one replica | Medium | 8/10 | 3.5/10 | High |
| P1-01 | P1 | Product capability | Feature parity | No goal, OKR or KPI object exists — evaluation is disconnected from what people were actually asked to achieve | High | 9/10 | 8/10 | High |
| P1-02 | P1 | Workflow integrity | Workflow realism | Deadlines are advisory only, and the SLA sweep measures total case age instead of time in the current stage | Low | 8/10 | 2.5/10 | High |
| P1-03 | P1 | Product capability | Feature parity | Notifications are in-app only, so the entire workflow depends on approvers voluntarily logging in | Medium | 9/10 | 4.5/10 | High |
| P1-04 | P1 | Product capability | Feature parity | Weights, thresholds, evidence rules and stage composition are Python constants — every customer needs a developer | High | 9/10 | 7/10 | High |
| P1-05 | P1 | Product capability | Feature parity | Indicators are mutable and unversioned, so editing the framework rewrites the meaning of past evaluations and breaks in-flight drafts | Medium | 7/10 | 4.5/10 | High |
| P1-06 | P1 | Product capability | Feature parity | No self-assessment, no 360 input, and no calibration — the result is one manager's opinion with no correction mechanism | High | 8/10 | 7/10 | High |
| P1-07 | P1 | Release management | Workflow realism | Evaluation periods are fully built server-side but hidden behind a disabled feature flag while the README presents them as a feature | Low | 7/10 | 2.5/10 | High |
| P1-08 | P1 | Privacy | Security & access control | Analytics and exports have no minimum-cohort suppression, so filtering to a small unit discloses individuals | Low | 7/10 | 2/10 | High |
| P1-09 | P1 | Auditability | Security & access control | The audit log is append-only by convention only, and two mutation paths are not logged at all | Medium | 8/10 | 4/10 | High |
| P1-10 | P1 | Authorization | Security & access control | Improvement plans are HR-only: the plan owner is notified but has no API to read or update the plan they own | Medium | 7/10 | 4/10 | High |
| P1-11 | P1 | Enterprise readiness | Enterprise readiness | No retention, deletion or legal-hold capability, and archived PDFs accumulate as bytes inside PostgreSQL forever | Medium | 7/10 | 5/10 | High |
| P1-12 | P1 | Observability | Reliability & observability | No metrics, tracing or error tracking — production failures are visible only as container logs | Medium | 6/10 | 4/10 | High |
| P1-13 | P1 | Testing | Testing & deployment | No real concurrency test and no end-to-end test — the enforcement chain is never verified as a whole | Medium | 7/10 | 4/10 | High |
| P1-14 | P1 | Enterprise readiness | Enterprise readiness | No SSO, no HRIS or payroll integration, no webhooks, no versioned public API | High | 8/10 | 7.5/10 | High |
| P2-01 | P2 | Product capability | Feature parity | Analytics exist only for HR — managers and executives have no analytical surface of their own | Medium | 7/10 | 4/10 | High |
| P2-02 | P2 | Security | Security & access control | Excel exports write user-supplied text without neutralising formula-triggering prefixes | Low | 4/10 | 1/10 | Medium |
| P2-03 | P2 | Product capability | Feature parity | No bulk operations — an annual cycle for a whole company is created one evaluation at a time | Medium | 7/10 | 3.5/10 | High |
| P2-04 | P2 | UX | UX & usability | No PWA manifest, no offline capability, no push — the employee and manager experience is desktop-web only | Medium | 6/10 | 4/10 | High |
| P2-05 | P2 | Reliability | Reliability & observability | Unbounded free-text fields, no explicit connection-pool sizing, and PDFs rendered inline on the request path | Medium | 5/10 | 3.5/10 | Medium |
| P2-06 | P2 | Security | Security & access control | No MFA, no session visibility, no password expiry, and no HSTS in the shipped nginx template | Medium | 6/10 | 4/10 | Medium |
| P2-07 | P2 | UX | UX & usability | No accessibility verification, no English locale scaffolding, and user-facing strings are inline literals | Low | 5/10 | 3/10 | Medium |
| P2-08 | P2 | Product capability | Feature parity | Reporting has no saved views, scheduled delivery, or cross-period comparison | Medium | 5/10 | 3.5/10 | High |
| P3-01 | P3 | Differentiation | Differentiation & AI | Renewal-risk early warning: predict the contract decision months before the evaluation, with explanation | Medium | 8/10 | 4/10 | High |
| P3-02 | P3 | Differentiation | Differentiation & AI | No-code process designer: let HR compose stages, weights, thresholds and rules without a developer | High | 8/10 | 8.5/10 | High |
| P3-03 | P3 | Differentiation | Differentiation & AI | Iranian compliance and localisation pack as a defensible moat | Medium | 8/10 | 5/10 | High |
| P3-04 | P3 | Differentiation | Differentiation & AI | Fast, low-friction workflows as the product promise: minutes per evaluation, measured and published | Low | 7/10 | 2.5/10 | High |
| P3-05 | P3 | Differentiation | Differentiation & AI | Smarter improvement plans: a template library generated from the organisation's own weak-indicator patterns | Medium | 7/10 | 4/10 | High |
| P3-06 | P3 | AI | Differentiation & AI | Evidence-quality assistant: help evaluators write specific, behavioural justifications | Medium | 7/10 | 4/10 | Medium |
| P3-07 | P3 | AI | Differentiation & AI | Rater-bias and pattern detection for calibration support | Medium | 7/10 | 3.5/10 | High |
| P3-08 | P3 | AI | Differentiation & AI | Narrative synthesis of qualitative content, with the human as author of record | Medium | 6/10 | 4/10 | Medium |
| MS-01 | Moonshot | Moonshot | Differentiation & AI | Continuous performance signal layer — evaluate from evidence, not memory | Very high | 9/10 | 9.5/10 | Medium |
| MS-02 | Moonshot | Moonshot | Differentiation & AI | Anonymised Iranian HR benchmark network | Very high | 8/10 | 10/10 | Medium |
| MS-03 | Moonshot | Moonshot | Differentiation & AI | Verifiable evaluation credentials — extend hash-verified PDFs into signed, portable attestations | Very high | 7/10 | 8.5/10 | Medium |


---

## Feature parity (8)

Capability gaps versus enterprise suites (Workday, SAP SuccessFactors, Oracle Fusion) and modern performance products (Lattice, Culture Amp, 15Five, Leapsome).

### P1-01 · P1 · No goal, OKR or KPI object exists — evaluation is disconnected from what people were actually asked to achieve

| Field | Value |
|---|---|
| Finding ID | P1-01 |
| Priority | P1 |
| Category | Product capability |
| Implementation difficulty | High |
| Business impact score | 9 / 10 |
| Implementation effort score | 8 / 10 |
| Confidence | High |

**Current state**

Twelve models, none of which represents an objective, key result, target or KPI. The only goal-shaped entity is ImprovementPlanGoal, which exists only inside a remedial plan created after a weak evaluation. Assessment is therefore twenty subjective 1–5 judgements plus evidence text.

**Exact repository evidence**

```text
The model package contains user, personnel, indicator, evaluation (record/score/comment/access), evaluation_period, improvement_plan, improvement_plan_goal, notification, audit_log and auth_session — no goal or objective entity outside the improvement plan.
```

**File path & location**

```text
backend/app/models/ · backend/app/models/improvement_plan.py · backend/app/core/constants.py
```

**Gap / risk / missing capability**

Every benchmark product treats goals as the spine that connects strategy to individual assessment: Workday and SuccessFactors cascade objectives through the org, Lattice and Leapsome make goal check-ins the weekly habit that supplies review evidence. Without a goal object DbsPulse cannot answer 'what was this person accountable for', cannot show progress between cycles, cannot supply the manager with anything factual at scoring time, and cannot distinguish an employee who missed agreed targets from one whose manager rates strictly. It also means the product has nothing to sell to a buyer whose stated problem is alignment rather than contract compliance.

**Recommended fix**

Introduce a first-class goal entity (owner personnel, title, description, measure type — numeric target, percentage, milestone or binary — start/end in Jalali, weight, parent goal for cascading, status) with progress updates that carry a value, a note and an author. Then wire it into what already exists: allow an indicator to reference goal achievement, surface the owner's goals and their progress read-only inside the scoring screen as evidence, and let an improvement-plan goal be promoted to a normal goal when the plan closes. Keep the scoring formula unchanged at first — goals as context before goals as arithmetic — so the change is additive and reversible.

**Product & business impact**

Moves DbsPulse from 'contract-renewal paperwork' to 'performance management'. It is the single largest capability gap versus every competitor and the prerequisite for continuous performance, for meaningful analytics and for most of the AI opportunities in section 3.

**Dependencies**

- New tables and migrations
- New UI surfaces for employee, manager and HR
- Should follow the configurability work in P1-04

### P1-03 · P1 · Notifications are in-app only, so the entire workflow depends on approvers voluntarily logging in

| Field | Value |
|---|---|
| Finding ID | P1-03 |
| Priority | P1 |
| Category | Product capability |
| Implementation difficulty | Medium |
| Business impact score | 9 / 10 |
| Implementation effort score | 4.5 / 10 |
| Confidence | High |

**Current state**

A well-built in-app notification system: per-user rows, unread counts, read and read-all, a dedup key preventing sweep spam, and notify_for_workflow_action invoked on every transition. The README states explicitly that email, SMS and messenger notifications are out of scope.

**Exact repository evidence**

```text
notifications service exposes notify, notify_once and notify_for_workflow_action; the notifications router serves list, read and read-all per user; README.md lists the absence of email/SMS/bot channels as an explicit scope decision.
```

**File path & location**

```text
backend/app/services/notifications.py · backend/app/api/routers/notifications.py · README.md
```

**Gap / risk / missing capability**

A CEO or deputy is precisely the user who will not open an HR tool unprompted. With no outbound channel, a pending approval is invisible until someone opens the app, so the reminder sweeps — even once they reliably run — can only add another row to a page nobody is looking at. There is also no path for account events that need to reach a user who cannot log in, such as a password reset, and no digest that would let a manager see 'three evaluations need you' without a visit.

**Recommended fix**

Add a channel abstraction behind the existing notify() call so the workflow code does not change: a notification_deliveries table (notification id, channel, status, attempts, provider message id, error), an outbox pattern with retry and backoff, and per-user, per-event-type preferences with quiet hours. Implement email first for reliability, then an Iranian SMS gateway for approval reminders and contract-expiry alerts, then optionally a Bale or Eitaa bot for in-country messaging. Never put scores or recommendations in the message body — send a deep link and a subject only. Give HR a delivery log so 'they were never told' can be answered with evidence.

**Product & business impact**

Directly attacks the metric that sells this product: days to complete an evaluation cycle. It also removes the most common operational complaint about internal HR tools — that approvals stall invisibly.

**Dependencies**

- Outbound provider and credentials
- Secrets management
- Pairs with P0-08 and P1-02

### P1-04 · P1 · Weights, thresholds, evidence rules and stage composition are Python constants — every customer needs a developer

| Field | Value |
|---|---|
| Finding ID | P1-04 |
| Priority | P1 |
| Category | Product capability |
| Implementation difficulty | High |
| Business impact score | 9 / 10 |
| Implementation effort score | 7 / 10 |
| Confidence | High |

**Current state**

GENERAL_SECTION_WEIGHT = 0.6, SPECIALIZED_SECTION_WEIGHT = 0.4, EVIDENCE_REQUIRED_SCORES = (1, 5), EVIDENCE_REQUIRED_MIN_WORDS = 3, EVIDENCE_MAX_WORDS = 40 and the four FINAL_RESULT_THRESHOLDS with their Persian recommendation strings are module-level constants. The /api/config endpoint exposes them read-only to the UI. Indicators are the only part of the model HR can edit, and they carry no weight of their own — compute_result averages equally within a section.

**Exact repository evidence**

```text
constants.py defines all of the above literally; config.py returns them for display; compute_result averages scores per section then applies the two fixed section weights; the indicator model has no weight column.
```

**File path & location**

```text
backend/app/core/constants.py · backend/app/api/routers/config.py · backend/app/services/evaluation.py:60-80 · backend/app/models/indicator.py
```

**Gap / risk / missing capability**

The scoring model is the part of a performance product every buyer wants to argue about. Today a customer who wants 70/30, a fifth renewal band, evidence required on a score of 2, or a heavier weight on safety indicators needs a code change, a review, a build and a deploy — which means DbsPulse cannot be sold to a second organisation without forking behaviour, and cannot let HR run a pilot with adjusted weights. There is also no versioning: even if the constants were editable, changing them would silently rewrite the meaning of historical scores, and finalize_scoring already requires the full current indicator set, so any mid-cycle change invalidates in-flight drafts.

**Recommended fix**

Introduce a versioned scoring configuration: a scoring_scheme record holding section weights, per-indicator weights, evidence rules and the threshold-to-recommendation table, with an activation date and an immutable version number. Stamp every evaluation_record with the scheme version it was created under, and have compute_result read the record's scheme rather than the constants — this makes history stable by construction. Build the HR editor with a preview that shows how the last N finalized evaluations would have been classified under the draft scheme before activation, and require a second HR approval to activate. Keep the current constants as the seed for version 1 so nothing breaks.

**Product & business impact**

This is the difference between a bespoke internal system and a sellable product, and it is also the fix that makes indicator and threshold changes safe with respect to history.

**Dependencies**

- Scheme tables and record stamping migration
- compute_result and finalize_scoring refactor
- Enables P1-01, P1-06 and most of the roadmap

### P1-05 · P1 · Indicators are mutable and unversioned, so editing the framework rewrites the meaning of past evaluations and breaks in-flight drafts

| Field | Value |
|---|---|
| Finding ID | P1-05 |
| Priority | P1 |
| Category | Product capability |
| Implementation difficulty | Medium |
| Business impact score | 7 / 10 |
| Implementation effort score | 4.5 / 10 |
| Confidence | High |

**Current state**

HR can create, edit, reorder and delete indicators; deletion is blocked with a 409 once the indicator has been scored, which protects referential integrity but not semantics. finalize_scoring requires the scored set to equal the set of all currently-active indicators. Finalized records keep a final_snapshot (SNAPSHOT_VERSION = 1) capturing the indicator text as evaluated.

**Exact repository evidence**

```text
The indicators router exposes CRUD plus reorder with a scored-indicator delete guard; finalize_scoring compares scored_ids against the active indicator keys; snapshot.py writes the evaluated indicator content into final_snapshot at finalization.
```

**File path & location**

```text
backend/app/api/routers/indicators.py · backend/app/services/workflow.py:159-189 · backend/app/services/snapshot.py
```

**Gap / risk / missing capability**

Two distinct failures. Operationally, adding or deactivating an indicator while evaluations are in draft makes every one of those drafts un-submittable or silently changes what completeness means — with no warning to HR that they have just broken twelve in-flight cases. Analytically, indicator text can be rewritten in place, so a trend chart comparing 'indicator 7' across two years may be comparing two different questions; the snapshot rescues the finalized document but not the comparison. Neither problem is visible to the person making the edit.

**Recommended fix**

Version the framework rather than the row: make an indicator set immutable once used, with edits creating a new version, and bind each evaluation (and each period) to a version. Where an in-place edit is genuinely intended, restrict it to typography and require a reason that is audit-logged. Add a pre-save impact warning naming the open records the change would affect, and block deactivation while any open draft depends on the indicator. In analytics, compare only within a framework version and mark cross-version series explicitly.

**Product & business impact**

Protects both HR's day-to-day confidence and the credibility of any longitudinal claim the product makes about an employee's trajectory.

**Dependencies**

- Framework-version tables (share with P1-04's scheme versioning)
- finalize_scoring change

### P1-06 · P1 · No self-assessment, no 360 input, and no calibration — the result is one manager's opinion with no correction mechanism

| Field | Value |
|---|---|
| Finding ID | P1-06 |
| Priority | P1 |
| Category | Product capability |
| Implementation difficulty | High |
| Business impact score | 8 / 10 |
| Implementation effort score | 7 / 10 |
| Confidence | High |

**Current state**

Scores come from exactly one evaluator per section path (the unit supervisor, or the deputy on the manager path). HR and the deputy can approve or return the whole record but there is no transition that adjusts an individual score. No peer, upward or multi-rater input exists (360 is explicitly out of scope in the README). No calibration session, cross-manager comparison, rater-leniency detection or distribution guidance exists.

**Exact repository evidence**

```text
TRANSITIONS provides approve/return only, with no score-adjustment action; the README lists 360-degree evaluation as out of scope; reports.py can display distributions but no endpoint writes an adjustment.
```

**File path & location**

```text
backend/app/services/workflow.py TRANSITIONS · README.md out-of-scope · backend/app/api/routers/reports.py
```

**Gap / risk / missing capability**

Single-rater scoring is systematically biased — leniency, severity, recency and halo effects are the most documented findings in performance measurement — and DbsPulse currently has no instrument to detect or correct any of them, while using the output to recommend whether a contract continues. Two managers applying different standards produce incomparable numbers that nonetheless meet the same numeric renewal thresholds. Because the only remedy is returning the entire record, HR's practical choice is to accept a score they doubt or restart the case.

**Recommended fix**

Sequence it. First calibration, which needs no new input source: an HR view grouping open or recently finalized cases by unit and manager showing distribution, mean and rater deviation, plus a formal calibration session object where a documented, audited adjustment with a mandatory reason can be applied to a specific score before finalization — never silently. Then self-assessment (see P0-06) as a second perspective displayed beside the manager's. Then optional lightweight multi-rater input for managers only — two or three peers, aggregated and shown as context, not merged into the score — which is the honest way to enter 360 territory without the anonymity and rater-set machinery of a full suite.

**Product & business impact**

Calibration is what makes scores comparable across units, and comparability is what makes a threshold-based renewal recommendation defensible. It is also a visible enterprise-maturity signal in evaluations against Lattice or SuccessFactors.

**Dependencies**

- P0-06 employee stage
- Score-adjustment transition and audit events
- Analytics groundwork

### P2-01 · P2 · Analytics exist only for HR — managers and executives have no analytical surface of their own

| Field | Value |
|---|---|
| Finding ID | P2-01 |
| Priority | P2 |
| Category | Product capability |
| Implementation difficulty | Medium |
| Business impact score | 7 / 10 |
| Implementation effort score | 4 / 10 |
| Confidence | High |

**Current state**

Four report endpoints and the audit-log viewer are HR-only. Seven dashboard endpoints exist, including a per-role overview that gives supervisors, deputies and the CEO their pending queues and basic counts, but nothing comparable to HR's filtered analytics.

**Exact repository evidence**

```text
reports.py gates every endpoint on the HR role; dashboard.py provides role-overview queues and counts rather than analysis.
```

**File path & location**

```text
backend/app/api/routers/reports.py · backend/app/api/routers/dashboard.py
```

**Gap / risk / missing capability**

A unit supervisor cannot see how their own scoring distribution compares to the organisation, which is the single most useful piece of feedback a rater can receive. The CEO gets a queue, not a view of workforce risk, unit performance or renewal exposure. The result is that the data DbsPulse already holds informs one department's decisions and nobody else's, which caps perceived value at 'HR paperwork tool'.

**Recommended fix**

Add two scoped analytics surfaces reusing the existing filter machinery: a manager view limited to their own assigned personnel (own distribution versus organisation mean, evidence-quality rate, time to complete their stage) and an executive view of aggregates only — unit comparison, renewal-recommendation mix, cycle time, contract-expiry pipeline. Both must route through the minimum-cohort suppression from P1-08 and through record-level drill-down checks, so opening analytics does not open individuals.

**Product & business impact**

Turns collected data into decisions for the two roles that hold budget and authority, and gives raters the feedback loop that improves scoring quality over time.

**Dependencies**

- P1-08 minimum-cohort suppression is a hard prerequisite
- Scoped query helpers

### P2-03 · P2 · No bulk operations — an annual cycle for a whole company is created one evaluation at a time

| Field | Value |
|---|---|
| Finding ID | P2-03 |
| Priority | P2 |
| Category | Product capability |
| Implementation difficulty | Medium |
| Business impact score | 7 / 10 |
| Implementation effort score | 3.5 / 10 |
| Confidence | High |

**Current state**

create_evaluation handles a single employee: it validates active personnel, requires an EvaluationAccess row, chooses the manager or standard path, guards against duplicate open records and returns a 409 with the conflicting id. periods.py can report progress across a cohort but cannot create one.

**Exact repository evidence**

```text
evaluations.py:117-235 is single-record; periods.py exposes list, create, close and progress with no bulk-create action.
```

**File path & location**

```text
backend/app/api/routers/evaluations.py:117-235 · backend/app/api/routers/periods.py
```

**Gap / risk / missing capability**

Opening a cycle for two hundred employees means two hundred manual creations, each of which can fail for its own reason (inactive personnel, missing access row, an existing open record) with no consolidated report of what succeeded. This is the moment HR most needs the tool to help and most likely to abandon it for a spreadsheet. The same absence applies to bulk access assignment and bulk reminders.

**Recommended fix**

Add a period-scoped bulk create that takes a cohort definition (unit, status, contract window), performs a dry run reporting exactly which employees would be created, skipped or blocked and why, then executes idempotently in one transaction per record so partial failure is survivable — returning a per-employee outcome list. Reuse the existing duplicate guard rather than bypassing it. Add bulk evaluation-access assignment by unit and a bulk reminder action from the at-risk queue.

**Product & business impact**

Removes the largest single piece of HR manual labour and makes period-based cycles practical, which is what makes P1-07 worth enabling.

**Dependencies**

- P1-07 periods enabled
- Dry-run reporting UI

### P2-08 · P2 · Reporting has no saved views, scheduled delivery, or cross-period comparison

| Field | Value |
|---|---|
| Finding ID | P2-08 |
| Priority | P2 |
| Category | Product capability |
| Implementation difficulty | Medium |
| Business impact score | 5 / 10 |
| Implementation effort score | 3.5 / 10 |
| Confidence | High |

**Current state**

Reports are computed on demand from query-parameter filters and can be exported to Excel. Nothing is saved, scheduled or compared across periods; the fifth export is also the one that is not audit-logged.

**Exact repository evidence**

```text
reports.py builds ad-hoc filtered queries with no saved-view model and no scheduling; export_report_excel:300-321 lacks a log_event call.
```

**File path & location**

```text
backend/app/api/routers/reports.py
```

**Gap / risk / missing capability**

HR rebuilds the same filter combination every month, cannot hand a stable definition to an executive, and cannot answer the question that actually matters — 'is performance improving' — because there is no period-over-period comparison. Manual re-exporting is also what drives sensitive spreadsheets into email.

**Recommended fix**

Add saved report definitions (owner, filters, visibility) and scheduled delivery of a link — never an attachment — through the notification channel of P1-03, with every execution audit-logged. Add period-over-period comparison once periods are enabled, including unit-level movement and distribution shift, respecting the minimum-cohort rule.

**Product & business impact**

Reduces recurring HR effort and replaces spreadsheet circulation with governed, logged access.

**Dependencies**

- P1-07 periods
- P1-03 delivery channel
- P1-08 suppression
- P1-09 export logging

---

## Workflow realism (5)

Whether the process is genuinely enforced by backend and database logic, and whether the interface tells the truth about it.

### P0-02 · P0 · No cancel, void or reassign transition — a single departed approver permanently blocks an employee from ever being evaluated again

| Field | Value |
|---|---|
| Finding ID | P0-02 |
| Priority | P0 |
| Category | Workflow integrity |
| Implementation difficulty | Low |
| Business impact score | 9 / 10 |
| Implementation effort score | 2.5 / 10 |
| Confidence | High |

**Current state**

The transition table defines exactly seven actions, all of which move a record forward or one stage back. There is no cancel, void, withdraw, delete, or reassign endpoint, and no way to change unit_supervisor_user_id, deputy_user_id or ceo_user_id on an existing record. A record only leaves the open state by reaching CEO finalization.

**Exact repository evidence**

```text
TRANSITIONS contains submit, hr_approve, hr_return, deputy_approve, deputy_return, ceo_finalize and the manager-path equivalent — no terminal action other than finalization. The evaluations router exposes no DELETE and no assignee-mutation endpoint. Meanwhile the partial unique index uq_open_evaluation_per_personnel forbids a second record for the same person while status != 'finalized'.
```

**File path & location**

```text
backend/app/services/workflow.py TRANSITIONS · backend/app/api/routers/evaluations.py (no cancel / reassign route) · backend/alembic/versions/b41c07a9d2e1_phase0_integrity_constraints.py:42-48
```

**Gap / risk / missing capability**

Two safeguards combine into a trap. If an assigned approver resigns, is deactivated, changes role, or was simply assigned by mistake, their stage can never be completed — the transition requires current_user.id to equal the stored assignee — and the unique index simultaneously prevents opening a replacement record. That employee becomes permanently un-evaluable, which in this product means their contract renewal has no supporting document. The only remedy is manual SQL against production, which is itself unaudited and destroys the integrity story the rest of the system is built on.

**Recommended fix**

Add two HR-only transitions to the declarative table so they inherit the existing lock, validation and audit path: (1) cancel_evaluation, moving any non-finalized record to a new terminal 'cancelled' status with a mandatory reason — and adjust the partial index predicate to status NOT IN ('finalized','cancelled') so a replacement can be opened; (2) reassign_stage_owner, replacing a single assignee with a validated active user of the correct role, logging old and new values. Both must write audit entries and notify affected parties. Add a startup or nightly integrity check that flags open records whose current assignee is inactive.

**Product & business impact**

Removes the only failure mode in the workflow that requires database surgery to recover from. Organisational churn is normal; today every departure silently creates orphaned cases that HR discovers at the worst possible moment — contract-renewal time.

**Dependencies**

- Index predicate change requires a migration
- Audit event types for cancel / reassign

### P0-05 · P0 · Score and comment writes bypass the row lock used by transitions, leaving a lost-update and write-after-submit window

| Field | Value |
|---|---|
| Finding ID | P0-05 |
| Priority | P0 |
| Category | Workflow integrity |
| Implementation difficulty | Low |
| Business impact score | 8 / 10 |
| Implementation effort score | 2 / 10 |
| Confidence | Medium |

**Current state**

Transition endpoints fetch the record through _get_record_or_404_for_update, which applies .with_for_update(of=EvaluationRecord). upsert_scores and set_evaluator_comment fetch through the unlocked _get_record_or_404 and then write child rows, relying on the (record, indicator) unique constraint for row identity but on nothing for record-state consistency.

**Exact repository evidence**

```text
_get_record_or_404_for_update at lines 60-78 uses with_for_update(of=EvaluationRecord) and is called only by the transition handlers; upsert_scores at 421-456 and set_evaluator_comment at 459-487 call the unlocked helper. The frontend auto-saves score drafts as the evaluator types, which increases write frequency against exactly these endpoints.
```

**File path & location**

```text
backend/app/api/routers/evaluations.py:60-78, :421-456, :459-487 · AGENTS.md (auto-save behaviour)
```

**Gap / risk / missing capability**

Two concrete races. First, if a score write is in flight when the same evaluator (or a second one, since the deputy also scores on the manager path) submits, the status check inside upsert_scores can pass against a state that submit is concurrently changing — allowing a write to land against a record that has already left the drafting stage, after finalize_scoring computed the percentages. The stored scores would then disagree with the stored result. Second, two evaluators editing the same indicator produce a last-writer-wins overwrite with no version check and no indication to either user that their value was replaced. Neither behaviour is covered by a test: test_workflow_concurrency.py holds two tests and its docstring states it does not perform a genuine two-connection race.

**Recommended fix**

Use _get_record_or_404_for_update in upsert_scores and set_evaluator_comment as well — the lock is already written and the added contention is negligible at this write volume. Add optimistic concurrency for the editing UI: a version or updated_at column returned with the draft and echoed on save, answering 409 when stale so the user is told rather than silently overwritten. Then add real race tests using two sessions on two connections asserting that exactly one of two simultaneous submits succeeds and that a score write racing a submit is rejected.

**Product & business impact**

Protects the arithmetic integrity of the one number the entire product exists to produce. A stored final percentage that does not match the stored scores is indefensible in a contract dispute and impossible to explain after the fact.

**Dependencies**

- Version column migration for optimistic concurrency (the lock fix alone needs none)

### P0-06 · P0 · The employee has no voice: no self-assessment, no visibility before the decision, no objection path, and no access to the signed document about them

| Field | Value |
|---|---|
| Finding ID | P0-06 |
| Priority | P0 |
| Category | Trust and fairness |
| Implementation difficulty | Medium |
| Business impact score | 10 / 10 |
| Implementation effort score | 5.5 / 10 |
| Confidence | High |

**Current state**

None of the seven transitions has an employee actor. _ensure_can_view admits HR plus the three chain members, so the subject cannot see the record while it is being decided; the employee list branch of list_evaluations returns only their own finalized records. After finalization the employee can acknowledge ('رؤیت'), which writes acknowledged_at and acknowledged_by, and can view their scorecard and own open improvement plans. summary_pdf is HR-only.

**Exact repository evidence**

```text
TRANSITIONS has no employee-role entry; _ensure_can_view at lines 81-88 tests membership in {unit_supervisor_user_id, deputy_user_id, ceo_user_id} with an HR bypass; list_evaluations at 300-373 restricts the employee branch to finalized records; the summary_pdf endpoint is decorated for HR only, and the frontend PDF button is rendered only for HR (EvaluationDetailPage.tsx:461).
```

**File path & location**

```text
backend/app/services/workflow.py TRANSITIONS · backend/app/api/routers/evaluations.py:81-88, :300-373, summary_pdf · backend/app/api/routers/me.py · frontend/src/pages/EvaluationDetailPage.tsx:461
```

**Gap / risk / missing capability**

The output of this system is a recommendation about whether a person's employment continues. That recommendation is produced entirely by managers, about the employee, without the employee contributing evidence, seeing the assessment while it can still be changed, or being able to formally contest it afterwards. Acknowledgment records that they saw a decision, not that they were heard. They cannot even obtain the hash-verified PDF that documents the decision — the only actor who can download it is HR. Every benchmark product (Workday, SuccessFactors, Lattice, 15Five, Leapsome) treats employee input as a first-class stage, and any labour-law review will ask what the employee said. Right now the answer is: nothing was recorded.

**Recommended fix**

Add an employee stage and an appeal path to the same declarative machine so they inherit locks, validation and audit. (1) An optional self_assessment stage before supervisor scoring: the employee submits their own indicator ratings plus achievement notes, shown side-by-side with the manager's during scoring but never averaged into the result. (2) An employee comment right on the finalized record, and a 'ثبت اعتراض' (file objection) transition available for a configurable window after acknowledgment, which notifies HR, opens a review task and is visible in the audit log and the archived record. (3) Let the subject download their own summary PDF — the same document, no HR gate, logged as a document access. (4) Show the employee a status-only view (which stage, since when) while the case is open, without exposing draft scores.

**Product & business impact**

Turns a manager-only judgement into a defensible two-sided process. This is simultaneously the largest fairness gap, the largest adoption risk (employees experience the product as something done to them), and one of the cheapest credibility wins available.

**Dependencies**

- New status values and transitions
- Self-assessment score storage separate from evaluation_scores
- Employee notification surface
- PDF authorization change

### P1-02 · P1 · Deadlines are advisory only, and the SLA sweep measures total case age instead of time in the current stage

| Field | Value |
|---|---|
| Finding ID | P1-02 |
| Priority | P1 |
| Category | Workflow integrity |
| Implementation difficulty | Low |
| Business impact score | 8 / 10 |
| Implementation effort score | 2.5 / 10 |
| Confidence | High |

**Current state**

run_sla_sweep selects records whose EvaluationRecord.created_at is older than a cutoff, maps status to the current owner via _current_owner_ids, and sends a deduplicated in-app notification. Nothing is blocked when a deadline passes, no stage has its own due date, and nothing escalates to a higher role.

**Exact repository evidence**

```text
run_sla_sweep filters on created_at <= cutoff while the notification text tells the recipient the item is waiting for their action; _current_owner_ids resolves the owner from status; notify_once prevents repeat rows; there is no due_date column on evaluation_records and no escalation target in the code.
```

**File path & location**

```text
backend/app/services/scheduled.py run_sla_sweep · _current_owner_ids · backend/app/models/evaluation.py
```

**Gap / risk / missing capability**

Measuring from creation makes the signal wrong in both directions. A case that reached the CEO yesterday but was opened six weeks ago notifies the CEO as overdue on their first day of ownership; a case that has sat one week in HR after being created a week ago never fires. Any return-and-resubmit cycle guarantees permanent overdue status. Because the only consequence is a notification to the person who is already ignoring the case, the mechanism cannot recover a stalled process — there is no escalation to the deputy or CEO, no HR dashboard of at-risk cases with an ageing figure, and no configurable per-stage service level.

**Recommended fix**

Track stage entry explicitly: add stage_entered_at (set on every transition) and compute overdue as now - stage_entered_at > the stage's configured limit; keep created_at for total cycle-time reporting, which is a genuinely useful separate metric. Make limits configurable per stage in HR settings rather than as constants. Add a two-step escalation — reminder to the owner, then notification to the owner's escalation target and to HR — and an 'at risk' HR queue sorted by days in stage. Record time-in-stage per transition so cycle-time analytics come free.

**Product & business impact**

Converts a noisy notification into a reliable operational control, and produces the cycle-time metric that lets HR prove the process got faster — the strongest quantitative argument for keeping the product.

**Dependencies**

- stage_entered_at migration
- Depends on P0-08 for the sweep to actually run
- Configuration store from P1-04

### P1-07 · P1 · Evaluation periods are fully built server-side but hidden behind a disabled feature flag while the README presents them as a feature

| Field | Value |
|---|---|
| Finding ID | P1-07 |
| Priority | P1 |
| Category | Release management |
| Implementation difficulty | Low |
| Business impact score | 7 / 10 |
| Implementation effort score | 2.5 / 10 |
| Confidence | High |

**Current state**

periods.py implements list, create, close and progress, enforces a single-open-period rule with a partial unique index, and notifies evaluators when a period opens. evaluation_records carries period_id with a supporting index. The frontend route renders <DisabledFeature title="دوره‌های ارزیابی" /> because FEATURE_PERIODS_ENABLED is false.

**Exact repository evidence**

```text
FEATURE_PERIODS_ENABLED = false at frontend/src/appInfo.ts:13; App.tsx substitutes the DisabledFeature component on that route; periods.py is complete and migration b7e94d02c158 adds the table, the one-open-period index and the record's period_id index; README.md describes periods as part of the system.
```

**File path & location**

```text
frontend/src/appInfo.ts:13 · frontend/src/App.tsx · backend/app/api/routers/periods.py · backend/alembic/versions/b7e94d02c158_phase3_evaluation_periods.py · README.md
```

**Gap / risk / missing capability**

Paid-for work is delivering no value, and the documentation actively misleads. Users see a navigation entry that leads to a disabled panel; a reviewer reading the README believes campaign management exists; an auditor clicking through concludes it does not. Meanwhile the API remains reachable to authorised callers, so the flag hides the UI without hiding the capability — a discoverability gap rather than a control. Nothing in the repository records why the flag is off, what would satisfy turning it on, or who owns that decision.

**Recommended fix**

Decide explicitly and remove the ambiguity. If periods are ready, finish the UI (period list, open/close with cohort preview, progress by unit, per-period reporting), enable the flag and cover it with tests. If they are not, state the specific blockers in the README and mark the capability as planned rather than delivered. Either way, adopt a convention that a flag has an owner, a rationale and an exit date, and that navigation never renders an entry for a disabled feature.

**Product & business impact**

Periods are the natural container for the entire annual cycle — cohort creation, progress tracking, per-period analytics and comparison — so this is the cheapest large capability gain available: most of the cost is already sunk.

**Dependencies**

- Frontend period screens
- Decision on bulk cohort creation (P2-03)

---

## Security & access control (8)

Authentication, session security, record-level authorization, privilege separation, sensitive-data exposure and audit integrity.

### P0-01 · P0 · Demo accounts with a published shared password are seeded by a migration that runs on every production boot

| Field | Value |
|---|---|
| Finding ID | P0-01 |
| Priority | P0 |
| Category | Security |
| Implementation difficulty | Low |
| Business impact score | 10 / 10 |
| Implementation effort score | 1.5 / 10 |
| Confidence | High |

**Current state**

Migration 1eaa459f4dde unconditionally inserts five users — hr1, sup1, sup2, dep1, ceo1 — all with the same password, plus three personnel rows and their evaluation-access rows. docker-entrypoint.sh executes 'alembic upgrade head' every time the backend container starts, so these accounts are created in any environment that has ever been migrated, including production. The password is additionally published in README.md and AGENTS.md.

**Exact repository evidence**

```text
DEMO_PASSWORD = "DbsPulse@12345" at line 23, followed by an unconditional upgrade() that inserts the five users; the entrypoint applies all migrations at boot; the same password appears in repository documentation.
```

**File path & location**

```text
backend/alembic/versions/1eaa459f4dde_seed_sample_users_personnel_access.py:23 · backend/docker-entrypoint.sh · README.md · AGENTS.md
```

**Gap / risk / missing capability**

A remote attacker who reads the public repository has five valid credential pairs, one of which (hr1) is the system's de-facto super-admin: it can read every employee's evaluation, reset any password, edit indicators, and approve or return any record. Because the seed is a migration rather than a script, deleting the users is not enough — the schema records the migration as applied, but any fresh environment recreates them, and operators who assume demo data is dev-only will not check.

**Recommended fix**

Make the seed conditional and non-secret: gate the entire upgrade body on an explicit SEED_DEMO_DATA environment flag defaulting to false, or move seeding out of Alembic into a separate 'seed' console command that the Compose file calls only for the dev profile. Add a follow-up migration that deactivates any user still holding the demo hash. Force must_change_password on any seeded account. Remove the literal password from README.md and AGENTS.md and replace it with an instruction to generate one. Add a startup assertion that refuses to boot in production if any user's password hash matches the known demo hash.

**Product & business impact**

Full compromise of all employee performance data and of the contract-renewal decision record. For an HR system this is simultaneously a data-protection incident, an employment-law exposure and an unrecoverable trust failure with the first enterprise customer that runs a security review.

**Dependencies**

- None — can ship immediately

### P0-03 · P0 · Any HR user can approve or return any evaluation, and the HR role is also the super-admin — no separation of duties

| Field | Value |
|---|---|
| Finding ID | P0-03 |
| Priority | P0 |
| Category | Authorization |
| Implementation difficulty | Medium |
| Business impact score | 9 / 10 |
| Implementation effort score | 5 / 10 |
| Confidence | High |

**Current state**

hr_approve and hr_return declare assignee_field = None, so ensure_transition_allowed skips the record-level ownership check that supervisor, deputy and CEO actions are subject to. Separately, the HR role alone gates user creation, password reset, activation, indicator CRUD, evaluation-access assignment, all improvement-plan operations, all analytics, all exports, the audit-log viewer, and the manual sweep trigger.

**Exact repository evidence**

```text
In TRANSITIONS the HR entries pass assignee_field=None while the supervisor/deputy/CEO entries name unit_supervisor_user_id / deputy_user_id / ceo_user_id; ensure_transition_allowed only compares user id when assignee_field is not None. require_roles(UserRole.hr) appears on every endpoint of users.py, indicators.py, improvement_plans.py, reports.py, audit_log.py and admin.py.
```

**File path & location**

```text
backend/app/services/workflow.py TRANSITIONS + ensure_transition_allowed · backend/app/api/routers/users.py · backend/app/api/routers/improvement_plans.py · backend/app/api/routers/audit_log.py
```

**Gap / risk / missing capability**

There is no notion of an HR case owner, so in an organisation with several HR staff, accountability for 'who was responsible for this case' does not exist — only 'who happened to click'. More seriously, one compromised or malicious HR account can reset the CEO's password, log in as CEO, finalize an evaluation, and then read (and export) the audit log that describes what it did. The role model has no auditor, no read-only HR analyst, and no admin separate from process participant.

**Recommended fix**

Split the concern in two steps. Short term: add hr_user_id to evaluation_records, set it when HR first touches the case, and set assignee_field='hr_user_id' for hr_approve/hr_return, with an explicit, audited HR-lead 'claim / hand over' action for legitimate reassignment. Medium term: decompose HR into distinct roles — hr_operator (process actions), hr_admin (users, indicators, configuration), hr_analyst (read-only reports), auditor (read-only audit log, no data mutation) — and forbid the account that resets a password from acting in that user's stage. Log every password reset as a security event visible to a role HR cannot self-grant.

**Product & business impact**

Converts 'HR is trusted with everything' into a defensible control model. Separation of duties is a standard question in enterprise procurement and in any labour dispute about who altered a performance record.

**Dependencies**

- Schema migration for hr_user_id
- Role enum expansion touches deps.py and every router
- Frontend role gating and navigation

### P0-04 · P0 · Login rate limiting can be bypassed with a spoofed header, and there is no per-account lockout

| Field | Value |
|---|---|
| Finding ID | P0-04 |
| Priority | P0 |
| Category | Security |
| Implementation difficulty | Medium |
| Business impact score | 9 / 10 |
| Implementation effort score | 3.5 / 10 |
| Confidence | Medium |

**Current state**

Login is limited to 10 requests per minute and refresh to 30 per minute using slowapi with key_func = get_remote_address. The limiter is constructed with no storage backend, so counters live in the worker process's memory. nginx sets X-Forwarded-For using $proxy_add_x_forwarded_for, which appends the client-supplied value to the chain, and uvicorn is started with --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}", trusting any proxy by default.

**Exact repository evidence**

```text
backend/app/core/rate_limit.py is four lines: Limiter(key_func=get_remote_address) with no storage_uri. auth.py decorates login with @limiter.limit("10/minute"). The nginx template forwards $proxy_add_x_forwarded_for. The entrypoint passes --proxy-headers --forwarded-allow-ips with a wildcard default.
```

**File path & location**

```text
backend/app/core/rate_limit.py (whole file) · backend/app/api/routers/auth.py · frontend/nginx/default.conf.template · backend/docker-entrypoint.sh
```

**Gap / risk / missing capability**

Because the trusted-proxy list is a wildcard and the forwarded chain includes attacker-controlled content, the address slowapi keys on is influenced by the request itself — rotating a header value plausibly resets the counter, making the per-IP limit ineffective against a scripted attack. Even where the header is handled correctly, the design has two further holes: counters are per-process, so N workers multiply every limit by N and a restart clears all state; and nothing at all counts failures per username, so a slow distributed attempt against a known account — such as the seeded hr1 from P0-01 — is unconstrained. Argon2 hashing and the dummy-hash timing defence protect the secret but not the account.

**Recommended fix**

Three changes. (1) Determine the client IP from a fixed, trusted position in the chain: set real_ip_header/set_real_ip_from in nginx, or replace $proxy_add_x_forwarded_for with an overwriting X-Forwarded-For, and replace the wildcard FORWARDED_ALLOW_IPS with the proxy's actual address. (2) Give the limiter shared storage (Redis or the existing PostgreSQL) so limits are global and survive restarts. (3) Add per-username failure counting with progressive delay and temporary lockout, persisted server-side, plus an audit event and an HR notification on lockout. Add a CAPTCHA or step-up challenge after a threshold.

**Product & business impact**

Credential brute force is the most likely real-world attack path against this system, and the payload behind a successful login is every employee's performance history and contract recommendation.

**Dependencies**

- Verify uvicorn 0.34.0 XFF selection behaviour before relying on it
- Shared store (Redis) or a DB-backed counter table
- nginx configuration change

### P1-08 · P1 · Analytics and exports have no minimum-cohort suppression, so filtering to a small unit discloses individuals

| Field | Value |
|---|---|
| Finding ID | P1-08 |
| Priority | P1 |
| Category | Privacy |
| Implementation difficulty | Low |
| Business impact score | 7 / 10 |
| Implementation effort score | 2 / 10 |
| Confidence | High |

**Current state**

Four HR-only report endpoints build composable filters (unit, status, date range, score range) over evaluation data and return aggregates — counts, averages, distributions. There is no minimum group size, no suppression of small cells, and no warning. The Excel report export applies the same filters with no suppression.

**Exact repository evidence**

```text
reports.py builds queries from the _Filters helper and returns aggregates directly with no group-size check anywhere in the module; export_report_excel at lines 300-321 serialises the same filtered result.
```

**File path & location**

```text
backend/app/api/routers/reports.py · _Filters · export_report_excel:300-321
```

**Gap / risk / missing capability**

Aggregation is not anonymisation. Filtering to a unit with two employees turns 'average final score' into an individual's score, and combining a unit filter with a score-range filter identifies exactly who scored below sixty — information that the record-level permission model deliberately withholds from anyone outside that person's chain. Today the only actor with report access is HR, which limits blast radius, but it also means the safeguard is 'only the most privileged role can see it' rather than a control; the moment managers or executives get the analytics they need (P2-01), the same endpoints leak individuals by construction. The exported spreadsheet then leaves the system entirely, with no suppression and — uniquely among the exports — no audit record.

**Recommended fix**

Enforce a minimum cohort size (five is a reasonable default, configurable) in a single place all report queries pass through: below the threshold, return a suppressed marker instead of a value and label it in the UI and the export. Block filter combinations that reduce the cohort below the threshold rather than answering them. Apply the same rule to any future manager or executive analytics, and add drill-down permission checks so that expanding an aggregate returns only records the caller may already see. Log every report execution and export with its filter set.

**Product & business impact**

Prevents the analytics surface from silently becoming a bypass around the record-level authorization the rest of the system implements properly — a prerequisite for opening analytics beyond HR.

**Dependencies**

- Threshold belongs in the configuration store (P1-04)
- Blocks safe delivery of P2-01

### P1-09 · P1 · The audit log is append-only by convention only, and two mutation paths are not logged at all

| Field | Value |
|---|---|
| Finding ID | P1-09 |
| Priority | P1 |
| Category | Auditability |
| Implementation difficulty | Medium |
| Business impact score | 8 / 10 |
| Implementation effort score | 4 / 10 |
| Confidence | High |

**Current state**

log_event inserts an audit_log row with evaluation record, actor, event type, old and new JSONB values and a timestamp, covering roughly 35 event types including transitions, score writes, user and indicator administration and four of five exports. HR can browse and export the log. Rows live in the application's own database, written by the application's own credentials.

**Exact repository evidence**

```text
audit.py performs a plain insert with no chaining or signature; audit_log.py exposes the HR viewer and xlsx export with an _EVENT_LABELS map of about 35 types; export_report_excel in reports.py:300-321 has no log_event call; the goal add, update and delete endpoints in improvement_plans.py write no audit entry.
```

**File path & location**

```text
backend/app/services/audit.py · backend/app/models/audit_log.py · backend/app/api/routers/reports.py:300-321 · backend/app/api/routers/improvement_plans.py
```

**Gap / risk / missing capability**

The audit log is the evidence base for any dispute about a performance decision, so its integrity properties matter as much as its coverage. Nothing prevents an UPDATE or DELETE against audit_log: there is no hash chain linking each entry to its predecessor, no signature, no write-once storage, and no replication to a store outside the application's control — so the log proves what happened only to someone who already trusts whoever holds database access, which per P0-03 is the same role the log is meant to hold accountable. Coverage has two concrete holes as well: improvement-plan goals — the content of a remedial plan attached to a contract decision — can be added, rewritten or deleted with no trace, and the report export is the one data-egress path that leaves no record of who extracted what.

**Recommended fix**

Harden and complete. Add a tamper-evident chain: each row stores the hash of its own canonical content plus the previous row's hash, with a periodic verification job and an HR-visible integrity status. Revoke UPDATE and DELETE on audit_log from the application's database role and write through an INSERT-only path. Ship entries to an external append-only sink (managed log service or WORM object storage) so an in-database alteration is detectable. Then close the coverage gaps: log goal create/update/delete with old and new values, and log report exports with the filter set and row count, as the other four exports already do.

**Product & business impact**

An audit trail that cannot be quietly edited is what lets an employer defend a non-renewal, and what lets an employee trust the process. Without it the existing log is documentation, not evidence.

**Dependencies**

- Database role and privilege changes
- External sink decision
- Hash-chain migration and backfill

### P1-10 · P1 · Improvement plans are HR-only: the plan owner is notified but has no API to read or update the plan they own

| Field | Value |
|---|---|
| Finding ID | P1-10 |
| Priority | P1 |
| Category | Authorization |
| Implementation difficulty | Medium |
| Business impact score | 7 / 10 |
| Implementation effort score | 4 / 10 |
| Confidence | High |

**Current state**

All eleven improvement-plan endpoints are decorated with require_roles(UserRole.hr). The model carries owner_user_id, and the owner receives a notification when a plan is created. The employee can read their own open plans through the me router. Managers have no access of any kind, and goal mutations are unlogged.

**Exact repository evidence**

```text
Every route in improvement_plans.py carries require_roles(UserRole.hr); owner_user_id exists on the model and is used only as a notification target; me.py exposes read-only own-plan access for the employee.
```

**File path & location**

```text
backend/app/api/routers/improvement_plans.py · backend/app/models/improvement_plan.py · backend/app/api/routers/me.py
```

**Gap / risk / missing capability**

The workflow that turns a poor evaluation into an actual improvement is the one workflow only HR can operate. The named owner is told they own a plan and then cannot open it; the line manager who must coach the employee daily cannot see the goals, record progress or note that a milestone slipped; the employee sees a static list. Practically, all progress tracking happens outside the system — in conversation or in spreadsheets — which means the review sweep fires against data nobody has updated and the conditional-renewal recommendation that triggered the plan is never closed out with evidence. Combined with the missing goal audit trail, a plan's content can be revised after the fact with no record.

**Recommended fix**

Give the plan a real participant model: the owner (manager) can read and update their plans, add progress notes and mark goals complete; the employee can add their own progress comment and see status and history; HR retains creation, closure and oversight. Enforce this with record-level checks in the same style as _ensure_can_view rather than role-only gates. Audit-log every goal and status mutation with old and new values. Add plan effectiveness reporting — did the score improve at the next evaluation — which is the analytic that proves the whole mechanism works.

**Product & business impact**

Closes the loop between the decision and the remedy. It is also what makes 'تمدید مشروط به برنامه بهبود مکتوب' a managed process rather than a sentence in a PDF.

**Dependencies**

- Record-level permission helper
- P1-09 audit coverage
- Manager UI surface

### P2-02 · P2 · Excel exports write user-supplied text without neutralising formula-triggering prefixes

| Field | Value |
|---|---|
| Finding ID | P2-02 |
| Priority | P2 |
| Category | Security |
| Implementation difficulty | Low |
| Business impact score | 4 / 10 |
| Implementation effort score | 1 / 10 |
| Confidence | Medium |

**Current state**

Five exports build workbooks with openpyxl, appending values including employee full names, organisational units, evaluator comments, improvement-plan titles and audit values directly into cells. The module contains no sanitisation of leading =, +, - or @ characters.

**Exact repository evidence**

```text
backend/app/services/excel.py (263 lines) creates RTL sheets with bold headers and appends model values verbatim; a search of the module for sanitisation, escaping or startswith checks returns nothing.
```

**File path & location**

```text
backend/app/services/excel.py
```

**Gap / risk / missing capability**

openpyxl treats a string beginning with '=' as a formula rather than text, so free-text fields that reach a spreadsheet can carry an expression that executes in the recipient's Excel. Since evaluator comments and return reasons are unbounded free text written by authenticated internal users, the realistic scenario is an insider planting content that runs when HR opens the export — and HR is precisely the role that exports. Impact is bounded by Excel's own protections but the class of issue is well known and trivially preventable.

**Recommended fix**

Add one helper that all sheet writers pass strings through: prefix a value beginning with =, +, - or @ (or tab/carriage return) with an apostrophe, or write the cell explicitly as an inline string with data_type 's'. Cap free-text length at the schema level as well, which also addresses the unbounded-text storage concern. Add a test asserting that a name of '=1+1' exports as literal text.

**Product & business impact**

Removes a known export-injection class from the only data path that leaves the system, at almost no cost.

**Dependencies**

- None

### P2-06 · P2 · No MFA, no session visibility, no password expiry, and no HSTS in the shipped nginx template

| Field | Value |
|---|---|
| Finding ID | P2-06 |
| Priority | P2 |
| Category | Security |
| Implementation difficulty | Medium |
| Business impact score | 6 / 10 |
| Implementation effort score | 4 / 10 |
| Confidence | Medium |

**Current state**

Argon2 hashing, a minimum password length of ten, must_change_password support, refresh rotation with reuse detection and family revocation, token_version invalidation on password change, and a strict-samesite path-scoped refresh cookie. Sessions are stored server-side in auth_sessions with jti, rotation and revocation columns. The nginx template sets CSP, X-Frame-Options DENY, nosniff and Referrer-Policy but no Strict-Transport-Security; a separate HTTPS example config is referenced in the README and was not inspected.

**Exact repository evidence**

```text
security.py and auth.py implement the above; sessions.py implements rotation with a 60-second grace window and RefreshReuseError triggering revoke_all_for_user; the auth router exposes no session-list or per-session revoke endpoint and no MFA path; the nginx template omits HSTS.
```

**File path & location**

```text
backend/app/core/security.py · backend/app/api/routers/auth.py · backend/app/services/sessions.py · frontend/nginx/default.conf.template · deploy/nginx-https.conf.example (not inspected)
```

**Gap / risk / missing capability**

The session foundation is genuinely good — rotation with reuse detection and a token_version kill switch is better than most systems this size — which makes the remaining gaps worth closing rather than rebuilding. There is no second factor for the CEO and HR accounts whose actions are legally consequential; users cannot see or revoke their own active sessions, so a stolen refresh token is invisible to its owner; no credential ageing or reuse policy exists; and because the shipped template lacks HSTS, a first-visit downgrade is possible unless the separate HTTPS example is used, which the audit could not confirm.

**Recommended fix**

Add TOTP-based MFA, mandatory for HR and CEO and optional otherwise, with recovery codes and an audit event on enrolment and reset. Expose a session list (device, last-seen IP, created, last-used) with per-session and all-other-session revocation, reusing the existing auth_sessions columns. Add HSTS with a long max-age and preload to the terminating server, redirect HTTP to HTTPS, and reconcile the two nginx configurations so the secure one is the default. Consider shortening the rotation grace window and alerting HR on every reuse-detection event, since that signal means a token was replayed.

**Product & business impact**

Protects the two accounts whose compromise is most damaging and gives users the means to notice a compromise themselves.

**Dependencies**

- MFA enrolment UI
- Notification channel for security alerts (P1-03)
- nginx/TLS configuration

---

## Enterprise readiness (3)

Tenancy, integrations, retention, scheduled work and the operational capabilities enterprise buyers verify.

### P0-08 · P0 · Reminders and escalation are effectively off in production: the scheduler is in-process, defaults to disabled, and is unsafe with more than one replica

| Field | Value |
|---|---|
| Finding ID | P0-08 |
| Priority | P0 |
| Category | Enterprise readiness |
| Implementation difficulty | Medium |
| Business impact score | 8 / 10 |
| Implementation effort score | 3.5 / 10 |
| Confidence | High |

**Current state**

Three sweeps — contract expiry, SLA, improvement-plan review — run inside an asyncio loop in the API process. settings.enable_scheduler defaults to False. The scheduler module's own docstring states that a multi-instance deployment requires migration to a shared worker or queue. An HR-only admin endpoint can trigger a sweep manually.

**Exact repository evidence**

```text
backend/app/core/scheduler.py implements the loop and documents the multi-instance caveat; config.py declares enable_scheduler: bool = False; scheduled.py implements the three sweeps with notify_once deduplication; admin.py exposes the manual trigger to HR.
```

**File path & location**

```text
backend/app/core/scheduler.py · backend/app/core/config.py · backend/app/services/scheduled.py · backend/app/api/routers/admin.py
```

**Gap / risk / missing capability**

The time-based half of the workflow is the half that makes a performance process actually complete on schedule, and it is the half least likely to be running. Left at the default the sweeps never execute, so contract expiries are not surfaced, stalled approvals are never chased, and improvement-plan reviews come due silently — the product behaves as if it had no reminders at all. Turned on with two replicas, every notification is generated twice (the dedup key limits the damage but the sweep work itself duplicates), and there is no leader election, no locking, no run history, and no way to tell whether last night's sweep succeeded or the process was simply restarted mid-loop.

**Recommended fix**

Move scheduled work to a dedicated single-replica worker service in Compose with an explicit schedule, or keep it in-process but guard each sweep with a PostgreSQL advisory lock so only one instance runs it. Record every run in a scheduler_runs table (sweep name, started, finished, items processed, error) and expose it on an HR operations screen plus /api/health/ready, so 'reminders stopped working' becomes visible instead of invisible. Default enable_scheduler to true for the worker role and document the production topology.

**Product & business impact**

Without this, deadline management is a feature the README describes and operations does not have. With it, the SLA and contract-expiry sweeps become the mechanism that makes DbsPulse the system HR trusts to not miss a renewal.

**Dependencies**

- Compose topology change
- Advisory-lock or worker-role decision
- Pairs with P1-02 stage-age SLA fix

### P1-11 · P1 · No retention, deletion or legal-hold capability, and archived PDFs accumulate as bytes inside PostgreSQL forever

| Field | Value |
|---|---|
| Finding ID | P1-11 |
| Priority | P1 |
| Category | Enterprise readiness |
| Implementation difficulty | Medium |
| Business impact score | 7 / 10 |
| Implementation effort score | 5 / 10 |
| Confidence | High |

**Current state**

evaluation_documents stores the rendered PDF bytes plus its SHA-256 alongside the operational tables. Nothing in the codebase deletes or archives an evaluation, a document, an audit entry, a notification or a personnel record. There is no retention policy, no purge job, no export-for-subject capability, no anonymisation path, and no legal-hold flag.

**Exact repository evidence**

```text
documents.py writes pdf_bytes and sha256 into the EvaluationDocument row; no module in the repository issues a delete against evaluations, documents, notifications or audit rows; no retention configuration exists.
```

**File path & location**

```text
backend/app/services/documents.py · backend/app/models/ · backend/app/api/routers/
```

**Gap / risk / missing capability**

Two problems that look separate and are not. Legally, a system holding performance judgements about identifiable employees needs answers to how long data is kept, what happens when an employee leaves, how a subject-access request is served, and how a record under dispute is preserved from deletion — and DbsPulse has none, which is a hard blocker in any customer with a privacy or works-council review. Operationally, keeping every PDF as a bytea in the primary database inflates the table, the backup, the restore time and every full-table maintenance operation, on a row that is written once and read rarely — the classic case for object storage. There is also no backup, restore or disaster-recovery procedure in the repository; the underlying infrastructure is outside the repository and therefore not verifiable, but the absence of any documented procedure is itself a finding.

**Recommended fix**

Define retention as data, not as code: per-entity retention periods, a documented lawful basis, and a scheduled job that anonymises or purges beyond the window while honouring a legal_hold flag that blocks deletion on any record under dispute. Implement an employee data export and a manager-visible 'what we hold about you' view. Move PDF bytes to object storage (Cloudflare R2 or an S3-compatible bucket) keeping the SHA-256 and metadata in the database so verification is unchanged, and serve documents through short-lived signed URLs. Document backup schedule, restore test cadence and RPO/RTO targets, and prove the restore at least once.

**Product & business impact**

Turns a privacy blocker into a selling point, and removes the largest source of future database bloat before it becomes a migration project.

**Dependencies**

- Object storage decision and credentials
- Legal input on retention periods
- Verification endpoint must keep working during migration

### P1-14 · P1 · No SSO, no HRIS or payroll integration, no webhooks, no versioned public API

| Field | Value |
|---|---|
| Finding ID | P1-14 |
| Priority | P1 |
| Category | Enterprise readiness |
| Implementation difficulty | High |
| Business impact score | 8 / 10 |
| Implementation effort score | 7.5 / 10 |
| Confidence | High |

**Current state**

Authentication is username and password against the local users table only. Personnel data is entered or maintained through the UI. The only machine-facing surface is the same user-bearer API the frontend uses, with OpenAPI documentation deliberately disabled in production. No API keys, service accounts, webhooks or connectors exist. The README lists SSO and org-chart-driven access as out of scope.

**Exact repository evidence**

```text
deps.py resolves the caller only from a user access token; main.py disables docs in production; no integration module, webhook dispatcher or API-key model exists anywhere in the backend; README.md records the scope decision.
```

**File path & location**

```text
backend/app/api/deps.py · backend/app/main.py · backend/app/models/ · README.md
```

**Gap / risk / missing capability**

For an internal tool this is defensible. For a product it is a wall. Every organisation past a modest size already has an identity provider and a payroll or personnel system, and will refuse to maintain a second employee list by hand — duplicate personnel data drifts, leavers stay active, and contract_end_date, the field the contract-expiry sweep depends on, silently goes stale. Without webhooks or an API, DbsPulse cannot notify a payroll system of a renewal decision, cannot be embedded in an existing HR portal, and cannot be extended by the customer at all.

**Recommended fix**

Sequence by buyer pain. First a personnel synchronisation contract — a documented import/upsert API keyed on personnel_code with dry-run and diff reporting — so the employee list can be fed from the customer's system of record instead of typed. Then OIDC single sign-on alongside local accounts, with role mapping from IdP groups and a break-glass local admin. Then outbound webhooks for the events other systems care about (evaluation finalized, recommendation issued, plan opened or closed, contract expiry approaching), signed and retried through the same outbox as P1-03. Then a versioned, documented, key-authenticated read API scoped to service accounts with their own audit events. Publish OpenAPI for the public surface while keeping the internal one closed in production.

**Product & business impact**

Integration ability is usually what decides an enterprise deal after the demo, and personnel sync specifically removes the data-quality problem that would otherwise undermine the product's flagship contract-renewal alerting.

**Dependencies**

- OIDC library and IdP test tenant
- Service-account and API-key model
- Outbox from P1-03
- Audit events for machine callers

---

## Reliability & observability (2)

Failure handling, scaling edges, concurrency limits and whether production problems are visible.

### P1-12 · P1 · No metrics, tracing or error tracking — production failures are visible only as container logs

| Field | Value |
|---|---|
| Finding ID | P1-12 |
| Priority | P1 |
| Category | Observability |
| Implementation difficulty | Medium |
| Business impact score | 6 / 10 |
| Implementation effort score | 4 / 10 |
| Confidence | High |

**Current state**

Request-ID middleware tags each request and the 500 handler returns a non-leaking error while logging internally. /api/health and /api/health/ready exist. Beyond that there is no metrics endpoint, no tracing, no error-tracking integration, no structured log schema, and no run history for the scheduler.

**Exact repository evidence**

```text
main.py registers the request-ID middleware, the safe 500 handler and the two health routes; no Prometheus, OpenTelemetry or Sentry dependency appears in requirements; scheduler.py keeps no persistent record of its runs.
```

**File path & location**

```text
backend/app/main.py · backend/requirements.txt · backend/app/core/scheduler.py
```

**Gap / risk / missing capability**

The failure modes this system actually has are the quiet ones: a sweep that stopped running, a PDF render that degraded because a native library is missing, a spike in 401s from an attack, a query that got slow as evaluation volume grew, an approval that has sat untouched for a month. None of these raises an alarm today — they are discovered when a user complains, and diagnosed by reading container output. Health endpoints exist but nothing is described as watching them, and whether external monitoring is attached is not verifiable from the repository.

**Recommended fix**

Instrument the paths that matter rather than everything: request rate, latency and error rate per endpoint; authentication failures and rate-limit rejections; transitions per stage and time-in-stage; sweep runs with outcome and duration; PDF render success and fallback count; notification delivery outcomes once P1-03 lands. Emit structured JSON logs including the existing request ID and the actor's role — never scores or personal data. Add error tracking with release tagging, and alerts on: readiness failing, sweep not completed in 24 hours, error rate above baseline, and authentication failure spikes. Extend /api/health/ready to assert database connectivity, migration head match and last successful sweep.

**Product & business impact**

Determines whether the operations story is 'we knew and fixed it' or 'the customer told us'. It is also a standard procurement question for any HR system handling sensitive data.

**Dependencies**

- Monitoring backend choice (external infrastructure — not verifiable from the repository)
- Pairs with P0-08 scheduler run history

### P2-05 · P2 · Unbounded free-text fields, no explicit connection-pool sizing, and PDFs rendered inline on the request path

| Field | Value |
|---|---|
| Finding ID | P2-05 |
| Priority | P2 |
| Category | Reliability |
| Implementation difficulty | Medium |
| Business impact score | 5 / 10 |
| Implementation effort score | 3.5 / 10 |
| Confidence | Medium |

**Current state**

Comment and reason schemas accept text with no maximum length. The engine is created with pool_pre_ping=True and no explicit pool_size or max_overflow. Finalization renders the PDF with WeasyPrint synchronously inside the CEO's request, then stores the bytes and hash.

**Exact repository evidence**

```text
The evaluation schemas define comment and reason as unbounded strings; db/session.py calls create_engine with pool_pre_ping and no sizing arguments; documents.archive_final_pdf is invoked directly from ceo_finalize.
```

**File path & location**

```text
backend/app/schemas/evaluation.py · backend/app/db/session.py · backend/app/api/routers/evaluations.py ceo_finalize · backend/app/services/documents.py
```

**Gap / risk / missing capability**

Three separate scaling edges. Unbounded text lets an authenticated user store arbitrarily large content in a row that is read on every record view and written into every export and PDF. Default pool sizing is fine for a handful of users but is an unmeasured guess under a period-opening burst, where two hundred evaluators arrive simultaneously with auto-saving score drafts. Inline PDF rendering puts a CPU-heavy native library on the latency path of the product's most important action, so a rendering slowdown becomes a failed finalization — mitigated by graceful degradation and idempotent re-run, but still the wrong place for the work.

**Recommended fix**

Bound the text fields at the schema and column level with a friendly Persian message. Set pool_size, max_overflow and pool_recycle deliberately, sized against expected concurrent evaluators, and expose pool saturation as a metric under P1-12. Move PDF rendering off the request path: finalize the record and enqueue the render, showing the document as 'being prepared' until it lands — the existing idempotency and hash-on-store logic already make retry safe. Add a load test for the period-opening burst.

**Product & business impact**

Turns the three places where the system would first bend under real organisational load into deliberate, measured decisions.

**Dependencies**

- Queue or worker from P0-08
- Metrics from P1-12
- Column-length migration

---

## UX & usability (2)

Employee and approver experience, mobile reach, accessibility and localisation architecture.

### P2-04 · P2 · No PWA manifest, no offline capability, no push — the employee and manager experience is desktop-web only

| Field | Value |
|---|---|
| Finding ID | P2-04 |
| Priority | P2 |
| Category | UX |
| Implementation difficulty | Medium |
| Business impact score | 6 / 10 |
| Implementation effort score | 4 / 10 |
| Confidence | High |

**Current state**

The shell sets lang=fa and dir=rtl with a viewport meta tag and a theme-color, uses an inline SVG favicon, lazy-loads routes and wraps navigation with flex-wrap. There is no manifest link, no service worker, and no native application.

**Exact repository evidence**

```text
frontend/index.html contains no manifest reference and no service-worker registration; no manifest or worker file exists under frontend/public.
```

**File path & location**

```text
frontend/index.html · frontend/src/
```

**Gap / risk / missing capability**

Scoring twenty indicators with mandatory evidence text is a phone-hostile task today, and the people most likely to be mobile — unit supervisors on a production floor, executives between meetings — are the ones whose delay stalls the chain. Employees have no reason to install anything, so acknowledgment and scorecard viewing depend on remembering a URL. Without a service worker there is also no push channel, which is the natural companion to P1-03.

**Recommended fix**

Ship a proper PWA: manifest with Persian name and icons, installability, a service worker caching the shell and static assets, and an offline-tolerant scoring draft that queues writes and reconciles through the existing upsert endpoint (safe because scores are idempotent per record and indicator). Redesign the scoring screen mobile-first — one indicator per view, large touch targets, evidence input with the word counter the backend rule already implies. Add Web Push for approvals and acknowledgments once the notification channel abstraction exists.

**Product & business impact**

Directly shortens approval latency and makes the employee surface something people actually open, which is the precondition for any engagement claim.

**Dependencies**

- P1-03 channel abstraction for push
- Mobile scoring redesign

### P2-07 · P2 · No accessibility verification, no English locale scaffolding, and user-facing strings are inline literals

| Field | Value |
|---|---|
| Finding ID | P2-07 |
| Priority | P2 |
| Category | UX |
| Implementation difficulty | Low |
| Business impact score | 5 / 10 |
| Implementation effort score | 3 / 10 |
| Confidence | Medium |

**Current state**

Deliberate accessibility groundwork exists — a skip link to #main-content, aria-label on the main navigation, semantic layout — and the Persian typography and RTL handling are excellent. But there is no automated accessibility check in CI, and every user-facing string is an inline Persian literal in the component that renders it, including the recommendation strings that originate as Python constants.

**Exact repository evidence**

```text
Layout.tsx provides the skip target and aria-labelled nav; no axe or accessibility dependency appears in frontend/package.json; no i18n library or message catalogue exists; constants.py holds Persian recommendation text server-side.
```

**File path & location**

```text
frontend/src/components/Layout.tsx · frontend/package.json · backend/app/core/constants.py
```

**Gap / risk / missing capability**

The accessibility intent is real but unverified: keyboard traversal of the scoring form, focus management on modal open, contrast of status chips and screen-reader behaviour in RTL are all unmeasured, and a public-sector or larger private buyer will ask. On localisation, Persian-first is the right strategic choice — but strings living inline means adding English or Arabic later touches every component, and it also prevents customer-specific wording (a common enterprise request) without code edits.

**Recommended fix**

Add axe-core assertions to the existing vitest suite for the main screens and put a keyboard-only pass of the scoring and approval flows into the release checklist. Extract strings into a message catalogue with Persian as the default locale — mechanical, low-risk, and it immediately enables per-customer terminology overrides. Serve recommendation and status labels from the configuration store (P1-04) rather than from constants so both sides share one source.

**Product & business impact**

Protects the product's strongest UX asset and removes the future rework cost of localisation and customer-specific wording.

**Dependencies**

- P1-04 configuration store for server-side labels

---

## Testing & deployment (2)

Test depth against actual risk, and whether releases are deliberate and reversible.

### P0-07 · P0 · Migrations run automatically on every container start, and the backend process runs as root

| Field | Value |
|---|---|
| Finding ID | P0-07 |
| Priority | P0 |
| Category | Deployment |
| Implementation difficulty | Low |
| Business impact score | 7 / 10 |
| Implementation effort score | 2 / 10 |
| Confidence | High |

**Current state**

docker-entrypoint.sh executes 'alembic upgrade head' before starting uvicorn, so any container start — a restart, a scale-up, a crash loop — applies schema changes. The backend Dockerfile installs Python 3.11-slim plus WeasyPrint's native libraries and declares no USER, so uvicorn and the application run with uid 0.

**Exact repository evidence**

```text
The entrypoint script runs the Alembic upgrade unconditionally and then launches uvicorn with --proxy-headers and a wildcard --forwarded-allow-ips default; the Dockerfile contains no USER directive between its dependency installation and its CMD.
```

**File path & location**

```text
backend/docker-entrypoint.sh · backend/Dockerfile
```

**Gap / risk / missing capability**

Auto-migration means schema change is coupled to process start rather than to a deliberate release step: two replicas starting together race on the same migration, a rollback of application code does not roll back the schema it already applied, and — as P0-01 shows — a data-seeding migration executes in production without anyone choosing to run it. There is no migration-reversibility check in CI and no rollback or blue-green strategy documented. Running as root then removes the last containment layer: any code-execution defect, including one reached through WeasyPrint's native rendering path, executes as root inside the container.

**Recommended fix**

Separate migration from boot: run 'alembic upgrade head' as an explicit release job or a Compose one-shot service that must succeed before the API rolls, and have the API assert at startup that the DB revision matches the code's expected head, refusing to serve on mismatch rather than migrating. Add a non-root user to the Dockerfile (create an appuser, chown what it needs, USER appuser) and drop capabilities in Compose. Add a CI step that applies and then downgrades every migration against a scratch database to prove reversibility. Document a rollback procedure.

**Product & business impact**

These are the two changes that make production incidents survivable rather than dramatic. Both are small, mechanical, and expected by anyone reviewing the deployment.

**Dependencies**

- Compose and CI pipeline changes
- Coordinate with the P0-01 seed fix

### P1-13 · P1 · No real concurrency test and no end-to-end test — the enforcement chain is never verified as a whole

| Field | Value |
|---|---|
| Finding ID | P1-13 |
| Priority | P1 |
| Category | Testing |
| Implementation difficulty | Medium |
| Business impact score | 7 / 10 |
| Implementation effort score | 4 / 10 |
| Confidence | High |

**Current state**

152 backend tests run against PostgreSQL in CI with a session-scoped 'alembic upgrade head' and a savepoint-per-test rollback fixture; 29 frontend tests use vitest and Testing Library; ruff, oxlint and a strict tsc -b build run on every push and pull request to main. test_workflow_concurrency.py contains two tests, and its own docstring concedes that a genuine two-connection race is not exercised.

**Exact repository evidence**

```text
conftest.py implements the session-scoped migration and savepoint rollback; the CI workflow defines a backend job with a postgres:16 service running ruff and pytest and a frontend job running lint, test and build; test_workflow_concurrency.py holds two tests with the documented limitation.
```

**File path & location**

```text
backend/tests/conftest.py · backend/tests/test_workflow_concurrency.py · .github/workflows/ci.yml
```

**Gap / risk / missing capability**

The engineering discipline here is above average for a project this size, but the tests are strongest where the risk is lowest. The behaviours that would actually damage a customer — two approvals racing, a score write landing during submit, the partial unique index catching a real duplicate under contention — are exactly the behaviours the savepoint-per-test fixture cannot express, because everything runs on one connection inside one transaction. There is no end-to-end test, so nothing proves that the UI's permission booleans and the backend's transition table still agree after either side changes; that agreement is currently maintained by hand in two places (workflow.py and EvaluationDetailPage.tsx:100-135). There is also no coverage gate, so an untested path is indistinguishable from a tested one, and no load test, so behaviour under contention is unmeasured. This audit could not execute the suite at all — PostgreSQL is unavailable in the review environment — so the CI definition is verified but no result is observed.

**Recommended fix**

Add a small number of high-value tests rather than chasing coverage. Real race tests on two connections: simultaneous approvals of the same record (exactly one succeeds), a score write racing a submit (rejected), and two concurrent create calls for the same employee (one 409 carrying the existing id). An end-to-end suite covering the full chain per role including return-and-resubmit, plus negative tests asserting that a forged direct API call at the wrong stage or by the wrong user is refused — the machine-checkable statement that the UI is not the enforcement layer. A test that the finalized PDF is byte-stable and its SHA-256 matches on re-render. Then add a coverage floor to CI and a nightly load test on the scoring and report endpoints.

**Product & business impact**

Converts the workflow guarantees from 'read as correct' to 'proven under contention', which is what makes it safe to keep changing the state machine as the product grows.

**Dependencies**

- Test fixture that supports multiple real connections
- E2E runner and seeded fixture environment

---

## Differentiation & AI (11)

Forward-looking findings — these are opportunities, not defects. Detail on strategy lives in section 3 (How DbsPulse Can Win).

### P3-01 · P3 · Renewal-risk early warning: predict the contract decision months before the evaluation, with explanation

| Field | Value |
|---|---|
| Finding ID | P3-01 |
| Priority | P3 |
| Category | Differentiation |
| Implementation difficulty | Medium |
| Business impact score | 8 / 10 |
| Implementation effort score | 4 / 10 |
| Confidence | High |

**Current state**

Risk is discovered at the end. The final weighted percentage is compared to four thresholds at CEO finalization, and the contract-expiry sweep warns HR that a date is approaching — but nothing indicates beforehand that a specific employee is heading toward non-renewal or conditional renewal.

**Exact repository evidence**

```text
constants.py FINAL_RESULT_THRESHOLDS applied by recommendation_for at finalization; scheduled.py warns on contract_end_date proximity only.
```

**File path & location**

```text
backend/app/core/constants.py · backend/app/services/evaluation.py recommendation_for · backend/app/services/scheduled.py
```

**Gap / risk / missing capability**

By the time the recommendation is 'عدم تمدید', the opportunity to change the outcome has passed — no coaching happened, no improvement plan ran, and the organisation loses a person it might have kept. All the raw material for an earlier signal already exists: prior finalized percentages and their trajectory, indicator-level weak spots, improvement-plan history and outcomes, time-in-stage patterns, and contract dates.

**Recommended fix**

Build a transparent, rules-first risk score computed from data the product already holds: previous final percentage and its direction, count of indicators below a threshold, open or failed improvement plans, and proximity of contract_end_date. Present it as a small set of named contributing factors, never as an opaque number, on an HR and manager 'attention needed' list with a suggested action. Keep it strictly advisory and never let it write a recommendation. Only after this is trusted, and only if measured to beat the rules, consider a model — and even then keep the rule-based explanation as the interface.

**Product & business impact**

Shifts the product from recording decisions to preventing avoidable losses, which is the strongest commercial story available on top of the existing data — and it needs no new data collection.

**Dependencies**

- P1-01 goals and P1-10 plan progress improve accuracy substantially
- Requires several completed cycles of history

### P3-02 · P3 · No-code process designer: let HR compose stages, weights, thresholds and rules without a developer

| Field | Value |
|---|---|
| Finding ID | P3-02 |
| Priority | P3 |
| Category | Differentiation |
| Implementation difficulty | High |
| Business impact score | 8 / 10 |
| Implementation effort score | 8.5 / 10 |
| Confidence | High |

**Current state**

The workflow is a hardcoded seven-transition table with a four-stage chain plus the manager path; scoring parameters are constants; the improvement-plan trigger is tied to the conditional-renewal string.

**Exact repository evidence**

```text
workflow.py TRANSITIONS is a frozen dataclass table; constants.py holds all parameters; CONDITIONAL_RENEWAL_RECOMMENDATION derives from FINAL_RESULT_THRESHOLDS[1][1].
```

**File path & location**

```text
backend/app/services/workflow.py · backend/app/core/constants.py
```

**Gap / risk / missing capability**

Every enterprise buyer's process differs — a fifth approval, a mandatory self-assessment for managers only, unit-specific weights, different thresholds for probationary staff. Today each variation is a fork of the code, which caps how many customers the product can serve without becoming unmaintainable.

**Recommended fix**

Promote the declarative transition table to data: a versioned process definition (stages, allowed roles, assignee source, required inputs, service levels, escalation targets) validated on save and executed by the existing engine, which is already declarative enough to make this an evolution rather than a rewrite. Add a visual editor with simulation against historical records, require a second approval to activate, stamp every record with its process version, and never migrate in-flight records to a new version.

**Product & business impact**

The clearest path from one-company system to multi-customer product, and a strong differentiator against rigid mid-market tools.

**Dependencies**

- P1-04 scoring configuration
- P1-05 framework versioning
- Simulation tooling

### P3-03 · P3 · Iranian compliance and localisation pack as a defensible moat

| Field | Value |
|---|---|
| Finding ID | P3-03 |
| Priority | P3 |
| Category | Differentiation |
| Implementation difficulty | Medium |
| Business impact score | 8 / 10 |
| Implementation effort score | 5 / 10 |
| Confidence | High |

**Current state**

The product is already deeply Persian-first: native Jalali conversion without external dependencies, full RTL, self-hosted Vazirmatn in both the app and the PDF, Persian digits in exports, and Persian recommendation and status vocabulary. What is absent is the regulatory and calendar layer around it.

**Exact repository evidence**

```text
frontend/src/utils/jalali.ts implements Birashk conversion natively; excel.py translates digits to Persian; the PDF template embeds Vazirmatn via @font-face; constants.py carries Persian recommendation strings.
```

**File path & location**

```text
frontend/src/utils/jalali.ts · backend/app/services/excel.py · backend/app/templates/evaluation_summary.html
```

**Gap / risk / missing capability**

Global suites localise text and stop there; they do not model Iranian labour-law contract mechanics, Jalali fiscal periods, official holiday calendars for working-day service levels, or the documentation an Iranian employer needs at renewal. That is exactly where a local product can be unbeatable rather than merely cheaper.

**Recommended fix**

Build the layer only a local vendor would: an Iranian holiday calendar driving working-day deadline calculations; Jalali fiscal-year periods as first-class cycle containers; contract-type awareness (probationary, fixed-term, renewal count) affecting which framework applies; renewal documentation templates aligned to labour-law practice; and a documented, hash-verified evaluation dossier suitable for internal dispute resolution — extending the QR verification that already exists. Keep every rule as configuration, not code.

**Product & business impact**

Converts a language advantage into a compliance advantage, which is far harder for an international competitor to copy than translation.

**Dependencies**

- P1-04 configuration store
- P1-07 periods
- Legal input on labour-law specifics

### P3-04 · P3 · Fast, low-friction workflows as the product promise: minutes per evaluation, measured and published

| Field | Value |
|---|---|
| Finding ID | P3-04 |
| Priority | P3 |
| Category | Differentiation |
| Implementation difficulty | Low |
| Business impact score | 7 / 10 |
| Implementation effort score | 2.5 / 10 |
| Confidence | High |

**Current state**

Real friction reducers already exist — auto-saving score drafts, role-scoped queues, conflict responses that deep-link to the blocking record, an evidence rule that keeps justification to at most forty words, and a manager path that avoids a meaningless empty supervisor stage.

**Exact repository evidence**

```text
AGENTS.md documents auto-save; evaluations.py:117-235 returns a 409 carrying evaluation_id; constants.py bounds evidence at 40 words; workflow.is_manager_path skips the supervisor stage cleanly.
```

**File path & location**

```text
backend/app/api/routers/evaluations.py:117-235 · backend/app/core/constants.py · backend/app/services/workflow.py
```

**Gap / risk / missing capability**

These wins are invisible because nothing measures them. There is no time-in-stage metric, no cycle-time report, no completion-rate view — so the product cannot prove its main advantage over a heavyweight suite, and cannot tell where the remaining friction is.

**Recommended fix**

Instrument the funnel using the stage_entered_at column from P1-02: median minutes to complete a scoring session, median hours per approval stage, end-to-end cycle time, first-pass rate versus returns, and evidence-quality rate. Show it to HR as an operational dashboard and to the buyer as the headline claim. Then attack the measured bottleneck — likely bulk actions for HR (P2-03), mobile approval for executives (P2-04), and keyboard-first scoring for supervisors.

**Product & business impact**

Makes 'faster than the alternatives' a demonstrable number instead of a marketing adjective, and gives the roadmap an objective target.

**Dependencies**

- P1-02 stage_entered_at
- P1-12 metrics

### P3-05 · P3 · Smarter improvement plans: a template library generated from the organisation's own weak-indicator patterns

| Field | Value |
|---|---|
| Finding ID | P3-05 |
| Priority | P3 |
| Category | Differentiation |
| Implementation difficulty | Medium |
| Business impact score | 7 / 10 |
| Implementation effort score | 4 / 10 |
| Confidence | High |

**Current state**

Plans are created by HR from scratch, with free-text goals, a review date and a status; a sweep notifies when review is due. There is no template, no link from the weak indicators that caused the plan, and no measurement of whether plans work.

**Exact repository evidence**

```text
improvement_plans.py exposes plan and goal CRUD with no template concept; scheduled.py runs the review-due sweep; nothing correlates a plan with the next evaluation's outcome.
```

**File path & location**

```text
backend/app/api/routers/improvement_plans.py · backend/app/services/scheduled.py
```

**Gap / risk / missing capability**

The plan is the product's only intervention, and it is the least supported part of it. HR reinvents remedial goals each time, quality depends on who wrote it, and nobody knows which plans lead to improvement — so the organisation cannot learn from its own history.

**Recommended fix**

Close the loop with data already present. Pre-fill a plan from the indicators scored lowest in the triggering evaluation. Build a template library of goals per indicator, seeded by HR and enriched by which templates preceded score improvement. Report plan effectiveness — score change at the next evaluation, by indicator and by manager — and surface the most effective templates first. Add manager and employee participation from P1-10 so progress is real data rather than recollection.

**Product & business impact**

Turns a compliance artifact into the mechanism that measurably improves performance, which is the outcome a buyer is actually purchasing.

**Dependencies**

- P1-10 plan participation
- P1-01 goals for progress semantics
- Multiple cycles of history

### P3-06 · P3 · Evidence-quality assistant: help evaluators write specific, behavioural justifications

| Field | Value |
|---|---|
| Finding ID | P3-06 |
| Priority | P3 |
| Category | AI |
| Implementation difficulty | Medium |
| Business impact score | 7 / 10 |
| Implementation effort score | 4 / 10 |
| Confidence | Medium |

**Current state**

Evidence is validated only for length — scores of 1 and 5 require between three and forty words, checked server-side by validate_evidence. Nothing assesses whether the text is specific, behavioural or non-discriminatory.

**Exact repository evidence**

```text
constants.py sets EVIDENCE_REQUIRED_SCORES, MIN_WORDS and MAX_WORDS; evaluation.py:34-57 validates word counts only.
```

**File path & location**

```text
backend/app/core/constants.py · backend/app/services/evaluation.py:34-57
```

**Gap / risk / missing capability**

Word count is a proxy for effort, not quality. 'ضعیف بود' padded to three words passes; so does text containing protected-characteristic references or pure personality judgement. Because this text is the written justification behind a contract decision, its quality is the difference between a defensible file and a liability.

**Recommended fix**

Assist, never decide. As the evaluator types, offer private, non-blocking guidance: is the statement specific, does it describe observable behaviour rather than personality, does it cover the review period, does it contain language that should be reconsidered. Keep the hard rule as the existing deterministic word check so submission never depends on a model. Prefer a self-hosted or in-region model given data sensitivity; if an external service is used, disclose it, send the minimum text with no identifiers, retain nothing, and let HR disable the feature per organisation. Log that assistance was offered — never store the suggestion as if it were the evaluator's words.

**Product & business impact**

Improves the quality of the product's most legally significant text at the moment of writing, and reduces returns caused by inadequate justification.

**Dependencies**

- Model hosting decision
- Privacy review and disclosure
- Per-organisation opt-out

### P3-07 · P3 · Rater-bias and pattern detection for calibration support

| Field | Value |
|---|---|
| Finding ID | P3-07 |
| Priority | P3 |
| Category | AI |
| Implementation difficulty | Medium |
| Business impact score | 7 / 10 |
| Implementation effort score | 3.5 / 10 |
| Confidence | High |

**Current state**

No leniency, severity, halo, central-tendency or recency analysis exists. Distributions can be displayed; nothing interprets them or flags a rater whose pattern differs systematically from peers.

**Exact repository evidence**

```text
reports.py returns distributions with no rater-level statistics; no calibration or adjustment path exists in workflow.py.
```

**File path & location**

```text
backend/app/api/routers/reports.py · backend/app/services/workflow.py
```

**Gap / risk / missing capability**

Single-rater scoring plus fixed numeric thresholds means a lenient manager's team is systematically likelier to be renewed than a strict manager's equally performing team. The system currently cannot see this, let alone correct it.

**Recommended fix**

Start with statistics, not machine learning: per-rater mean and variance versus organisational and unit baselines, score-clustering detection, an all-fives or all-threes flag, and identical-evidence-text detection across employees. Surface these only to HR inside the calibration workflow (P1-06) as prompts for a documented human conversation — never as an automatic adjustment and never shown to the employee. Publish the method so a flagged manager can see exactly why. Guard against the obvious failure mode: a genuinely high-performing unit must not be labelled as leniently rated, so always require human confirmation before any adjustment.

**Product & business impact**

Makes scores comparable across managers, which is the precondition for a threshold-based renewal recommendation to be fair.

**Dependencies**

- P1-06 calibration workflow
- Sufficient volume for meaningful statistics

### P3-08 · P3 · Narrative synthesis of qualitative content, with the human as author of record

| Field | Value |
|---|---|
| Finding ID | P3-08 |
| Priority | P3 |
| Category | AI |
| Implementation difficulty | Medium |
| Business impact score | 6 / 10 |
| Implementation effort score | 4 / 10 |
| Confidence | Medium |

**Current state**

Evidence text, evaluator comments and threaded replies accumulate per record and are read individually. The PDF reproduces them; nothing summarises across indicators, cycles or a unit.

**Exact repository evidence**

```text
evaluation_comments with threaded replies (migration c4f7e2a9b103); snapshot.py stores the full text into final_snapshot; no summarisation exists anywhere.
```

**File path & location**

```text
backend/app/models/evaluation.py · backend/app/services/snapshot.py
```

**Gap / risk / missing capability**

An executive reviewing thirty renewal cases reads either a number or dozens of comment fragments; HR preparing a plan re-reads the whole history. The qualitative signal the system carefully collects is effectively unread at the moment decisions are made.

**Recommended fix**

Offer draft syntheses for specific, bounded tasks: a strengths-and-development summary from one evaluation's evidence, a trajectory narrative across an employee's finalized cycles, and a themes view across a unit. Every output must be labelled as a draft, cite the source comments it derives from, be editable, and require a human to adopt it before it is stored — the stored text is then attributed to that person, not to the model. Never place a generated summary in the archived legal document unless a human adopted and signed it, since the snapshot and hash exist precisely to guarantee authorship.

**Product & business impact**

Makes accumulated qualitative data usable at decision time without diluting accountability for what the record says.

**Dependencies**

- Model hosting and privacy review
- Adoption/attribution UX
- Must not alter final_snapshot semantics

### MS-01 · Moonshot · Continuous performance signal layer — evaluate from evidence, not memory

| Field | Value |
|---|---|
| Finding ID | MS-01 |
| Priority | Moonshot |
| Category | Moonshot |
| Implementation difficulty | Very high |
| Business impact score | 9 / 10 |
| Implementation effort score | 9.5 / 10 |
| Confidence | Medium |

**Current state**

Performance data enters the system exclusively as a manager's twenty judgements at a point in time, with no connection to any operational system.

**Exact repository evidence**

```text
evaluation_scores is the only performance data source; no integration surface exists (see P1-14).
```

**File path & location**

```text
backend/app/models/evaluation.py · backend/app/api/
```

**Gap / risk / missing capability**

Annual recall is the weakest possible input to a decision about someone's employment, and it is the input every mid-market tool shares. Organisations already generate objective signals — task completion, quality incidents, attendance, training, safety, customer outcomes — that never reach the evaluation.

**Recommended fix**

Build a signal ingestion layer: typed, consented, per-organisation-configured feeds from ERP, task and production systems, aggregated into period summaries that appear beside the manager's score as evidence — visible to the employee, always attributable to a source, never automatically converted into a rating. Publish clearly which signals a customer has enabled. This is a moonshot because it requires the integration platform of P1-14, a strong governance model, and explicit rejection of surveillance-style signals such as keystroke or screen monitoring.

**Product & business impact**

Would reposition DbsPulse from a review tool to the organisation's performance evidence system — the highest-ceiling opportunity in this audit.

**Dependencies**

- P1-14 integrations
- P1-01 goals
- P1-04 configuration
- Employee-consent and transparency framework

### MS-02 · Moonshot · Anonymised Iranian HR benchmark network

| Field | Value |
|---|---|
| Finding ID | MS-02 |
| Priority | Moonshot |
| Category | Moonshot |
| Implementation difficulty | Very high |
| Business impact score | 8 / 10 |
| Implementation effort score | 10 / 10 |
| Confidence | Medium |

**Current state**

Single-organization architecture with no tenant discriminator; all analytics are internal to one deployment.

**Exact repository evidence**

```text
No organization_id on any of the 12 models; reports.py aggregates within the single deployment only.
```

**File path & location**

```text
backend/app/models/ · backend/app/api/routers/reports.py
```

**Gap / risk / missing capability**

Iranian HR leaders have no credible local benchmarks for score distributions, renewal rates, turnover or cycle times, and international benchmarks are irrelevant to local labour practice. Nobody is positioned to supply this.

**Recommended fix**

Once multi-tenancy exists, offer opt-in benchmarking with genuine privacy engineering: aggregate only, enforced minimum cohort sizes well above the reporting threshold, k-anonymity across every published dimension, differential-privacy noise on small groups, no cross-tenant record access ever, and a published methodology plus an independent review. Contractual guarantees that raw data never leaves a tenant. Charge for the insight, not the data.

**Product & business impact**

A network effect no international competitor can replicate locally — each customer makes the benchmark better, which makes the product harder to leave.

**Dependencies**

- Multi-tenancy (a rearchitecture, per the tenancy verdict)
- P1-08 suppression as the foundation
- Legal and privacy framework
- Meaningful customer count

### MS-03 · Moonshot · Verifiable evaluation credentials — extend hash-verified PDFs into signed, portable attestations

| Field | Value |
|---|---|
| Finding ID | MS-03 |
| Priority | Moonshot |
| Category | Moonshot |
| Implementation difficulty | Very high |
| Business impact score | 7 / 10 |
| Implementation effort score | 8.5 / 10 |
| Confidence | Medium |

**Current state**

Finalization already produces an immutable snapshot, a byte-stable PDF, a stored SHA-256 and a public QR verification page keyed by an unguessable token — a genuinely strong integrity chain, verified as implemented.

**Exact repository evidence**

```text
documents.archive_final_pdf stores bytes and hash idempotently; verify.py serves public token lookup for finalized records only, rate-limited at 30 per minute; the PDF template embeds the verification QR at lines 107-113.
```

**File path & location**

```text
backend/app/services/documents.py · backend/app/api/routers/verify.py · backend/app/templates/evaluation_summary.html:107-113
```

**Gap / risk / missing capability**

Verification today proves the document matches what this deployment stored, and only while this deployment is online. It cannot be verified offline, cannot be presented by the employee as portable proof, and does not carry a cryptographic identity for the signing authority — and the hash itself is not printed in the document, so an offline holder has nothing to compare.

**Recommended fix**

Issue each finalized evaluation as a cryptographically signed attestation: organisation key pair with published public key, detached signature over the canonical snapshot, the hash printed in the PDF alongside the QR, and offline verification through a standalone verifier. Let the employee hold and share their own attestation with selective disclosure — proving 'renewed with standard terms' without revealing indicator scores. Consider a timestamping authority or an append-only transparency log so the issuance date is provable independently of the vendor. Keep it entirely optional and employee-controlled.

**Product & business impact**

Would make DbsPulse the system whose output is trusted outside the company that produced it — a differentiator with no equivalent in this market segment, built on infrastructure that already exists.

**Dependencies**

- Key management and rotation
- P1-11 document storage migration
- Legal recognition of the attestation
- Standalone verifier

---

Audit of `sanyzrn/DbsPulse_V2` — branch `main`, commit `ef0166b091d2d167d808702e084c079e5143e307`. Findings derive from static inspection of source files in that commit. No application code was modified. Items that cannot be confirmed from the repository are labelled *Not verifiable from the repository*.
