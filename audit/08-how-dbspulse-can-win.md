> **DbsPulse V2 — Product, Architecture, Workflow, Security & UX Audit**  
> Repository: <https://github.com/sanyzrn/DbsPulse_V2> · Branch `main` · Commit `ef0166b091d2d167d808702e084c079e5143e307`  
> Site section: 3. How DbsPulse Can Win

# How DbsPulse can win — practical advantages, honest positioning, and AI that stays advisory

Differentiation grounded in what the codebase already does well and what the Iranian market actually needs — not parity with every global suite. Each opportunity names the findings it depends on, so strategy and roadmap stay connected.

## Where DbsPulse actually stands

DbsPulse is a real, well-engineered, single-organization performance-evaluation and contract-renewal system — not a prototype and not a dashboard. Its workflow engine and document-integrity chain are stronger than its market segment would suggest. What it is not, yet, is a performance-management product: it has no goals, no competencies, no employee voice, no calibration, no configurability, no integrations and no outbound notifications. The honest summary is that DbsPulse has built the hardest 20% (verifiable, enforced process) and skipped much of the expected 80% (the content of performance management).

## 3.1 · Existing assets — what is already strong enough to build a strategy on

Verified strengths — each one read in source. These are the foundations the rest of section 3 leverages.

### A declarative, backend-enforced state machine

The seven-transition table checks from-status, role and record-level assignee in one place before any mutation, and transitions hold a row lock. Most systems of this size scatter these checks through endpoint bodies or trust the UI; DbsPulse does neither.

**Evidence**

```text
backend/app/services/workflow.py — Transition dataclass, TRANSITIONS, ensure_transition_allowed
```

### Database-level protection against duplicate open evaluations

A partial unique index makes a second open evaluation for the same employee impossible under any race, and the create endpoint converts the resulting IntegrityError into a 409 carrying the conflicting evaluation_id so the UI can deep-link to it. This is the correct pattern, correctly applied.

**Evidence**

```text
migration b41c07a9d2e1:42-48 · backend/app/api/routers/evaluations.py:117-235
```

### Document integrity that most competitors of this size do not attempt

Finalization writes an immutable snapshot, renders a byte-stable PDF, stores its SHA-256, is idempotent on re-run, degrades gracefully when WeasyPrint's native libraries are missing, and exposes public verification through an unguessable token rather than the guessable sequential evaluation code — a threat the team identified and fixed deliberately.

**Evidence**

```text
backend/app/services/documents.py · snapshot.py · migration b28cc6abdf2a (verify_token with backfill) · backend/app/api/routers/verify.py
```

### Session handling that is better than the project's size would predict

Access tokens live only in JavaScript memory, never localStorage. Refresh tokens sit in an httponly, samesite=strict, path-scoped cookie backed by server-side session rows with rotation, a 60-second grace window, reuse detection that revokes the entire family, and a token_version claim that invalidates every issued token on password change.

**Evidence**

```text
frontend/src/api/client.ts · backend/app/api/routers/auth.py · backend/app/services/sessions.py · backend/app/api/deps.py
```

### Genuinely Persian-first, not translated

A native Birashk-algorithm Jalali converter with no external dependency, full Tailwind RTL, self-hosted Vazirmatn in both the application and the PDF, Persian digits in Excel exports, and Persian domain vocabulary throughout. This is the product's clearest existing advantage over any localised international suite.

**Evidence**

```text
frontend/src/utils/jalali.ts · backend/app/services/excel.py · backend/app/templates/evaluation_summary.html
```

### Production-aware configuration guards

Settings validators refuse to start in production with the default JWT secret, with localhost or non-HTTPS CORS origins, or with a non-HTTPS public base URL — failing fast instead of running insecurely. OpenAPI docs are disabled in production and the 500 handler returns a request ID without leaking internals.

**Evidence**

```text
backend/app/core/config.py · backend/app/main.py
```

### Real engineering hygiene

152 backend and 29 frontend tests, ruff with a broad rule set, oxlint, a strict tsc -b build in CI on every push and pull request, pinned dependencies, purposeful indexes across the hot paths, and Persian docstrings that explain why the code exists rather than restating what it does.

**Evidence**

```text
.github/workflows/ci.yml · backend/tests/conftest.py · migrations c7f2d81a5e30 and d5b1f3e7c920 (15 indexes)
```

### A sharply chosen use case

