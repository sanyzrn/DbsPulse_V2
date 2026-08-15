> **DbsPulse V2 — Product, Architecture, Workflow, Security & UX Audit**  
> Repository: <https://github.com/sanyzrn/DbsPulse_V2> · Branch `main` · Commit `ef0166b091d2d167d808702e084c079e5143e307`  
> Site section: 4. Execution Roadmap

# Execution roadmap — sequenced by dependency, not by appetite

Six waves from P0 blockers to moonshots. Priorities: **P0** critical production, security, workflow and trust blockers · **P1** required to compete credibly · **P2** high-value improvements · **P3** strong differentiators · **Moonshots**. Every item links back to its evidence in section 2.

## 4.1 · Impact versus effort

All 41 findings plotted. On the site, hovering any point shows its title and clicking opens the finding. The upper-left quadrant is the work to do first — high business impact, low implementation cost.

**Quadrant key**

- **Quick wins** — high impact · low effort
- **Major bets** — high impact · high effort
- **Fill-ins** — low impact · low effort
- **Question marks** — low impact · high effort

| ID | Priority | Title | Impact | Effort | Impact − Effort | Quadrant |
|---|---|---|---|---|---|---|
| P0-01 | P0 | Demo accounts with a published shared password are seeded by a migration that runs on every production boot | 10 | 1.5 | 8.5 | Quick win |
| P0-02 | P0 | No cancel, void or reassign transition — a single departed approver permanently blocks an employee from ever being evaluated again | 9 | 2.5 | 6.5 | Quick win |
| P0-05 | P0 | Score and comment writes bypass the row lock used by transitions, leaving a lost-update and write-after-submit window | 8 | 2 | 6.0 | Quick win |
| P0-04 | P0 | Login rate limiting can be bypassed with a spoofed header, and there is no per-account lockout | 9 | 3.5 | 5.5 | Quick win |
| P1-02 | P1 | Deadlines are advisory only, and the SLA sweep measures total case age instead of time in the current stage | 8 | 2.5 | 5.5 | Quick win |
| P0-07 | P0 | Migrations run automatically on every container start, and the backend process runs as root | 7 | 2 | 5.0 | Quick win |
| P1-08 | P1 | Analytics and exports have no minimum-cohort suppression, so filtering to a small unit discloses individuals | 7 | 2 | 5.0 | Quick win |
| P0-06 | P0 | The employee has no voice: no self-assessment, no visibility before the decision, no objection path, and no access to the signed document about them | 10 | 5.5 | 4.5 | Major bet |
| P0-08 | P0 | Reminders and escalation are effectively off in production: the scheduler is in-process, defaults to disabled, and is unsafe with more than one replica | 8 | 3.5 | 4.5 | Quick win |
| P1-03 | P1 | Notifications are in-app only, so the entire workflow depends on approvers voluntarily logging in | 9 | 4.5 | 4.5 | Quick win |
| P1-07 | P1 | Evaluation periods are fully built server-side but hidden behind a disabled feature flag while the README presents them as a feature | 7 | 2.5 | 4.5 | Quick win |
| P3-04 | P3 | Fast, low-friction workflows as the product promise: minutes per evaluation, measured and published | 7 | 2.5 | 4.5 | Quick win |
| P0-03 | P0 | Any HR user can approve or return any evaluation, and the HR role is also the super-admin — no separation of duties | 9 | 5 | 4.0 | Major bet |
| P1-09 | P1 | The audit log is append-only by convention only, and two mutation paths are not logged at all | 8 | 4 | 4.0 | Quick win |
| P3-01 | P3 | Renewal-risk early warning: predict the contract decision months before the evaluation, with explanation | 8 | 4 | 4.0 | Quick win |
| P2-03 | P2 | No bulk operations — an annual cycle for a whole company is created one evaluation at a time | 7 | 3.5 | 3.5 | Quick win |
| P3-07 | P3 | Rater-bias and pattern detection for calibration support | 7 | 3.5 | 3.5 | Quick win |
| P1-10 | P1 | Improvement plans are HR-only: the plan owner is notified but has no API to read or update the plan they own | 7 | 4 | 3.0 | Quick win |
| P1-13 | P1 | No real concurrency test and no end-to-end test — the enforcement chain is never verified as a whole | 7 | 4 | 3.0 | Quick win |
| P2-01 | P2 | Analytics exist only for HR — managers and executives have no analytical surface of their own | 7 | 4 | 3.0 | Quick win |
| P2-02 | P2 | Excel exports write user-supplied text without neutralising formula-triggering prefixes | 4 | 1 | 3.0 | Fill-in |
| P3-03 | P3 | Iranian compliance and localisation pack as a defensible moat | 8 | 5 | 3.0 | Major bet |
| P3-05 | P3 | Smarter improvement plans: a template library generated from the organisation's own weak-indicator patterns | 7 | 4 | 3.0 | Quick win |
| P3-06 | P3 | Evidence-quality assistant: help evaluators write specific, behavioural justifications | 7 | 4 | 3.0 | Quick win |
| P1-05 | P1 | Indicators are mutable and unversioned, so editing the framework rewrites the meaning of past evaluations and breaks in-flight drafts | 7 | 4.5 | 2.5 | Quick win |
| P1-04 | P1 | Weights, thresholds, evidence rules and stage composition are Python constants — every customer needs a developer | 9 | 7 | 2.0 | Major bet |
| P1-11 | P1 | No retention, deletion or legal-hold capability, and archived PDFs accumulate as bytes inside PostgreSQL forever | 7 | 5 | 2.0 | Major bet |
| P1-12 | P1 | No metrics, tracing or error tracking — production failures are visible only as container logs | 6 | 4 | 2.0 | Quick win |
| P2-04 | P2 | No PWA manifest, no offline capability, no push — the employee and manager experience is desktop-web only | 6 | 4 | 2.0 | Quick win |
| P2-06 | P2 | No MFA, no session visibility, no password expiry, and no HSTS in the shipped nginx template | 6 | 4 | 2.0 | Quick win |
| P2-07 | P2 | No accessibility verification, no English locale scaffolding, and user-facing strings are inline literals | 5 | 3 | 2.0 | Quick win |
| P3-08 | P3 | Narrative synthesis of qualitative content, with the human as author of record | 6 | 4 | 2.0 | Quick win |
| P2-05 | P2 | Unbounded free-text fields, no explicit connection-pool sizing, and PDFs rendered inline on the request path | 5 | 3.5 | 1.5 | Quick win |
| P2-08 | P2 | Reporting has no saved views, scheduled delivery, or cross-period comparison | 5 | 3.5 | 1.5 | Quick win |
| P1-01 | P1 | No goal, OKR or KPI object exists — evaluation is disconnected from what people were actually asked to achieve | 9 | 8 | 1.0 | Major bet |
| P1-06 | P1 | No self-assessment, no 360 input, and no calibration — the result is one manager's opinion with no correction mechanism | 8 | 7 | 1.0 | Major bet |
| P1-14 | P1 | No SSO, no HRIS or payroll integration, no webhooks, no versioned public API | 8 | 7.5 | 0.5 | Major bet |
| P3-02 | P3 | No-code process designer: let HR compose stages, weights, thresholds and rules without a developer | 8 | 8.5 | -0.5 | Major bet |
| MS-01 | Moonshot | Continuous performance signal layer — evaluate from evidence, not memory | 9 | 9.5 | -0.5 | Major bet |
| MS-03 | Moonshot | Verifiable evaluation credentials — extend hash-verified PDFs into signed, portable attestations | 7 | 8.5 | -1.5 | Major bet |
| MS-02 | Moonshot | Anonymised Iranian HR benchmark network | 8 | 10 | -2.0 | Major bet |

