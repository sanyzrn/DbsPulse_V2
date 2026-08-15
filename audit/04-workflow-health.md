> **DbsPulse V2 — Product, Architecture, Workflow, Security & UX Audit**  
> Repository: <https://github.com/sanyzrn/DbsPulse_V2> · Branch `main` · Commit `ef0166b091d2d167d808702e084c079e5143e307`  
> Site section: 1.3 · Workflow health

# Workflow health — is the process enforced, or merely displayed?

Fifteen checks asking whether the backend and the database prove what the interface implies. 8 of 15 come back enforced — an unusually good result for this segment — but the failures are consequential, and every case where the UI implies enforcement the backend does not provide is called out explicitly.

## Verdict index

| ID | Question | Verdict | Confidence |
|---|---|---|---|
| W-01 | Are stage transitions enforced by the backend, or only by the UI? | Backend enforced | High |
| W-02 | Can a stage be skipped by calling the API directly? | Blocked | High |
| W-03 | Is manager-to-employee ownership enforced at record level? | Enforced for supervisor / deputy / CEO — absent for HR | High |
| W-04 | Are duplicate open evaluations prevented? | Prevented at database level | High |
| W-05 | Are concurrent transitions on the same record safe? | Safe for transitions, unproven for score writes | Medium |
| W-06 | Is submission complete and validated server-side? | Backend enforced | High |
| W-07 | Does the UI faithfully represent what the backend can do? | No — one fully-built capability is hidden | High |
| W-08 | Can a record ever become unrecoverable? | Yes — permanent deadlock is reachable | High |
| W-09 | Do returns / rework / resubmission work end to end? | Backend enforced | High |
| W-10 | Are deadlines, reminders and escalation real? | Reminders only — no enforcement, no escalation | High |
| W-11 | Will reminders actually run in production? | Conditional and single-instance only | High |
| W-12 | Is the audit trail complete and tamper-resistant? | Complete-ish, not tamper-resistant | High |
| W-13 | Is historical integrity of a finalized decision protected? | Strong for the document, weak for the framework | High |
| W-14 | Can the employee influence or contest a decision that affects their job? | No | High |
| W-15 | Can a record be viewed by someone outside its chain? | Blocked, with one privacy caveat | High |

## Detail

### W-01 — Are stage transitions enforced by the backend, or only by the UI?

**Verdict:** Backend enforced · **Confidence:** High

ensure_transition_allowed checks record.status == spec.from_status and current_user.role == spec.allowed_role and, where an assignee field is set, current_user.id == that field — raising before any mutation. The frontend guard booleans in EvaluationDetailPage.tsx:100-135 mirror these rules but are not the enforcement point: removing them changes nothing server-side.

**Repository evidence**

```text
backend/app/services/workflow.py ensure_transition_allowed · frontend/src/pages/EvaluationDetailPage.tsx:100-135
```

### W-02 — Can a stage be skipped by calling the API directly?

**Verdict:** Blocked · **Confidence:** High

Each action is bound to exactly one from_status. Calling ceo_finalize on a submitted record fails the from_status check, so the chain cannot be short-circuited by crafting requests. The manager path is not a bypass: it is a distinct, consistently-applied shape where the record starts at hr_approved with unit_supervisor_user_id = NULL and is_manager_path() is consulted everywhere the supervisor stage matters.

**Repository evidence**

```text
backend/app/services/workflow.py TRANSITIONS · is_manager_path()
```

### W-03 — Is manager-to-employee ownership enforced at record level?

**Verdict:** Enforced for supervisor / deputy / CEO — absent for HR · **Confidence:** High

Supervisor, deputy and CEO actions require current_user.id to equal the record's stored assignee. The two HR transitions (hr_approve, hr_return) declare assignee_field = None, so any user holding the HR role can approve or return any evaluation in the organization. Combined with HR also owning user management and password resets, there is no separation of duties.

**Repository evidence**

```text
backend/app/services/workflow.py TRANSITIONS — assignee_field=None for hr_approve/hr_return
```