Contract-renewal decision support is a narrow, high-stakes, recurring problem that the global suites treat as a side effect of their review module. Owning it — with threshold-based recommendations, contract-expiry alerting and a verifiable decision document — is a more defensible position than competing on breadth.

**Evidence**

```text
backend/app/core/constants.py FINAL_RESULT_THRESHOLDS · backend/app/services/scheduled.py · README.md
```

## 3.2 · Competitive advantages to pursue

High-value differentiation where DbsPulse can be better rather than merely cheaper. Referenced finding IDs are the prerequisites — see section 2 (Gap Analysis) for the evidence and the fix.

### 01. Own the renewal decision, end to end

No competitor in this segment treats contract renewal as the primary object. DbsPulse already produces a threshold-based recommendation, warns on contract expiry, and issues a hash-verified decision document. Extending that into early risk detection (P3-01), renewal documentation packs and a renewal pipeline view makes 'the system Iranian HR uses at renewal time' a category DbsPulse defines rather than competes in.

**Depends on:** P3-01 · P3-03 · P1-02

### 02. Simplicity as a measured promise

Mid-market buyers abandon enterprise suites over friction, not features. The auto-save, role-scoped queues, forty-word evidence cap and manager path are already friction reducers — but nothing measures them. Instrumenting minutes per evaluation and hours per stage (P3-04) turns simplicity into a number a buyer can compare, and points the roadmap at whichever step is actually slow.

**Depends on:** P3-04 · P2-03 · P2-04

### 03. Persian-first as compliance, not translation

Native Jalali handling, RTL and Persian typography are already done properly. Layering Iranian labour-law contract mechanics, a working-day holiday calendar, Jalali fiscal periods and locally-recognised renewal documentation (P3-03) creates a moat an international vendor cannot cross by hiring a translator.

**Depends on:** P3-03 · P1-04 · P1-07

### 04. Verifiable process as the trust argument

The enforced state machine, immutable snapshot, SHA-256 and QR verification already support a claim nobody else in the segment makes: every renewal decision can be proven to have followed the process and to be unaltered. Closing the audit-log integrity gap (P1-09) and adding employee voice (P0-06) turns that from an implementation detail into the reason a cautious employer chooses this product.

**Depends on:** P1-09 · P0-06 · MS-03

### 05. Configurability as the path to a second customer

Weights, thresholds, evidence rules, stages and labels currently live in code. Versioned configuration (P1-04) followed by a process designer (P3-02) is what lets DbsPulse serve organisations with different practices from one codebase — the difference between a project and a product.

**Depends on:** P1-04 · P1-05 · P3-02

### 06. Mobile-first for the roles that block the chain

Supervisors on a floor and executives between meetings are the people whose delay stalls every case. A PWA with push and a one-indicator-per-screen scoring flow (P2-04), combined with real outbound notifications (P1-03), attacks cycle time where it is actually lost.

**Depends on:** P2-04 · P1-03

## What DbsPulse should deliberately not chase

- Full parity with Workday or SAP SuccessFactors. Compensation planning, succession, learning management, workforce planning and org modelling are decade-scale investments and are not why anyone would buy DbsPulse.
- Anonymous full 360 with rater-set management. The machinery is heavy, the cultural fit in many Iranian organisations is uncertain, and a lightweight manager-peer input path (P1-06) captures most of the value.
- Engagement surveys and sentiment analysis. Culture Amp owns that category and it does not reinforce the contract-renewal wedge.
- Multi-tenant SaaS as an early goal. It is a rearchitecture, not a feature; only pursue it when there is a second and third paying customer demanding hosted delivery.
- AI that produces or approves a decision. Not a capability question — an ethical and legal boundary this product must not cross.

## Persian-market opportunities

### Iranian payroll and HR system connectors

The personnel list must come from the customer's system of record, not from typing. Connectors to the local payroll and HR systems Iranian companies actually run — alongside a generic personnel-sync API keyed on personnel_code — remove the data-drift problem that would otherwise make contract-expiry alerting unreliable.

### Jalali fiscal cycles and working-day service levels

Deadlines that ignore Iranian holidays are wrong deadlines. A holiday calendar driving working-day calculations, and periods aligned to the Iranian fiscal year, are small features that signal the product was built here.

### In-country messaging channels

Email adoption varies; SMS and local messengers are how approvals actually get chased. Building the channel abstraction (P1-03) with an Iranian SMS gateway and optional local messenger bot is a practical advantage over any vendor that assumes email plus Slack.

### Data residency as a default assurance

