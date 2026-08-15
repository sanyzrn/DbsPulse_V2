> **DbsPulse V2 — Product, Architecture, Workflow, Security & UX Audit**  
> Repository: <https://github.com/sanyzrn/DbsPulse_V2> · Branch `main` · Commit `ef0166b091d2d167d808702e084c079e5143e307`  
> Site section: 1.1 · Score methodology and confidence

# Weighted scoring model

Seven areas, transparently weighted. Each row expands to show the evidence the score is based on, the specific deductions applied, and the confidence level. Scores reflect what the backend or the database schema provably enforces — never what the UI or the README asserts.

**Formula.** Overall = Σ (area score × weight). Area scores are assigned from inspected source evidence only: a capability scores where it is provably enforced in backend code or the database schema, not where the UI or README claims it.

## Summary

| Area | Score | Weight | Contribution | Confidence |
|---|---|---|---|---|
| Product capability maturity | 58 / 100 | 25% | 14.50 | High |
| Workflow integrity and enforcement | 78 / 100 | 20% | 15.60 | High |
| Security and access control | 62 / 100 | 15% | 9.30 | High |
| Enterprise reliability and operations | 45 / 100 | 15% | 6.75 | Medium |
| UX and usability | 76 / 100 | 10% | 7.60 | Medium |
| Testing and engineering quality | 72 / 100 | 10% | 7.20 | Medium |
| Deployment and production readiness | 52 / 100 | 5% | 2.60 | Medium |
| **Weighted total** | **64 / 100** | **100%** | **64.00** | — |

**Overall maturity: 64 / 100 — Solid internal tool — not yet a commercial performance-management product**

_Shape shows where DbsPulse is strong relative to its own weakest areas. Workflow enforcement is its structural strength; enterprise operations and product capability are the drags on the weighted total._

## Area detail

### Product capability maturity — 58 / 100 (weight 25%)

**Confidence:** High · **Contribution to total:** 14.50 points

**Evidence**

One evaluation object type with 20 fixed indicators on a 1–5 scale (backend/app/core/constants.py, indicators router). Fixed 60/40 section weighting and four hardcoded renewal thresholds. Full four-stage approval chain, return/rework, improvement plans with goals, employee scorecard with acknowledgment, HR analytics with four report endpoints, Excel exports, byte-stable archived PDF with SHA-256 and public QR verification, evaluation periods (backend complete, UI disabled).

**Main deductions**

- No goal / OKR / KPI object at all — nothing to link an evaluation to
- No competency framework or job-family differentiation; the same 20 indicators apply to everyone
- No employee self-assessment step in the state machine
- No 360 / peer / upward feedback (README lists it as out of scope)
- No calibration, normalization or rating-distribution management
- Weights, thresholds and evidence rules are Python constants, not configuration
- Evaluation periods shipped but hidden by FEATURE_PERIODS_ENABLED = false

### Workflow integrity and enforcement — 78 / 100 (weight 20%)

**Confidence:** High · **Contribution to total:** 15.60 points

**Evidence**

A declarative transition table (backend/app/services/workflow.py) checks from-status, actor role and record-level assignee on every action; ensure_transition_allowed raises before any mutation. Transitions load the row with .with_for_update(of=EvaluationRecord). A partial unique index (uq_open_evaluation_per_personnel WHERE status != 'finalized') makes duplicate open evaluations impossible at the database level, and the create endpoint converts the IntegrityError into a 409 carrying the existing evaluation_id. finalize_scoring refuses to submit unless every active indicator is scored, and evidence rules for scores 1 and 5 are validated server-side.

**Main deductions**

- HR transitions have assignee_field = None — any HR user may approve or return any record (no ownership, no separation of duties)
- Score writes and evaluator comments do not take the row lock used by transitions
- No cancel / void / reassign transition: a record whose approver leaves becomes permanently stuck and blocks all future evaluations of that employee
- Deadlines produce notifications only — nothing is blocked, escalated to a higher role, or auto-advanced
- The SLA sweep measures total case age (created_at), not time in the current stage
- The scheduler is an in-process asyncio loop, disabled by default and unsafe with more than one replica

### Security and access control — 62 / 100 (weight 15%)

**Confidence:** High · **Contribution to total:** 9.30 points

**Evidence**

Argon2 password hashing; short-lived access tokens held only in JavaScript memory; refresh tokens in an httponly, samesite=strict, path-scoped cookie with server-side session rows, rotation, reuse detection and family revocation; a token_version claim that invalidates every issued token on password change; role gates via require_roles on every protected route; record-level view checks (_ensure_can_view); a public verification endpoint keyed by an unguessable token rather than the sequential evaluation code; production config validators that refuse the default JWT secret and non-HTTPS origins; nginx CSP, X-Frame-Options DENY, nosniff and Referrer-Policy.