## 4.2 · Recommended implementation order — six waves

Windows are indicative for a small team and assume the waves run in order; items inside a wave are listed in the order they should be started.

### Wave 1 — Stop the bleeding

**Window:** Weeks 1–3 · **Items:** 5

Nothing else matters until these are closed. All are small, mechanical and independent.

| Order | ID | Priority | Finding | Category | Difficulty | Impact |
|---|---|---|---|---|---|---|
| 1 | P0-01 | P0 | Demo accounts with a published shared password are seeded by a migration that runs on every production boot | Security | Low | 10/10 |
| 2 | P0-07 | P0 | Migrations run automatically on every container start, and the backend process runs as root | Deployment | Low | 7/10 |
| 3 | P0-02 | P0 | No cancel, void or reassign transition — a single departed approver permanently blocks an employee from ever being evaluated again | Workflow integrity | Low | 9/10 |
| 4 | P0-05 | P0 | Score and comment writes bypass the row lock used by transitions, leaving a lost-update and write-after-submit window | Workflow integrity | Low | 8/10 |
| 5 | P2-02 | P2 | Excel exports write user-supplied text without neutralising formula-triggering prefixes | Security | Low | 4/10 |

**Outcome.** No published credentials in any environment, deliberate rather than accidental migrations, a non-root container, no unrecoverable evaluations, and score writes serialised on the same lock as transitions.