Self-hosted, in-country deployment is already the shipping model. Making residency an explicit, documented guarantee — including that any AI feature runs locally or with a named, disclosed processor — answers the objection that blocks international SaaS in many Iranian organisations before the conversation starts.

### Persian-language performance content

A library of indicator wording, evidence examples and improvement-plan goals written in professional Persian, tuned by industry, is content no international product will produce and every local HR team needs on day one.

## 3.3 · AI opportunities and safeguards

Four features that qualify, five that are refused.

**Governing principle.** AI in DbsPulse must assist the people who decide and must never decide. Because the product's output is a recommendation about whether someone's employment continues, every AI feature is evaluated against six questions before it is built: which specific user problem it solves, whether the product already holds the data it needs, whether it is implementable and maintainable in this stack, what it does to privacy and security, whether its output is explainable and human-reviewed, and what business value it produces that is measurable. A feature that fails any one of these is not built.

### Qualified AI features

| Feature | User / business problem | Available product data | Feasibility | Privacy & security | Explainability & human review | Measurable value |
|---|---|---|---|---|---|---|
| **P3-06 — Evidence-quality assistant** | Word-count validation cannot tell a specific behavioural justification from padded text, yet that text is the written basis of a contract decision. | Evidence text as it is typed, plus the indicator being scored. No historical personal data required. | Straightforward — non-blocking guidance beside the existing deterministic word check, which remains the only hard rule. | Prefer a self-hosted or in-region model. If external, send minimal text without identifiers, retain nothing, disclose the processor, allow per-organisation opt-out. | Named checks with plain-Persian reasons; the evaluator's words are always the record, suggestions are never auto-inserted. | Fewer returns for inadequate justification; measurably higher evidence-quality rate; a stronger file in a dispute. |
| **P3-07 — Rater-bias and pattern detection** | Single-rater scoring plus fixed numeric thresholds means a lenient manager's team is systematically likelier to be renewed than a strict manager's equally performing team, and nothing detects this. | Existing scores by rater, unit and period — no new collection at all. Statistics before machine learning. | Low technical risk; the main requirement is enough volume for the comparison to mean anything. | Visible only to HR inside the calibration workflow; never shown to the employee; never used in the employee's own record. | Published method and thresholds, so a flagged manager can see exactly what pattern triggered the prompt. | Comparable scores across managers, which is what makes a threshold-based renewal recommendation defensible. |
| **P3-01 — Renewal-risk early warning (rules-first)** | Risk becomes visible at finalization, when it is too late to coach, plan or retain. | Prior finalized percentages and trajectory, indicator-level weak spots, improvement-plan history, contract dates — all already stored. | Deliberately a transparent rule set first; a model only if measured to outperform it, and even then the rule-based explanation stays the interface. | Internal to the employee's existing chain and HR; no new data, no external processing. | Presented as named contributing factors with a suggested action, never as an opaque score. | Avoidable attrition prevented and improvement plans started while they can still change the outcome. |
| **P3-08 — Narrative synthesis of qualitative content** | Carefully collected evidence and comments go unread at decision time because there is too much of it and no summary. | Evidence text, comments and threaded replies already attached to the record. | Bounded, well-understood summarisation over short texts. | Self-hosted or in-region preferred; nothing leaves the deployment without disclosure and consent. | Output is a labelled draft citing the source comments, editable, and stored only after a human adopts it — at which point authorship is attributed to that person. | Faster, better-informed review of a renewal caseload without diluting accountability for the record. |

#### Expanded

##### P3-06 — Evidence-quality assistant

- **User / business problem:** Word-count validation cannot tell a specific behavioural justification from padded text, yet that text is the written basis of a contract decision.
- **Available product data:** Evidence text as it is typed, plus the indicator being scored. No historical personal data required.
- **Implementation feasibility:** Straightforward — non-blocking guidance beside the existing deterministic word check, which remains the only hard rule.
- **Privacy & security implications:** Prefer a self-hosted or in-region model. If external, send minimal text without identifiers, retain nothing, disclose the processor, allow per-organisation opt-out.
- **Explainability & human review:** Named checks with plain-Persian reasons; the evaluator's words are always the record, suggestions are never auto-inserted.
- **Measurable business value:** Fewer returns for inadequate justification; measurably higher evidence-quality rate; a stronger file in a dispute.

##### P3-07 — Rater-bias and pattern detection