**Main deductions**

- A migration seeds five demo accounts with a published shared password, and the container entrypoint applies migrations on every boot
- Rate limiting keys on a client-influenced X-Forwarded-For and is in-process only
- No per-account lockout, no MFA, no session list or self-revocation for users
- The single HR role is simultaneously process owner, super-admin, user manager and password resetter
- Analytics endpoints have no minimum-cohort suppression, so small units are re-identifiable
- Audit log is append-only by convention only — no hash chain, no WORM storage
- Excel exports write user-supplied text without neutralising leading =, +, -, @

### Enterprise reliability and operations — 45 / 100 (weight 15%)

**Confidence:** Medium · **Contribution to total:** 6.75 points

**Evidence**

Health and readiness endpoints (/api/health, /api/health/ready), request-ID middleware with a non-leaking 500 handler, pool_pre_ping on the engine, idempotent PDF archiving with graceful degradation when WeasyPrint native libraries are missing, notification deduplication keys, and 15 purposeful indexes across the hot query paths.

**Main deductions**

- Single-organization schema — no path to multi-company SaaS without a migration and query-wide scoping
- In-process scheduler; horizontal scaling silently duplicates or drops sweeps
- No metrics, tracing or error-tracking integration; observability is stdout logs plus request IDs
- No data retention, purge, legal-hold or subject-deletion capability; final PDFs are stored as bytes inside PostgreSQL forever
- No backup / restore / disaster-recovery procedure in the repository (external infrastructure not verifiable)
- No SSO, no HRIS or payroll integration, no webhooks, no versioned public API
- Notifications are in-app only, so the whole process depends on users choosing to log in

### UX and usability — 76 / 100 (weight 10%)

**Confidence:** Medium · **Contribution to total:** 7.60 points

**Evidence**

Genuinely Persian-first: lang=fa dir=rtl, full Tailwind RTL, self-hosted Vazirmatn (also inside the PDF template), a native Birashk-algorithm Jalali converter with no external dependency (frontend/src/utils/jalali.ts), Persian digit rendering in exports, and Persian error/label text throughout. Role-specific dashboards, a skip link to #main-content, aria-labelled navigation, lazy-loaded routes, auto-saving score drafts, conflict responses that deep-link to the blocking evaluation.

**Main deductions**

- No mobile application and no PWA manifest; responsiveness is CSS-only
- Employees see nothing until the evaluation is finalized and can never download the signed PDF about themselves
- A navigation entry exists for a feature that renders a 'disabled' panel (evaluation periods)
- No accessibility test in CI; keyboard and screen-reader behaviour unverified
- No English locale scaffolding — user-facing strings are inline Persian literals

### Testing and engineering quality — 72 / 100 (weight 10%)

**Confidence:** Medium · **Contribution to total:** 7.20 points

**Evidence**

152 backend tests with a session-scoped 'alembic upgrade head' and savepoint-per-test rollback fixture (backend/tests/conftest.py), 29 frontend tests with vitest and Testing Library, ruff with E/W/F/I/B/UP rule sets, oxlint, a strict tsc -b build step, pinned dependency versions, and consistently documented Persian docstrings that explain intent rather than restating code.

**Main deductions**

- backend/tests/test_workflow_concurrency.py contains two tests and its own docstring concedes it does not exercise a true two-connection race
- No end-to-end test; the enforcement chain from UI action to database state is never tested as a whole
- No load, soak or performance test; concurrency behaviour under real contention is unmeasured
- No coverage gate in CI, so untested paths cannot be distinguished from tested ones
- This audit could not execute the suite (PostgreSQL unavailable) — CI configuration verified, results not observed

### Deployment and production readiness — 52 / 100 (weight 5%)

**Confidence:** Medium · **Contribution to total:** 2.60 points

**Evidence**

Docker Compose with db and backend bound to 127.0.0.1, an nginx front-end container with security headers, a TLS example config (deploy/nginx-https.conf.example, referenced but not inspected), CI running lint, tests and build on every push and pull request to main, and production config validators that fail fast on insecure settings.

**Main deductions**

- docker-entrypoint.sh runs 'alembic upgrade head' on every container start — including the demo-user seed migration
- The backend image declares no USER, so the application runs as root
- No rollback, blue-green or canary strategy; no migration-reversibility check in CI
- No HSTS in the shipped nginx template; secrets come from plain environment variables with demo defaults in compose
- No alerting attached to the health endpoints (external monitoring not verifiable from the repository)

---

Audit of `sanyzrn/DbsPulse_V2` — branch `main`, commit `ef0166b091d2d167d808702e084c079e5143e307`. Findings derive from static inspection of source files in that commit. No application code was modified. Items that cannot be confirmed from the repository are labelled *Not verifiable from the repository*.