### W-04 — Are duplicate open evaluations prevented?

**Verdict:** Prevented at database level · **Confidence:** High

A partial unique index (uq_open_evaluation_per_personnel on subject_personnel_id WHERE status != 'finalized') makes a second open evaluation physically impossible regardless of race timing. create_evaluation also performs an application pre-check and catches IntegrityError, returning 409 with the conflicting evaluation_id so the UI can deep-link to it. This is the correct pattern and rare at this scale.

**Repository evidence**

```text
backend/alembic/versions/b41c07a9d2e1_phase0_integrity_constraints.py:42-48 · backend/app/api/routers/evaluations.py:117-235
```

### W-05 — Are concurrent transitions on the same record safe?

**Verdict:** Safe for transitions, unproven for score writes · **Confidence:** Medium

Transition handlers load the record through _get_record_or_404_for_update, which applies .with_for_update(of=EvaluationRecord), serialising competing approvals. However upsert_scores and set_evaluator_comment use the unlocked _get_record_or_404, so two evaluators editing simultaneously — or an edit landing concurrently with a submit — has no serialisation point. No test exercises a real two-connection race; test_workflow_concurrency.py contains two tests and its docstring admits the limitation.

**Repository evidence**

```text
backend/app/api/routers/evaluations.py:60-78 vs :421-456, :459-487 · backend/tests/test_workflow_concurrency.py
```

### W-06 — Is submission complete and validated server-side?

**Verdict:** Backend enforced · **Confidence:** High

finalize_scoring compares the set of scored indicator IDs against all active indicators and refuses partial submission; validate_evidence independently enforces the ≥3 and ≤40 word bounds on evidence for scores of 1 and 5. Neither rule depends on the browser.

**Repository evidence**

```text
backend/app/services/workflow.py:159-189 · backend/app/services/evaluation.py:34-57
```

### W-07 — Does the UI faithfully represent what the backend can do?

**Verdict:** No — one fully-built capability is hidden · **Confidence:** High

Evaluation periods are complete server-side and documented in the README as a feature, yet the route renders <DisabledFeature title="دوره‌های ارزیابی" /> because FEATURE_PERIODS_ENABLED = false. Anyone auditing by clicking would conclude periods are unbuilt; anyone auditing by reading the README would conclude they are shipped. Both are wrong.

**Repository evidence**

```text
frontend/src/appInfo.ts:13 · frontend/src/App.tsx · backend/app/api/routers/periods.py · README.md
```

### W-08 — Can a record ever become unrecoverable?

**Verdict:** Yes — permanent deadlock is reachable · **Confidence:** High

The transition table contains no cancel, void, withdraw, delete or reassign action, and there is no endpoint to change an in-flight record's assignees. If an assigned supervisor, deputy or CEO leaves, is deactivated, or was assigned in error, the record can never advance — and because the partial unique index blocks any second open record for that employee, that employee can never be evaluated again. The only escape is direct SQL.

**Repository evidence**

```text
backend/app/services/workflow.py TRANSITIONS · backend/app/api/routers/evaluations.py (no cancel/reassign endpoint) · migration b41c07a9d2e1:42-48
```

### W-09 — Do returns / rework / resubmission work end to end?

**Verdict:** Backend enforced · **Confidence:** High

Return transitions exist for HR and deputy, move the record back to the scoring stage, notify the previous owner, and require a reason. Resubmission re-runs the full completeness and evidence validation. Threaded comment replies let the returning stage's objection and the scorer's answer stay attached to the record.

**Repository evidence**

```text
backend/app/services/workflow.py TRANSITIONS (hr_return, deputy_return) · migration c4f7e2a9b103_threaded_comment_replies.py
```

### W-10 — Are deadlines, reminders and escalation real?

**Verdict:** Reminders only — no enforcement, no escalation · **Confidence:** High

Three sweeps exist (contract expiry, SLA, improvement-plan review) and each writes deduplicated in-app notifications to the current stage owner. Nothing is blocked when a deadline passes, nothing escalates to a higher role, no stage has a configurable due date, and the SLA sweep filters on EvaluationRecord.created_at — total case age — while its message tells the recipient the item is waiting for their action. A record returned and resubmitted keeps triggering as overdue.