- **User / business problem:** Single-rater scoring plus fixed numeric thresholds means a lenient manager's team is systematically likelier to be renewed than a strict manager's equally performing team, and nothing detects this.
- **Available product data:** Existing scores by rater, unit and period — no new collection at all. Statistics before machine learning.
- **Implementation feasibility:** Low technical risk; the main requirement is enough volume for the comparison to mean anything.
- **Privacy & security implications:** Visible only to HR inside the calibration workflow; never shown to the employee; never used in the employee's own record.
- **Explainability & human review:** Published method and thresholds, so a flagged manager can see exactly what pattern triggered the prompt.
- **Measurable business value:** Comparable scores across managers, which is what makes a threshold-based renewal recommendation defensible.

##### P3-01 — Renewal-risk early warning (rules-first)

- **User / business problem:** Risk becomes visible at finalization, when it is too late to coach, plan or retain.
- **Available product data:** Prior finalized percentages and trajectory, indicator-level weak spots, improvement-plan history, contract dates — all already stored.
- **Implementation feasibility:** Deliberately a transparent rule set first; a model only if measured to outperform it, and even then the rule-based explanation stays the interface.
- **Privacy & security implications:** Internal to the employee's existing chain and HR; no new data, no external processing.
- **Explainability & human review:** Presented as named contributing factors with a suggested action, never as an opaque score.
- **Measurable business value:** Avoidable attrition prevented and improvement plans started while they can still change the outcome.

##### P3-08 — Narrative synthesis of qualitative content

- **User / business problem:** Carefully collected evidence and comments go unread at decision time because there is too much of it and no summary.
- **Available product data:** Evidence text, comments and threaded replies already attached to the record.
- **Implementation feasibility:** Bounded, well-understood summarisation over short texts.
- **Privacy & security implications:** Self-hosted or in-region preferred; nothing leaves the deployment without disclosure and consent.
- **Explainability & human review:** Output is a labelled draft citing the source comments, editable, and stored only after a human adopts it — at which point authorship is attributed to that person.
- **Measurable business value:** Faster, better-informed review of a renewal caseload without diluting accountability for the record.

### Explicitly refused — not a capability question

- **Automatic scoring or automatic renewal recommendation** — This would make the model the decision-maker in an employment decision. It is the boundary the product must not cross, regardless of accuracy.

- **Inference of protected or sensitive characteristics** — No health, family, political, religious or personal-life inference of any kind. Not a feature — a permanent exclusion.

- **Sentiment scoring of individual employees** — Unreliable, invasive, and it changes what people are willing to write, which degrades the evidence the product depends on.

- **Surveillance-style productivity signals** — Keystroke, screen or message monitoring would destroy trust in the system and contaminate the performance signal layer of MS-01 before it starts.

- **Chat assistant with unrestricted access to all employee data** — A natural-language interface that bypasses the record-level authorization the rest of the system enforces would be the largest single security regression available.

### Risk safeguards

- **Bias amplification** — Never train on historical outcomes as ground truth — past renewal decisions encode past bias. Rules-first wherever a rule works. Any statistical feature must be tested for differential impact across units, tenure and job families before release, and re-tested on a schedule.

- **Opaque scoring** — No unexplained number ever reaches a decision-maker. Every AI-derived output arrives with named factors, a plain-Persian explanation and a documented method. If an output cannot be explained, it is not shown.

- **Automated employment decisions** — Enforce architecturally, not by policy: AI outputs are advisory records with no write path to recommendation, final percentage or workflow status. The recommendation is produced by the deterministic threshold table and finalized by a human, and the archived snapshot records the human actor.

- **Inappropriate use of sensitive employee data** — Data minimisation per feature, explicit purpose limitation, no cross-purpose reuse, no training on customer data without separate consent, per-organisation opt-out for every AI feature, in-region or self-hosted inference preferred, and disclosure of any external processor.

- **Loss of human accountability** — Every AI-assisted artifact records who adopted it. A suggestion the evaluator accepted becomes the evaluator's statement. The audit log distinguishes assistance offered from content authored, and the archived legal document contains only human-adopted text.

- **Employees unaware they are subject to AI-assisted assessment** — Publish which AI features are enabled in that organisation and what they do, in Persian, on a page the employee can reach from their own scorecard. Transparency is a product feature here, not a legal footnote.

---

Audit of `sanyzrn/DbsPulse_V2` — branch `main`, commit `ef0166b091d2d167d808702e084c079e5143e307`. Findings derive from static inspection of source files in that commit. No application code was modified. Items that cannot be confirmed from the repository are labelled *Not verifiable from the repository*.