### Wave 2 — Make the process trustworthy

**Window:** Weeks 3–8 · **Items:** 6

Close the authorization, brute-force, privacy and reliability gaps that any security review will find, and give the employee a voice.

| Order | ID | Priority | Finding | Category | Difficulty | Impact |
|---|---|---|---|---|---|---|
| 1 | P0-04 | P0 | Login rate limiting can be bypassed with a spoofed header, and there is no per-account lockout | Security | Medium | 9/10 |
| 2 | P0-03 | P0 | Any HR user can approve or return any evaluation, and the HR role is also the super-admin — no separation of duties | Authorization | Medium | 9/10 |
| 3 | P1-08 | P1 | Analytics and exports have no minimum-cohort suppression, so filtering to a small unit discloses individuals | Privacy | Low | 7/10 |
| 4 | P0-08 | P0 | Reminders and escalation are effectively off in production: the scheduler is in-process, defaults to disabled, and is unsafe with more than one replica | Enterprise readiness | Medium | 8/10 |
| 5 | P1-02 | P1 | Deadlines are advisory only, and the SLA sweep measures total case age instead of time in the current stage | Workflow integrity | Low | 8/10 |
| 6 | P0-06 | P0 | The employee has no voice: no self-assessment, no visibility before the decision, no objection path, and no access to the signed document about them | Trust and fairness | Medium | 10/10 |

**Outcome.** Rate limiting that cannot be bypassed, HR case ownership and separation of duties, analytics that cannot re-identify individuals, reminders that reliably run and measure time in stage, and an employee who can self-assess, object and hold their own document.

### Wave 3 — Become a product

**Window:** Months 2–5 · **Items:** 6

The configurability, notification and release work that makes a second customer possible.

| Order | ID | Priority | Finding | Category | Difficulty | Impact |
|---|---|---|---|---|---|---|
| 1 | P1-04 | P1 | Weights, thresholds, evidence rules and stage composition are Python constants — every customer needs a developer | Product capability | High | 9/10 |
| 2 | P1-05 | P1 | Indicators are mutable and unversioned, so editing the framework rewrites the meaning of past evaluations and breaks in-flight drafts | Product capability | Medium | 7/10 |
| 3 | P1-03 | P1 | Notifications are in-app only, so the entire workflow depends on approvers voluntarily logging in | Product capability | Medium | 9/10 |
| 4 | P1-07 | P1 | Evaluation periods are fully built server-side but hidden behind a disabled feature flag while the README presents them as a feature | Release management | Low | 7/10 |
| 5 | P1-09 | P1 | The audit log is append-only by convention only, and two mutation paths are not logged at all | Auditability | Medium | 8/10 |
| 6 | P1-10 | P1 | Improvement plans are HR-only: the plan owner is notified but has no API to read or update the plan they own | Authorization | Medium | 7/10 |

**Outcome.** Versioned scoring configuration and framework versions that keep history honest, outbound notifications, periods enabled, a tamper-evident audit log, and improvement plans that managers and employees actually operate.

### Wave 4 — Compete credibly