**Repository evidence**

```text
backend/app/services/scheduled.py run_sla_sweep (created_at <= cutoff) · _current_owner_ids · notify_once
```

### W-11 — Will reminders actually run in production?

**Verdict:** Conditional and single-instance only · **Confidence:** High

The scheduler is an asyncio loop inside the API process, gated by enable_scheduler which defaults to False. Its own docstring states that a multi-instance deployment requires migration to a shared worker or queue. With two replicas every sweep runs twice; with the flag left at its default, no sweep ever runs and the only reminder path is HR clicking the manual trigger.

**Repository evidence**

```text
backend/app/core/scheduler.py (docstring) · backend/app/core/config.py enable_scheduler: bool = False · backend/app/api/routers/admin.py
```

### W-12 — Is the audit trail complete and tamper-resistant?

**Verdict:** Complete-ish, not tamper-resistant · **Confidence:** High

log_event appends actor, event type, old/new JSONB and timestamp for about 35 event types covering transitions, score writes, user and indicator administration, and four of the five exports. But the rows live in the same database the application writes to with full privileges, there is no hash chain or signature linking entries, and no append-only or external store. Two specific gaps: improvement-plan goal add/update/delete are never logged, and export_report_excel has no log_event call.

**Repository evidence**

```text
backend/app/services/audit.py · backend/app/api/routers/reports.py:300-321 · backend/app/api/routers/improvement_plans.py
```

### W-13 — Is historical integrity of a finalized decision protected?

**Verdict:** Strong for the document, weak for the framework · **Confidence:** High

The decision itself is well protected: an immutable final_snapshot, a byte-stable archived PDF with its SHA-256, idempotent archiving, and public token-based verification. What is not protected is the measurement framework — indicators are mutable and unversioned, so editing or deleting an indicator changes the meaning of past evaluations and, because finalize_scoring requires all currently-active indicators, silently invalidates every in-flight draft.

**Repository evidence**

```text
backend/app/services/snapshot.py · backend/app/services/documents.py · backend/app/api/routers/indicators.py · backend/app/services/workflow.py:159-189
```

### W-14 — Can the employee influence or contest a decision that affects their job?

**Verdict:** No · **Confidence:** High

The subject of the evaluation has no stage, no self-assessment, no comment right, and no visibility until the record is finalized (_ensure_can_view admits HR and the three chain members only). After finalization they may acknowledge — 'رؤیت' — which records acknowledged_at and acknowledged_by. There is no objection, appeal or dispute transition, and they cannot download the signed PDF about themselves because summary_pdf is HR-only. For a system whose output is a contract-renewal recommendation, this is the single largest fairness and defensibility gap.

**Repository evidence**

```text
backend/app/api/routers/evaluations.py:81-88 _ensure_can_view, summary_pdf (HR-only) · backend/app/api/routers/me.py acknowledge
```

### W-15 — Can a record be viewed by someone outside its chain?

**Verdict:** Blocked, with one privacy caveat · **Confidence:** High

_ensure_can_view restricts non-HR access to users whose ID appears in unit_supervisor_user_id, deputy_user_id or ceo_user_id — a real record-level (BOLA-resistant) check rather than a role-only check, and list endpoints are scoped per role rather than filtered client-side. The caveat is not the record endpoint but the analytics ones: HR reports aggregate with no minimum-cohort threshold, so filtering to a two-person unit effectively discloses individual scores.

**Repository evidence**

```text
backend/app/api/routers/evaluations.py:81-88 · :300-373 list_evaluations · backend/app/api/routers/reports.py _Filters
```

---

Audit of `sanyzrn/DbsPulse_V2` — branch `main`, commit `ef0166b091d2d167d808702e084c079e5143e307`. Findings derive from static inspection of source files in that commit. No application code was modified. Items that cannot be confirmed from the repository are labelled *Not verifiable from the repository*.