**Window:** Months 4–9 · **Items:** 7

The capability gaps that decide competitive evaluations, plus the operational maturity to support them.

| Order | ID | Priority | Finding | Category | Difficulty | Impact |
|---|---|---|---|---|---|---|
| 1 | P1-01 | P1 | No goal, OKR or KPI object exists — evaluation is disconnected from what people were actually asked to achieve | Product capability | High | 9/10 |
| 2 | P1-06 | P1 | No self-assessment, no 360 input, and no calibration — the result is one manager's opinion with no correction mechanism | Product capability | High | 8/10 |
| 3 | P2-01 | P2 | Analytics exist only for HR — managers and executives have no analytical surface of their own | Product capability | Medium | 7/10 |
| 4 | P2-03 | P2 | No bulk operations — an annual cycle for a whole company is created one evaluation at a time | Product capability | Medium | 7/10 |
| 5 | P1-12 | P1 | No metrics, tracing or error tracking — production failures are visible only as container logs | Observability | Medium | 6/10 |
| 6 | P1-13 | P1 | No real concurrency test and no end-to-end test — the enforcement chain is never verified as a whole | Testing | Medium | 7/10 |
| 7 | P1-11 | P1 | No retention, deletion or legal-hold capability, and archived PDFs accumulate as bytes inside PostgreSQL forever | Enterprise readiness | Medium | 7/10 |

**Outcome.** Goals connected to evaluation, calibration that makes scores comparable, analytics for managers and executives, bulk cycle operations, real observability, race and end-to-end tests, and a defensible retention and document-storage story.

### Wave 5 — Win the market

**Window:** Months 6–14 · **Items:** 8

Differentiation that is only credible once the foundation exists.

| Order | ID | Priority | Finding | Category | Difficulty | Impact |
|---|---|---|---|---|---|---|
| 1 | P3-01 | P3 | Renewal-risk early warning: predict the contract decision months before the evaluation, with explanation | Differentiation | Medium | 8/10 |
| 2 | P3-04 | P3 | Fast, low-friction workflows as the product promise: minutes per evaluation, measured and published | Differentiation | Low | 7/10 |
| 3 | P3-03 | P3 | Iranian compliance and localisation pack as a defensible moat | Differentiation | Medium | 8/10 |
| 4 | P2-04 | P2 | No PWA manifest, no offline capability, no push — the employee and manager experience is desktop-web only | UX | Medium | 6/10 |
| 5 | P3-05 | P3 | Smarter improvement plans: a template library generated from the organisation's own weak-indicator patterns | Differentiation | Medium | 7/10 |
| 6 | P3-07 | P3 | Rater-bias and pattern detection for calibration support | AI | Medium | 7/10 |
| 7 | P3-06 | P3 | Evidence-quality assistant: help evaluators write specific, behavioural justifications | AI | Medium | 7/10 |
| 8 | P1-14 | P1 | No SSO, no HRIS or payroll integration, no webhooks, no versioned public API | Enterprise readiness | High | 8/10 |

**Outcome.** Early renewal-risk detection with explanation, published cycle-time proof, an Iranian compliance and calendar pack, a mobile-first employee and approver experience, improvement plans that measurably work, calibration support, evidence-quality assistance, and integrations that make the product embeddable.

### Wave 6 — Reach further

**Window:** Year 2+ · **Items:** 9

Only after the platform is stable, configurable, integrated and trusted.

| Order | ID | Priority | Finding | Category | Difficulty | Impact |
|---|---|---|---|---|---|---|
| 1 | P3-02 | P3 | No-code process designer: let HR compose stages, weights, thresholds and rules without a developer | Differentiation | High | 8/10 |
| 2 | P2-08 | P2 | Reporting has no saved views, scheduled delivery, or cross-period comparison | Product capability | Medium | 5/10 |
| 3 | P2-05 | P2 | Unbounded free-text fields, no explicit connection-pool sizing, and PDFs rendered inline on the request path | Reliability | Medium | 5/10 |
| 4 | P2-06 | P2 | No MFA, no session visibility, no password expiry, and no HSTS in the shipped nginx template | Security | Medium | 6/10 |
| 5 | P2-07 | P2 | No accessibility verification, no English locale scaffolding, and user-facing strings are inline literals | UX | Low | 5/10 |
| 6 | P3-08 | P3 | Narrative synthesis of qualitative content, with the human as author of record | AI | Medium | 6/10 |
| 7 | MS-01 | Moonshot | Continuous performance signal layer — evaluate from evidence, not memory | Moonshot | Very high | 9/10 |
| 8 | MS-03 | Moonshot | Verifiable evaluation credentials — extend hash-verified PDFs into signed, portable attestations | Moonshot | Very high | 7/10 |
| 9 | MS-02 | Moonshot | Anonymised Iranian HR benchmark network | Moonshot | Very high | 8/10 |

**Outcome.** A no-code process designer, mature reporting and reliability, hardened authentication, verified accessibility and localisation, narrative synthesis, and the three moonshots — continuous performance signals, verifiable credentials, and an anonymised Iranian benchmark network.

## 4.3 · Dependencies — critical path

Six chains where sequence matters. Building the dependent item first means rebuilding it later, or shipping a genuine risk.

| Build first | Unblocks | Why sequence matters |
|---|---|---|
| P1-04 versioned configuration | P1-05 · P1-01 · P3-02 · P3-03 · P2-07 · P1-02 limits | Almost every capability the roadmap adds needs a place to store per-organisation rules. Building them against constants means rebuilding them later. |
| P1-08 minimum-cohort suppression | P2-01 manager and executive analytics · MS-02 benchmarking | Opening analytics beyond HR without suppression turns aggregates into an authorization bypass. This is a hard prerequisite, not a nice-to-have. |
| P0-08 reliable scheduler | P1-02 SLA · P1-03 delivery · P3-05 plan reviews · P2-05 async PDF | Every time-based and asynchronous feature depends on scheduled work that provably runs exactly once. |
| P1-02 stage_entered_at | P3-04 cycle-time proof · P2-01 stage analytics · escalation | Time in stage is the atom of every workflow metric and every escalation rule. |
| P0-06 employee stage | P1-06 calibration · P3-05 plan effectiveness · trust positioning | Self-assessment supplies the second perspective calibration compares against, and the employee's participation is what makes the process defensible. |
| P1-14 integrations | MS-01 performance signals · reliable contract-expiry alerting | Signals and accurate contract dates both require the customer's systems to feed DbsPulse rather than HR retyping them. |

### Expanded

- **P1-04 versioned configuration → P1-05 · P1-01 · P3-02 · P3-03 · P2-07 · P1-02 limits**  
  Almost every capability the roadmap adds needs a place to store per-organisation rules. Building them against constants means rebuilding them later.

- **P1-08 minimum-cohort suppression → P2-01 manager and executive analytics · MS-02 benchmarking**  
  Opening analytics beyond HR without suppression turns aggregates into an authorization bypass. This is a hard prerequisite, not a nice-to-have.

- **P0-08 reliable scheduler → P1-02 SLA · P1-03 delivery · P3-05 plan reviews · P2-05 async PDF**  
  Every time-based and asynchronous feature depends on scheduled work that provably runs exactly once.

- **P1-02 stage_entered_at → P3-04 cycle-time proof · P2-01 stage analytics · escalation**  
  Time in stage is the atom of every workflow metric and every escalation rule.

- **P0-06 employee stage → P1-06 calibration · P3-05 plan effectiveness · trust positioning**  
  Self-assessment supplies the second perspective calibration compares against, and the employee's participation is what makes the process defensible.

- **P1-14 integrations → MS-01 performance signals · reliable contract-expiry alerting**  
  Signals and accurate contract dates both require the customer's systems to feed DbsPulse rather than HR retyping them.

---

Audit of `sanyzrn/DbsPulse_V2` — branch `main`, commit `ef0166b091d2d167d808702e084c079e5143e307`. Findings derive from static inspection of source files in that commit. No application code was modified. Items that cannot be confirmed from the repository are labelled *Not verifiable from the repository*.
