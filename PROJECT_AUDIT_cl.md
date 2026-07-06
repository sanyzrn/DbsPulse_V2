# PROJECT_AUDIT.md — DbsPulse (سامانه ارزیابی عملکرد سازمانی)

**Audited artifact:** `soooonet.zip` — FastAPI (Python 3.11, SQLAlchemy 2.0, Alembic, PostgreSQL 16) backend + React 19 / TypeScript / Vite / Tailwind v4 frontend. Four-stage approval workflow (Unit Supervisor → HR → Deputy → CEO) for personnel performance evaluation prior to contract renewal, with PDF/QR-verifiable output.

**Scope of this audit:** full static review of ~186 files (~15.7k LOC) across backend, frontend, tests, CI, Docker/Nginx, and deployment docs. No code was modified; this document is a read-only assessment.

**Headline assessment:** this is an unusually mature codebase for its size — it already implements many practices teams get wrong (in-memory access tokens + HttpOnly refresh cookies, refresh-token rotation with theft detection, Argon2, NIST-800-63B password policy, autoescaped Jinja2 + sandboxed WeasyPrint URL fetcher, declarative workflow state machine, structured audit log, request-ID middleware, CSP headers, loopback-only DB/backend ports). The findings below are therefore weighted toward **real but second-order** issues — enumeration/privacy leaks, scalability ceilings, missing operational tooling, accessibility gaps, and product/UX gaps — rather than fundamental flaws. Every item below was verified against the actual source, not assumed.

---

# Part 1 – Complete Audit

## 1. Security

### 1.1 Public verification endpoint leaks performance data via sequential-ID enumeration
**Issue:** `GET /api/verify/{evaluation_code}` (`backend/app/api/routers/verify.py`) is intentionally unauthenticated (for QR-code scanning on printed documents) and returns `subject_full_name`, `org_unit`, `final_weighted_pct`, and `recommendation` for any finalized evaluation. Evaluation codes are generated from a plain Postgres sequence (`EVL-0001`, `EVL-0002`, …, see `next_evaluation_code`). Rate limiting is only 30 req/min per IP with no CAPTCHA/backoff escalation.
**Why it's a problem:** Anyone can walk the sequence (`EVL-0001` … `EVL-9999`) and harvest every employee's name, org unit, and performance score/recommendation — a serious internal-privacy leak, especially since HR performance data is sensitive personal information (and in many jurisdictions regulated). The 30/min limit only slows a single-threaded scraper; a distributed scraper (or one that rotates IPs) is not meaningfully throttled.
**Best professional solution:** Replace sequential evaluation codes with a non-guessable identifier for the *public* verification surface — e.g. a random 128-bit token (UUIDv4 or `secrets.token_urlsafe(24)`) stored alongside the record and embedded in the QR/verify URL, while keeping the human-readable `EVL-000N` code for internal UIs only. Alternatively, require a short-lived, single-purpose signed token embedded only in the printed QR.
**Implementation strategy:**
1. Add a `verify_token` column (unique, indexed) to `evaluation_records`, generated at finalization time in `ceo_finalize`/`archive_final_pdf`.
2. Change `verify_url_for()` to build the URL from `verify_token`, not `evaluation_code`.
3. Change the `verify` router to look up by `verify_token`.
4. Keep `evaluation_code` for internal search only; never expose it as the sole lookup key on an unauthenticated endpoint.
5. Add a backfill Alembic migration for existing finalized rows.
6. Consider lowering the public rate limit further (e.g. 10/min) and logging repeated misses per IP for alerting.

### 1.2 Secrets present in the shared archive (`backend/.env`)
**Issue:** `backend/.env` is correctly listed in `.gitignore` (so it isn't committed to git), but it **was included in the zip archive** handed to this audit, and contains what appears to be a real local Postgres password (`DATABASE_URL=postgresql+psycopg://postgres:Sany1910@localhost:5432/dbspulsenew`).
**Why it's a problem:** Whoever packaged this zip for review/handoff/deployment likely did `zip -r project.zip .` without excluding `.env`. If this archive is emailed, uploaded to a shared drive, or attached to a ticket, the credential leaks outside its intended blast radius even though git itself is clean. Credentials that "only" protect a local dev database are still worth rotating once potentially exposed, and this pattern (an otherwise git-safe secret escaping via zip/tarball/CI-artifact) is a common real-world leak vector.
**Best professional solution:** Rotate the exposed password immediately; never bundle `.env` in distributable archives; add a packaging step that explicitly denylists `.env*`.
**Implementation strategy:**
1. Rotate the local Postgres password referenced in `.env`.
2. Add a `.git-archive-ignore`/packaging script (`tar`/`zip` with `-x .env`) or a `make package` target that copies only tracked files (`git archive`).
3. Add a pre-commit/CI **secret-scanning** step (e.g. `gitleaks detect` or `trufflehog`) that also runs against release archives, not just git history.
4. Document in the README: "never zip the working tree directly; use `git archive HEAD`."

### 1.3 Rate limiting is in-process/in-memory (SlowAPI default backend)
**Issue:** `app/core/rate_limit.py` creates `Limiter(key_func=get_remote_address)` with no `storage_uri`, so SlowAPI defaults to an in-memory counter local to a single process.
**Why it's a problem:** The moment the backend is scaled horizontally (multiple Uvicorn workers, multiple containers/replicas — which the roadmap explicitly anticipates, per the comment in `scheduler.py`/`config.py` about "single-instance" scheduling), each instance keeps its own counters. A "10 login attempts/minute" limit effectively becomes "10 × N replicas" attempts/minute, silently weakening brute-force protection exactly when the app is under the most load/scrutiny. It also means limits reset on every process restart/deploy.
**Best professional solution:** Back SlowAPI with a shared store (Redis) once more than one backend process/instance is running.
**Implementation strategy:**
1. Add Redis as a service (already natural next to Postgres in `docker-compose.yml`).
2. `Limiter(key_func=get_remote_address, storage_uri="redis://redis:6379/0")`.
3. Add a health check for Redis in compose, and a graceful degradation path (log + allow) if Redis is briefly unavailable, rather than hard-failing all requests.
4. Also rate-limit by **username** (in addition to IP) on `/auth/login`, since IP-based limits don't stop credential stuffing from many source IPs against one account.

### 1.4 No account lockout / anomaly detection beyond token-family revocation
**Issue:** Failed logins are logged (`login_failed` audit events) and rate-limited, but there's no per-account lockout, no escalating backoff, and no alerting on repeated failures against a single username.
**Why it's a problem:** A slow, low-and-slow distributed brute force (a few attempts/minute per IP, many IPs) stays under the rate limit indefinitely and is only visible if someone actively queries the audit log.
**Best professional solution:** Add a lightweight anomaly signal: after N failed logins for a given username within a window, temporarily require a short cool-down or a CAPTCHA, and surface a dashboard/notification to HR/security.
**Implementation strategy:** Track failed-attempt counters per username (Redis, TTL-based) in the login endpoint; on threshold, return a generic 429 regardless of whether the password would have been correct; add a scheduled sweep (reusing the existing `scheduled.py` pattern) that raises a notification to HR when a username crosses a threshold.

### 1.5 JWT access tokens cannot be revoked before expiry
**Issue:** Access tokens are short-lived (30 min) and validated against `token_version`, but that check only happens on refresh and on `get_current_user` — which *does* re-check `token_version` per request (good), but there is no immediate server-side "kill switch" for a single compromised access token independent of full account/session revocation. This is a minor design tradeoff, not a bug, but worth documenting.
**Why it's a problem:** In an incident-response scenario ("we think this specific token was phished in the last 10 minutes"), the operational answer today is "bump `token_version`," which logs out *all* of the user's sessions/devices, not just the suspected one. That's acceptable but should be an explicit, documented tradeoff for the ops runbook.
**Best professional solution:** Keep the current design (it's reasonable for this app's risk profile) but document the tradeoff, and consider a `jti`-based access-token denylist (short TTL, matches token lifetime) for true single-token revocation in a future security hardening pass.
**Implementation strategy:** Add a short section to `README.md`/an `SECURITY.md` runbook describing: "to revoke a single session, use X; to revoke all sessions for a user, increment token_version (already automatic on password change)."

### 1.6 CORS/cookie configuration should be re-verified per deployment target
**Issue:** `SameSite=strict` + `secure` cookie flags are correctly conditioned on `ENVIRONMENT=production`, and CORS origins are configurable. This is good, but there is no automated check (CI or startup assertion) that `cors_origins` in a production `.env` doesn't accidentally include `http://` origins or wildcard-like patterns.
**Why it's a problem:** A future engineer copy-pasting `.env.example` into a production `.env` might forget to update `CORS_ORIGINS`/`PUBLIC_BASE_URL` from localhost values, silently breaking cookie delivery (SameSite=strict + cross-origin) or, worse, permissively widening it later ("just add `*`" pressure under a deploy deadline).
**Best professional solution:** Add the same defensive pattern already used for `JWT_SECRET_KEY` (`_forbid_insecure_secret_in_production`) to CORS/public URL: refuse to start in `production` if origins contain `localhost`/`127.0.0.1` or a scheme mismatch with `secure` cookies.
**Implementation strategy:** Extend the `model_validator` in `config.py` to validate `cors_origins_list` and `public_base_url` against `environment == "production"`.

### 1.7 No Content-Security-Policy `report-uri`/`report-to` or CSP violation monitoring
**Issue:** The Nginx config ships a solid CSP (`default-src 'self'; ...; frame-ancestors 'none'`), but there is no reporting endpoint, so CSP violations (which would indicate either a bug or an actual injection attempt) are silently dropped by the browser.
**Why it's a problem:** CSP without reporting is a seatbelt with no crash sensor — it protects, but you never learn when it fired.
**Best professional solution:** Add a `report-to`/`report-uri` directive pointing at a lightweight logging endpoint (or a third-party collector), and alert on spikes.
**Implementation strategy:** Add a `/api/csp-report` POST endpoint (unauthenticated, heavily rate-limited, just logs), reference it in the CSP header, and wire logs into whatever log aggregation is chosen (see §10 Observability).

---

## 2. Backend Architecture & Code Quality

### 2.1 Business-rule constants are hardcoded, not configurable
**Issue:** `app/core/constants.py` hardcodes section weights (60/40), the evidence word minimum (15), the evidence-exempt score (3), and the four final-result thresholds (60/75/90/101) as Python literals.
**Why it's a problem:** These are exactly the kind of numbers an HR policy change will touch (e.g., "raise the specialized weight to 45%" or "require 20 words of evidence"). Today that requires a code change, PR review, and redeploy for what is fundamentally a business-policy edit, not an engineering change. It also means there is no historical record of *when* a policy value changed, separate from the git log.
**Best professional solution:** Move these into a versioned, admin-editable settings table (already have `GET /api/config` returning them read-only to the frontend — the natural next step is a `PUT` for HR/admin, with the changes taking effect for **new** evaluations only, since finalized snapshots already freeze the values used at the time).
**Implementation strategy:**
1. Add an `app_settings` table (key/value + effective-from timestamp, or a single-row config table with an audit trail via the existing `audit_log`).
2. Add HR-only `PUT /api/config` with validation (weights sum to 1.0, thresholds monotonic and cover [0,100]).
3. Keep sane in-code defaults as a fallback/seed.
4. Because `EvaluationRecord.final_snapshot` already freezes computed values at finalization, changing config mid-flight only affects evaluations not yet finalized — document this explicitly so HR understands the effective-date semantics.

### 2.2 Notification and audit-log tables have no retention/pruning strategy
**Issue:** `Notification` rows are created liberally (per workflow transition, per SLA sweep with dedup) and `AuditLog` rows are created for essentially every mutating action, but nothing in the codebase deletes or archives old rows. `AuthSession` rows accumulate similarly (every login creates one, every refresh rotates to a new one) with no cleanup job for long-expired/revoked sessions.
**Why it's a problem:** Over years of operation, these tables grow unbounded. `AuditLog` almost certainly *should* be kept indefinitely for compliance, but should be moved to cheaper/cold storage instead of living in the hot OLTP table forever; `Notification` and `AuthSession` have no such requirement and will bloat indexes and slow queries (e.g., the notification bell's unread-count query) as the organization ages.
**Best professional solution:** Add scheduled maintenance jobs, following the exact pattern already established in `services/scheduled.py`:
- Purge/soft-delete read notifications older than N months.
- Hard-delete `AuthSession` rows that are both `revoked_at IS NOT NULL` and older than the refresh-token TTL.
- Partition or archive `AuditLog` to a separate table/warehouse after N years, keeping only aggregates or a compressed export in the hot path.
**Implementation strategy:** Add `run_notification_cleanup_sweep`, `run_expired_session_cleanup_sweep` functions in `scheduled.py`, include them in `run_all_sweeps`, and add unit tests mirroring the existing `test_scheduled.py` patterns.

### 2.3 `Personnel.is_manager` toggle doesn't reconcile in-flight evaluations
**Issue:** In `PATCH /api/personnel/{id}` (`personnel.py`), flipping `is_manager` to `True` correctly clears the `EvaluationAccess.unit_supervisor_user_id`, but if that personnel currently has an **open** (non-finalized) `EvaluationRecord` with a non-null `unit_supervisor_user_id` and `status=draft/submitted`, that in-flight record is left exactly as-is — now inconsistent with the person's new "manager path" designation.
**Why it's a problem:** The workflow now has an evaluation record that doesn't match `is_manager_path()`'s expectations for *new* evaluations, since the invariant "manager path ⇒ no supervisor" is enforced only at creation time (`create_evaluation`), not retroactively. This is an edge case, but a real inconsistency window: HR could promote someone to "manager" mid-evaluation-cycle and the existing open record keeps behaving as a normal (non-manager) evaluation, which may or may not be intended, but is undocumented and untested.
**Best professional solution:** Either (a) explicitly block changing `is_manager` while an open evaluation exists for that person (simplest, safest), or (b) explicitly document and test the "in-flight record keeps its original path" behavior as intentional.
**Implementation strategy:** Add a guard in `update_personnel`: if `is_manager` is changing and an open `EvaluationRecord` exists for the personnel, raise `400` with a clear message ("finish or cancel the open evaluation before changing this flag"). Add a regression test.

### 2.4 No soft-delete / archival path for `Personnel` and `User`
**Issue:** There is `is_active`/`status` for personnel and users (good — no hard deletes), but there is no way to fully offboard a user/personnel record (e.g., GDPR-style "right to erasure" for a departed non-evaluated contractor) beyond marking inactive; all historical FKs point to hard row IDs with no anonymization path.
**Why it's a problem:** For organizations subject to data-protection regulation, "deactivate" isn't equivalent to "erase," and there is currently no supported way to actually remove/anonymize a person's PII on request while preserving the *shape* of historical audit/evaluation data (which often has independent legal retention requirements).
**Best professional solution:** Add an explicit anonymization routine that nulls/scrambles PII fields (name, username) on request while retaining the row and its foreign-key relationships (so historical evaluations/audit logs remain structurally valid), rather than deleting rows outright.
**Implementation strategy:** Add an HR-only `POST /api/personnel/{id}/anonymize` (and equivalent for users) that overwrites `full_name`→"Former Employee #<id>", clears any free-text fields, and logs the action distinctly in the audit log as `pii_erasure_requested`.

### 2.5 `EvaluationRecord.subject` uses `lazy="joined"`; other relationships don't — inconsistent eager-loading policy
**Issue:** `subject` on `EvaluationRecord` and `commenter` on `EvaluationComment` are eagerly joined (to avoid N+1), but `scores` and `comments` collections on `EvaluationRecord` are default lazy-loaded, and callers (e.g., `get_evaluation`) rely on FastAPI's `response_model` serialization triggering lazy loads inside the request (works, but each nested list becomes its own round trip in a sync session).
**Why it's a problem:** For the detail endpoint returning one full evaluation this is a handful of extra small queries — fine at current scale — but it's an inconsistent pattern that will bite harder once `list_evaluations` (or a future "export all" feature) tries to include nested details across many rows, reintroducing N+1 in exactly the place the code comments say N+1 was already fixed once (`dashboard.py`'s comment about the *previous* N+1 problem shows the team is aware of this class of bug).
**Best professional solution:** Standardize eager-loading strategy: use `selectinload()` explicitly at the query site for collections that are always needed by a given endpoint, rather than relying on relationship-level `lazy="joined"` for singular objects only.
**Implementation strategy:** Audit each endpoint that serializes nested collections (`get_evaluation`, `export_evaluations_excel`) and add explicit `.options(selectinload(EvaluationRecord.scores), selectinload(EvaluationRecord.comments))` where those are always rendered, with a code comment explaining why (mirroring the existing documentation style in the codebase).

### 2.6 Single monolithic `evaluations.py` router (520 lines) mixes many responsibilities
**Issue:** One router file handles CRUD, all four workflow transitions, comments, scores, Excel export, and PDF export.
**Why it's a problem:** Not a bug, but a maintainability concern: as more workflow variants are added (the "manager path" special-casing already adds meaningful branching), this file will keep growing and become a hotspot for merge conflicts and cognitive load.
**Best professional solution:** Split by concern once it grows past ~300–400 lines: `evaluations_crud.py`, `evaluations_workflow.py`, `evaluations_comments.py`, `evaluations_export.py`, all mounted under the same `/api/evaluations` prefix.
**Implementation strategy:** Straightforward mechanical refactor; no behavior change. Do this alongside a test-suite run to confirm route registration order/behavior is unaffected.

### 2.7 `deps.py` hits the database on every authenticated request with no short-lived cache
**Issue:** `get_current_user` does `db.get(User, ...)` on every request to check `is_active`/`token_version`.
**Why it's a problem:** This is the *correct* choice for revocation correctness (a cached user object would delay logout-everywhere semantics), so this is not really a "fix it" item — but it does mean auth is a full round trip to Postgres per request, which matters once traffic grows.
**Best professional solution:** Keep correctness as the default, but add a short (e.g., 5–10 second) in-process or Redis-backed cache keyed by `(user_id, token_version)` so bursts of requests from the same user in the same second don't each hit Postgres, while still capping staleness to a few seconds — an acceptable tradeoff for a low-traffic internal HR tool that may see spikes at evaluation-period deadlines.
**Implementation strategy:** Wrap the `db.get(User, ...)` call with an LRU/TTL cache (e.g., `cachetools.TTLCache`) invalidated on `token_version` bump (password change/logout-everywhere already increments it, so cache entries naturally go stale correctly at the exact moment they should).

---

## 3. Data Model & Database

### 3.1 No explicit database indexes shown beyond primary/unique keys for high-traffic filter columns
**Issue:** Looking at query patterns (`evaluations.py`, `dashboard.py`), the code filters/joins frequently on `EvaluationRecord.status`, `EvaluationRecord.unit_supervisor_user_id` / `deputy_user_id` / `ceo_user_id`, `EvaluationRecord.subject_personnel_id`, and `Notification.user_id` + `dedup_key` + `created_at`. Without inspecting the Alembic migration bodies in full detail, these are the columns most likely to need composite indexes, and it's worth an explicit `EXPLAIN ANALYZE` pass before production scale.
**Why it's a problem:** As the organization's evaluation history grows (multi-year), sequential scans on these filters will slow list/dashboard endpoints noticeably, especially `list_evaluations` (role-based filters) and the dashboard aggregate queries.
**Best professional solution:** Add composite indexes matching actual query predicates, verified with `EXPLAIN ANALYZE` on realistic data volumes (e.g., 5 years × several hundred employees × quarterly cycles).
**Implementation strategy:**
- `CREATE INDEX ix_eval_records_status ON evaluation_records(status);`
- `CREATE INDEX ix_eval_records_supervisor ON evaluation_records(unit_supervisor_user_id) WHERE unit_supervisor_user_id IS NOT NULL;` (same for deputy/ceo)
- `CREATE INDEX ix_notification_user_created ON notifications(user_id, created_at DESC);`
- `CREATE INDEX ix_notification_dedup ON notifications(user_id, dedup_key, created_at);`
- Add these as a new Alembic revision; measure before/after with `EXPLAIN (ANALYZE, BUFFERS)`.

### 3.2 `final_snapshot` (JSONB) duplicates data already in normalized tables
**Issue:** At finalization, `build_final_snapshot` freezes a full JSON copy of the evaluation (scores, comments, personnel info) into `EvaluationRecord.final_snapshot`, which is the right call for legal/PDF stability — but there is no documented reconciliation process if the normalized source data (e.g., `Personnel.full_name` changes after finalization due to a typo fix) diverges from the frozen snapshot.
**Why it's a problem:** Two sources of truth for "what was this person's name at evaluation time" can silently diverge with no alert. This is an intentional design tradeoff (byte-stable legal PDFs), but it's undocumented *why* the two can differ and *that* they're allowed to.
**Best professional solution:** Document this explicitly in a code comment/README section: "the snapshot is the legal record; live tables reflect the current state and may differ after finalization." Add a small admin utility that can diff live vs. snapshot data for spot-checking data quality.
**Implementation strategy:** Add a `GET /api/evaluations/{id}/snapshot-diff` (HR-only, read-only) that flags any live/snapshot mismatch for the given record, useful for data-quality audits.

### 3.3 No database-level check that `deputy_user_id`/`ceo_user_id` actually hold the `deputy`/`ceo` role
**Issue:** Role correctness for `EvaluationAccess` is enforced at the API layer (`_ensure_active_user_with_role`), but the foreign keys themselves don't constrain role — a direct DB write (migration, manual fix, future bulk-import script) could assign a `unit_supervisor`-role user as `ceo_user_id` with nothing catching it at the database level.
**Why it's a problem:** Defense-in-depth: application-layer-only invariants are one bad migration or admin script away from producing "stuck" evaluations that can never be approved (exactly the failure mode the code comment in `evaluation_access.py` already worries about).
**Best professional solution:** This is hard to express as a plain SQL `CHECK` constraint (would need a trigger, since it spans two tables), so the pragmatic answer is a **periodic integrity-check job** rather than a hard DB constraint.
**Implementation strategy:** Add a scheduled/admin-triggerable "data integrity sweep" that verifies every `EvaluationAccess`/`EvaluationRecord` assignee still has the expected role and `is_active=True`, and notifies HR of any drift (reusing the `run_all_sweeps` pattern).

### 3.4 Numeric percentages stored as `Numeric(5,2)` but Python floats used in computation
**Issue:** `compute_result` in `evaluation.py` does floating-point division/rounding (`round((general_sum / general_max) * 100, 1)`) before persisting into `Numeric(5,2)` columns.
**Why it's a problem:** Mixing Python `float` arithmetic with a `Numeric` (arbitrary precision) column type risks subtle rounding mismatches between what's computed and what's ultimately stored/compared (e.g., threshold comparisons in `recommendation_for` operate on the pre-persistence float, not the post-round-trip `Decimal`). At today's scale of "1–5 integer scores averaged," this is very unlikely to ever produce a wrong recommendation, but it's fragile: a future change to allow half-point scores (2.5, 4.5) would make this a real correctness risk.
**Best professional solution:** Use `Decimal` consistently for any monetary/score-threshold-sensitive computation, or explicitly document that scores are integers 1–5 and thus this is safe *only* under that constraint.
**Implementation strategy:** Add an inline comment in `constants.py`/`evaluation.py` stating the integer-score assumption explicitly, and add a unit test that would fail if someone widens `EvaluationScore.score` to allow decimals without revisiting the rounding logic.

---

## 4. API Design

### 4.1 Inconsistent error payload shapes
**Issue:** Most `HTTPException` calls use `detail: str`, but the "open evaluation exists" conflict (`create_evaluation`) uses `detail: {"message": ..., "evaluation_id": ...}` — a structured object. The frontend's `extractErrorMessage`/`extractConflictEvaluationId` helpers already have to special-case this.
**Why it's a problem:** Every new "structured error" case forces another bespoke frontend helper and another `isinstance`-style check; there's no single conventions doc for "when is `detail` a string vs. an object," so the next contributor will likely guess wrong.
**Best professional solution:** Adopt a single, consistent error envelope for the whole API (e.g., `{"detail": "...", "code": "EVALUATION_ALREADY_OPEN", "meta": {"evaluation_id": 42}}`), documented once, used everywhere.
**Implementation strategy:** Introduce a small `AppError` exception class wrapping `HTTPException` with a mandatory `code` and optional `meta`; add a global exception handler that normalizes the envelope; migrate existing raises incrementally (non-breaking since `detail` as a string still works for simple cases).

### 4.2 No API versioning strategy
**Issue:** All routes are under `/api/...` with no version segment (`/api/v1/...`).
**Why it's a problem:** Any breaking change to a response shape in the future (e.g., renaming `stage` after the noted removal of the `stage` column) has no clean migration path for external consumers (mobile app, integrations, Excel macros hitting the API directly) without a version bump.
**Best professional solution:** Introduce `/api/v1` now, while there's only one consumer (the bundled frontend), so the pattern is established before it's painful to add.
**Implementation strategy:** Mount all routers under a shared `/api/v1` prefix (a one-line change to each router's `prefix=`, or a parent `APIRouter(prefix="/api/v1")` that includes the sub-routers); update the frontend `baseURL` accordingly; keep `/api/health` unversioned as an infra-level endpoint.

### 4.3 No OpenAPI examples / rich descriptions on most endpoints
**Issue:** Docstrings exist (in Persian) for many endpoints, explaining *why* a design choice was made, which is excellent for maintainers, but few endpoints use FastAPI's `responses=`/`Field(..., examples=[...])` to enrich the actual OpenAPI/Swagger schema for API consumers.
**Why it's a problem:** `/docs` (enabled outside production) is the primary "living documentation" for any future integration work, but currently reads more like internal engineering commentary than consumer-facing API docs.
**Best professional solution:** Add `summary=`, `description=`, and response examples to the most-used endpoints (auth, evaluations CRUD/workflow), keeping the existing Persian internal comments as-is (they're valuable) but adding consumer-facing English/Persian summaries too.
**Implementation strategy:** Incremental — start with `auth.py` and `evaluations.py` since those are the highest-traffic/most-integrated surfaces.

### 4.4 No idempotency keys on state-mutating workflow endpoints
**Issue:** `submit`, `hr-approve`, `deputy-approve`, `ceo-finalize` etc. are POSTs with no idempotency-key support. A double-click or a client retry after a network blip (axios interceptor auto-retries on 401 already; a similar pattern could plausibly retry on timeout) could, in theory, attempt the same transition twice.
**Why it's a problem:** The workflow state machine's `ensure_transition_allowed` check (comparing `record.status != spec.from_status`) *does* make a true double-submit safe today (second call will 4xx because status already changed) — this is good — but a **duplicate PDF archival or duplicate notification** could still occur in a narrow race if two requests both pass the status check before either commits (see §4.5).
**Best professional solution:** Combine the existing status-based idempotency with a `SELECT ... FOR UPDATE` (row lock) on the evaluation record for all workflow transitions, closing the race window entirely rather than relying on optimistic status comparison.
**Implementation strategy:** In `_get_record_or_404`/`apply_transition`, use `db.execute(select(EvaluationRecord).where(...).with_for_update())` for the workflow endpoints specifically (not the read-only ones), so two concurrent transition requests serialize instead of racing.

### 4.5 Concurrent workflow transitions: narrow race window
**Issue:** Following on from 4.4 — `apply_transition` reads `record.status`, does business logic, then writes `record.status = spec.to_status` and commits, all without a row lock. Two simultaneous requests for the *same* transition (e.g., double-click "Approve") could both pass `ensure_transition_allowed` before either commits, particularly under Postgres's default `READ COMMITTED` isolation.
**Why it's a problem:** Worst case, this could produce two audit log entries and (more importantly) two notification bursts, or in the CEO-finalize case, a duplicate attempt to write `EvaluationDocument` — though `archive_final_pdf` does check `existing = get_document(...)` first, so the actual PDF is protected by that idempotency check specifically. The other create_evaluation path *does* correctly use a partial unique index + `IntegrityError` handling as its concurrency guard — that pattern should be extended to workflow transitions too, for consistency.
**Best professional solution:** As in 4.4, add `SELECT ... FOR UPDATE` around the read-modify-write in `apply_transition`.
**Implementation strategy:** Same as 4.4; add a regression test using two threads/sessions hitting the same transition concurrently (mirroring the existing `test_workflow.py` style) to confirm only one succeeds and one gets a clean 4xx.

---

## 5. Frontend Architecture & Code Quality

### 5.1 No global React error boundary
**Issue:** `main.tsx` wraps the app in `StrictMode` → `BrowserRouter` → `QueryClientProvider` → `ToastProvider` → `ConfirmProvider` → `AuthProvider` → `App`, but there is no `<ErrorBoundary>` anywhere in the tree.
**Why it's a problem:** Any uncaught render-time exception in any page (a null-dereference from unexpected API data, a bug in a new feature) currently blows away the *entire* React tree to a blank white screen with no user-facing message and no recovery action — a much worse failure mode than the app's otherwise careful error handling (Toasts, `extractErrorMessage`, loading skeletons) would suggest.
**Best professional solution:** Add a top-level error boundary with a friendly "something went wrong, please refresh" screen and a "report" affordance, plus route-level boundaries around the riskiest pages (PDF/Excel export triggers, dashboard charts) so one broken widget doesn't take down the whole page.
**Implementation strategy:** Add an `ErrorBoundary` component (class component, since React error boundaries still require a class) wrapping `<Outlet />` in `Layout.tsx` and another wrapping the whole `<App />` in `main.tsx` as a last-resort catch-all; wire it to whatever error-tracking service is adopted (see §11).

### 5.2 No code-splitting / lazy loading of routes
**Issue:** `App.tsx` statically imports every page component (18+ pages including HR admin pages, dashboards with Recharts, PDF/Excel triggers) at the top of the file, so the initial JS bundle includes code that 4 of 5 roles (`employee`, `unit_supervisor`, `deputy`, `ceo`) will never execute (all the HR-only admin pages).
**Why it's a problem:** Every user — including a `unit_supervisor` on a slow connection who only ever sees one page — downloads and parses the HR dashboard's Recharts-heavy bundle, the audit log page, indicators management, etc. This directly increases time-to-interactive for the majority of users.
**Best professional solution:** Route-based code splitting with `React.lazy` + `Suspense`, especially for the entire `hr/*` subtree and the Recharts-dependent `DashboardPage`.
**Implementation strategy:**
```tsx
const DashboardPage = lazy(() => import("./pages/hr/DashboardPage"));
// ...
<Route path="/hr/dashboard" element={<Suspense fallback={<PageSkeleton />}><DashboardPage /></Suspense>} />
```
Apply consistently to all `hr/*`, `supervisor/*`, `deputy/*`, `ceo/*`, `employee/*` routes; measure bundle-size impact with `vite-bundle-visualizer` before/after.

### 5.3 No internationalization (i18n) layer
**Issue:** All UI strings are hardcoded Persian literals directly inside JSX (e.g., `NAV_BY_ROLE`, `SCORE_LABELS`, every error message). There is no `react-i18next`/`FormatJS` or equivalent, and no separation between UI copy and code.
**Why it's a problem:** This is a reasonable initial choice for a single-locale internal tool, but it means: (a) any future requirement to support English (for a multinational parent company, an auditor, or an international investor doing due diligence) requires touching nearly every component; (b) copy changes require a developer and a full redeploy instead of a translator editing a resource file; (c) there's no single place to audit all user-facing strings for tone/consistency.
**Best professional solution:** Extract all strings into locale resource files now, even while shipping only `fa-IR`, so the *architecture* supports a second locale without a rewrite.
**Implementation strategy:** Introduce `react-i18next` (or a lighter custom `useTranslation` hook backed by JSON files) with `fa.json` as the only locale initially; migrate incrementally, starting with the highest-value shared strings (`SCORE_LABELS`, status/role labels, validation messages), then page by page.

### 5.4 No end-to-end (E2E) test coverage
**Issue:** There are solid unit tests (Vitest + Testing Library on the frontend, pytest with 100 test functions on the backend), but nothing exercises the full stack together (e.g., Playwright/Cypress simulating "supervisor logs in → scores an evaluation → HR approves → CEO finalizes → PDF downloads").
**Why it's a problem:** The most valuable and most fragile part of this product *is* the four-stage workflow spanning both frontend and backend; unit tests on each side independently can't catch integration regressions (e.g., a frontend field name drifting from a backend schema field, or a routing/permission mismatch that only manifests when a real browser session navigates the actual app).
**Best professional solution:** Add a thin E2E suite covering the "happy path" workflow end-to-end plus the "manager path" special case, run against a real (test) Postgres and real backend in CI.
**Implementation strategy:** Add Playwright, seed a test database (reusing the existing seed-data pattern from the README's sample users), write 2–3 critical-path specs, and add a `frontend-e2e` job to `.github/workflows/ci.yml` that spins up backend + Postgres via `docker compose` before running Playwright against the built frontend.

### 5.5 No visual regression / accessibility automation in CI
**Issue:** CI runs `oxlint`, unit tests, and a production build for the frontend, and `ruff` + `pytest` for the backend — good baseline — but there's no automated accessibility audit (e.g., `axe-core`) or visual regression tooling (e.g., Percy/Chromatic) gating merges.
**Why it's a problem:** Accessibility regressions (see §7) and unintended visual changes currently rely entirely on manual review.
**Best professional solution:** Add `@axe-core/playwright` assertions to the new E2E suite (§5.4) and, optionally, a lightweight visual-diff step for key pages.
**Implementation strategy:** `expect(await new AxeBuilder({ page }).analyze()).toHaveNoViolations()` in each Playwright spec's final step, wired into the same CI job.

### 5.6 Toast/Confirm/Modal providers are good, but no unified async-action pattern
**Issue:** Each page (e.g., `EvaluationDetailPage`) manages its own `busy`/`error` `useState` around API calls (`setBusy(true); try {...} catch { showError(...) } finally { setBusy(false) }`), repeated across many pages rather than centralized in a shared hook.
**Why it's a problem:** This is boilerplate duplication rather than a bug — each page reinvents the same "in-flight + error" plumbing, which is exactly what React Query's `useMutation` already exists to solve, and the codebase already uses `@tanstack/react-query` for reads (`useEvaluationDetail` etc.) but apparently not consistently for writes (workflow actions call `apiClient` directly with manual `busy` state instead of `useMutation`).
**Why it matters for maintainability:** Any cross-cutting improvement (e.g., "automatically invalidate the evaluations list after any mutation," "show a consistent loading spinner style") currently has to be applied page-by-page instead of once.
**Best professional solution:** Standardize all write operations through `useMutation`, with `onSuccess` invalidating the relevant query keys and `onError` routed through the shared `useToast`.
**Implementation strategy:** Introduce a small `useApiMutation` wrapper around `useMutation` that automatically calls `extractErrorMessage` and `showError` on failure, and migrate the workflow-action call sites (`submit_evaluation`, `hr_approve`, etc. from the frontend side) to use it, removing the manual `busy`/`error` state from each page.

---

## 6. UI / UX

### 6.1 No autosave for in-progress evidence/score drafts
**Issue:** `ScoreForm`/`useScoreForm` keeps all draft scores/evidence text in local React state; there is a `PUT /{id}/scores` "draft save" endpoint (`scores_draft_saved` audit event), but nothing in the reviewed pages appears to call it automatically on an interval/debounce — it looks like it's invoked on an explicit "save" action tied to page navigation or a button, not continuously.
**Why it's a problem:** A supervisor who spends 20 minutes writing detailed 15+ word evidence for a dozen indicators and then has their laptop sleep, browser crash, or accidentally navigate away loses all unsaved work — an outsized cost for what should be a low-risk, frequent action, and precisely the kind of moment that damages user trust in the tool.
**Best professional solution:** Add debounced autosave (e.g., every 5–10 seconds of inactivity, or on blur of each textarea) calling the existing draft-save endpoint, with a small "Saved ✓ / Saving…" indicator near the form.
**Implementation strategy:** Wrap the existing `useDebouncedValue` hook (already present in `api/queries.ts`) around the `drafts` state, and fire the existing scores PUT endpoint on change; add a `beforeunload` warning if there are unsaved changes newer than the last successful save.

### 6.2 No "unsaved changes" navigation guard
**Issue:** Related to 6.1 — there's no `beforeunload`/router-blocking guard when a user has typed evidence text and tries to navigate away or close the tab.
**Why it's a problem:** Same root cause as 6.1 — silent data loss with no warning.
**Best professional solution:** Standard `window.onbeforeunload` + React Router's `useBlocker` (v7 supports this) when `isDirty` is true.
**Implementation strategy:** Track a simple `isDirty` boolean in the score-form hook (`drafts !== lastSavedDrafts`), wire both guards to it.

### 6.3 Modal has no focus trap or focus restoration
**Issue:** `ui/Modal.tsx` correctly sets `role="dialog"`, `aria-modal="true"`, and closes on Escape/backdrop click, and locks body scroll — genuinely good baseline work — but it does not (a) move focus into the modal when it opens, (b) trap Tab/Shift+Tab focus inside the modal while open, or (c) restore focus to the triggering element on close.
**Why it's a problem:** A keyboard or screen-reader user opening a modal keeps their focus on (and can keep Tab-ing through) the page behind the modal, which is both confusing and a WCAG 2.1 (2.4.3 Focus Order, 2.1.2 No Keyboard Trap equivalent expectation for dialogs) violation. This affects every confirm dialog and every data-entry modal in the app.
**Best professional solution:** Implement a standard focus-trap pattern: on mount, save `document.activeElement`, move focus to the modal (first focusable element or the dialog container itself via `tabIndex={-1}`), trap Tab within the modal's focusable elements, and on unmount restore focus to the saved element.
**Implementation strategy:** Either hand-roll ~30 lines of focus-trap logic in `Modal.tsx` (save/restore `activeElement`, a `keydown` handler cycling focus between first/last focusable child), or adopt a small dependency like `focus-trap-react`. Given how central this component is (used by every dialog/confirm in the app), fixing it once here fixes it everywhere.

### 6.4 Notification bell / async data has no explicit "empty state" pass reviewed for tone
**Issue:** Not fully verifiable without running the app, but worth a deliberate design pass: ensure every list/table (personnel, users, evaluations, audit log, notifications) has a considered empty state (icon + helpful copy + a clear next action), not just a blank table — this is the kind of polish that's easy to skip under deadline pressure and easy to miss in a code-only review.
**Why it's a problem:** A blank table with no explanation ("is this broken, or is there really nothing here?") is a common source of support tickets and user confusion, especially for a first-time HR user setting up personnel before any evaluations exist.
**Best professional solution:** Standardize an `<EmptyState icon title description action />` component and audit every list page to use it.
**Implementation strategy:** Create the shared component in `ui/`, then do a page-by-page pass (`PersonnelPage`, `UsersPage`, `QueuePage`, `AuditLogPage`, `NotificationBell` dropdown, dashboards before data exists) to ensure each has a considered zero-state.

### 6.5 No bulk actions for HR-heavy workflows
**Issue:** HR is the busiest role (approves every evaluation, manages all personnel/users/indicators), yet every reviewed action (approve, return, comment) appears to operate on a single evaluation at a time via its own detail page.
**Why it's a problem:** During evaluation season (the whole point of this product — pre-renewal review cycles), HR may need to approve dozens of straightforward, already-well-scored evaluations in a short window; a one-by-one detail-page flow is a real productivity tax for the primary power user of the system.
**Best professional solution:** Add a bulk-approve action from the HR queue list (`QueuePage`) for evaluations that meet a "no evidence violations, no flags" fast-path, with a clear confirmation summary before committing, while still requiring individual review/comment for anything unusual.
**Implementation strategy:** Add a multi-select column + "Approve selected" button to `QueuePage`, backed by a new `POST /api/evaluations/bulk-hr-approve` endpoint that loops the existing single-record transition logic (reusing `apply_transition` under one DB transaction, so it's all-or-nothing per batch) and returns a per-item success/failure summary for the UI to render.

### 6.6 No keyboard shortcuts for the primary review workflow
**Issue:** Approving/returning/commenting on evaluations is entirely mouse-driven.
**Why it's a problem:** For power users doing many approvals in a row, keyboard shortcuts (e.g., `A` to approve, `R` to open the return dialog, `[`/`]` to move between queue items) meaningfully speed up repetitive review work — a common expectation in modern review-heavy tools (email triage, code review, ticket queues).
**Best professional solution:** Add an opt-in keyboard-shortcut layer on the review/detail pages with a visible "?" help overlay listing shortcuts.
**Implementation strategy:** A small custom hook (`useHotkeys` — either hand-rolled or via a lightweight library) scoped to the evaluation detail page, disabled while any text input/textarea has focus (to avoid conflicting with evidence typing).

---

## 7. Accessibility

### 7.1 Modal focus trap — see §6.3 (cross-referenced here as it's also an accessibility, not just UX, defect).

### 7.2 Color as the sole differentiator in some score displays
**Issue:** `ScoreForm.tsx`'s `SELECTED_TONE`/`READONLY_TONE` maps do pair color with text labels (`SCORE_LABELS`) and numerals, which is good practice — but other places in the app (status badges, dashboard "lowest performers" lists, chart colors in Recharts widgets) should be audited to confirm every colored indicator also carries a text/pattern cue, not color alone, for colorblind users (a meaningfully large fraction of any large workforce).
**Why it's a problem:** Deuteranopia/protanopia (red-green colorblindness) affects roughly 1 in 12 men; a red/amber/green performance-status system that relies purely on hue for meaning is not accessible to that population, which matters more than usual here because this data affects real employment decisions.
**Best professional solution:** Audit every use of semantic color (`StatusBadge`, chart legends, dashboard "lowest N" lists) to confirm a text label or icon always accompanies the color.
**Implementation strategy:** A focused accessibility pass over `StatusBadge.tsx`, `Meters.tsx`, and the Recharts configurations in `DashboardPage.tsx`, adding icons/patterns/labels wherever color is currently the only signal; verify with a colorblindness simulator (e.g., browser dev tools' vision-deficiency emulation).

### 7.3 No skip-to-content link
**Issue:** `Layout.tsx`'s header has a two-row nav (brand/user menu, then role-based nav links) before `<main>`; there's no "skip to main content" link for keyboard/screen-reader users.
**Why it's a problem:** Keyboard users must Tab through the entire header (brand link, notification bell, change-password icon, logout button, then every nav link) on *every single page* before reaching page content — a significant, avoidable friction for a role like `unit_supervisor` who might navigate between many evaluations in a session.
**Best professional solution:** Add a visually-hidden-until-focused "skip to content" link as the very first focusable element.
**Implementation strategy:** `<a href="#main-content" className="sr-only focus:not-sr-only ...">پرش به محتوای اصلی</a>` as the first child of the layout, with `id="main-content"` added to the `<main>` element.

### 7.4 Chart accessibility (Recharts) likely needs supplementary text/table alternatives
**Issue:** The dashboard uses Recharts for radar/trend/bar visualizations. Recharts renders SVG with limited built-in screen-reader support; without explicit `aria-label`/`role="img"` + a text summary or an accompanying data table, these charts are effectively invisible to screen-reader users.
**Why it's a problem:** HR's analytical dashboard — arguably one of the most valuable features for decision-making — would be unusable non-visually as currently likely configured.
**Best professional solution:** Pair every chart with either a visually-hidden data table (same data, `<table>` markup) or a concise auto-generated text summary ("Average final score across 8 org units ranges from 61% to 88%; Sales is lowest at 61%.").
**Implementation strategy:** Add a `<VisuallyHiddenDataTable data={...} />` companion component rendered alongside each chart in `DashboardPage.tsx`, and add `role="img" aria-label="..."` to the chart container summarizing its content.

### 7.5 RTL + bidirectional content edge cases
**Issue:** The app is properly RTL (`dir` handling visible in `Brand.tsx`'s `dir="ltr"` wrapper for the app name), which is good attention to detail — but user-entered evidence text or personnel names could contain Latin-script substrings (e.g., an English job title, an email address in a comment) that need explicit `dir="auto"` or Unicode bidi isolation (`<bdi>`) to render correctly inside an RTL page; this should be verified across all free-text render sites (evidence text, comments, personnel names/job titles).
**Why it's a problem:** Mixed-direction text without proper isolation can visually scramble punctuation/number ordering (a classic RTL bug), degrading readability of exactly the free-text evidence that evaluators are legally required to write carefully.
**Best professional solution:** Wrap all free-text user content in `<bdi>` (bidirectional isolation) rather than relying on the page's ambient `dir`.
**Implementation strategy:** Audit `ScoreFormTable`'s evidence display, `EvaluationComment` rendering, and `Personnel.full_name`/`job_title` render sites; wrap dynamic user content in `<bdi>{value}</bdi>`.

---

## 8. Performance & Scalability

### 8.1 In-process scheduler doesn't support horizontal scaling
**Issue:** `enable_scheduler` in `config.py` and the accompanying comment in `.env.example` explicitly acknowledge: *"for single-instance deployment enable this; for multi-instance, migrate later to a shared worker"* — the team is already aware of this limitation.
**Why it's a problem:** If the backend is ever scaled to N replicas with the scheduler enabled on all of them, every sweep (`run_all_sweeps`) runs N times redundantly — wasted work at best, and duplicate-but-deduped notifications (protected by `notify_once`, so not actually broken, just wasteful) at worst.
**Best professional solution:** Move scheduled sweeps to a dedicated worker process/queue (Celery beat, APScheduler with a distributed lock, or a simple Postgres-advisory-lock-guarded cron) decoupled from the web-serving replicas.
**Implementation strategy:** Introduce a lightweight `worker` service in `docker-compose.yml` that runs only the scheduler loop (reusing the existing `run_all_sweeps`), guarded by a Postgres advisory lock (`pg_try_advisory_lock`) so even if misconfigured to run on multiple nodes, only one actually executes at a time; disable `enable_scheduler` in the main web service entirely once this exists.

### 8.2 No caching layer for expensive/rarely-changing reads
**Issue:** `GET /api/config` is fetched once per session with `staleTime: Infinity` on the frontend (good), but on the backend it's recomputed from constants on every call with no HTTP caching headers (`Cache-Control`/`ETag`); similarly, `active_indicators_by_id` re-queries the (rarely changing) indicators table on every scores-related request.
**Why it's a problem:** Minor at current scale, but an easy, essentially free win.
**Best professional solution:** Add `Cache-Control: private, max-age=300` (or similar) to `/api/config` and `/api/indicators`, and/or an in-process TTL cache for `active_indicators_by_id` given indicators change extremely rarely (HR-managed reference data).
**Implementation strategy:** FastAPI `Response` header injection on those two endpoints; a `cachetools.TTLCache(maxsize=1, ttl=60)` wrapper around indicator lookups used inside scoring/workflow code paths.

### 8.3 Dashboard aggregate queries recompute from scratch on every request
**Issue:** `DashboardOverview` runs ~5 separate aggregate queries (org unit averages, evaluator averages, lowest-N indicators, lowest-N units, lowest-N people) with no caching, on every request to `/api/dashboard/overview`.
**Why it's a problem:** These are OLAP-style aggregations over the full evaluation history; as history grows into years of data across hundreds/thousands of employees, this endpoint will slow down, especially since it's likely opened frequently by HR (a natural "landing page" habit).
**Best professional solution:** Cache the computed overview for a short TTL (a few minutes is plenty for a dashboard that summarizes slow-moving HR data) and/or precompute it via the existing scheduled-sweep mechanism into a small summary table refreshed periodically.
**Implementation strategy:** Simplest: wrap the endpoint body in a Redis-backed cache keyed by nothing (single global dashboard) with a 5-minute TTL, invalidated (or just left to expire) on `ceo_finalize`. More robust: materialize into a `dashboard_summary` table updated by a scheduled sweep, making the endpoint a cheap read of pre-computed rows.

### 8.4 No pagination cursor strategy for large lists — offset/limit will degrade
**Issue:** `list_evaluations`, `list_personnel`, `list_users` all use classic `LIMIT/OFFSET` pagination.
**Why it's a problem:** Offset pagination gets linearly slower as `offset` grows (Postgres still has to scan and discard the skipped rows) and is prone to "shifting page" bugs if new rows are inserted between page loads. At this app's realistic scale (hundreds to low thousands of personnel/evaluations) this is not urgent, but worth flagging before the organization's evaluation history spans many years.
**Best professional solution:** Move to keyset (cursor-based) pagination — `WHERE created_at < :last_seen ORDER BY created_at DESC LIMIT :n` — for the highest-traffic lists once row counts justify it.
**Implementation strategy:** Not urgent; revisit once any list exceeds ~10k rows. Document the threshold in a `PERFORMANCE_NOTES.md` so it isn't forgotten.

### 8.5 PDF generation is synchronous and blocks the request/worker
**Issue:** `render_evaluation_summary_pdf` (WeasyPrint) runs synchronously inside the `ceo_finalize` and `evaluation_summary_pdf` request handlers.
**Why it's a problem:** WeasyPrint PDF rendering (especially with embedded fonts/QR images) is CPU-bound and can take a noticeable fraction of a second to a few seconds; running it inline in a sync FastAPI request handler blocks that worker thread/process for the duration, and if many CEO-finalize actions cluster near a deadline, this could visibly slow the whole API for other users sharing the same worker pool.
**Why it's already partially mitigated:** The idempotent "archive once" design means this cost is paid at most once per evaluation (subsequent downloads serve the cached bytes) — a genuinely good mitigation already in place.
**Best professional solution:** For the *first* generation, either run it in a background thread pool (FastAPI's `run_in_threadpool`, since WeasyPrint isn't async-native) so it doesn't block the event loop, or move PDF generation to an async task queue (Celery/RQ) with the API returning "processing" and the frontend polling/subscribing for completion.
**Implementation strategy:** Simplest immediate fix: wrap the WeasyPrint call in `run_in_threadpool(render_evaluation_summary_pdf, ...)` inside `archive_final_pdf`. Longer-term: move to a task queue if evaluation volume grows enough that clustering becomes a real observed problem (don't over-engineer prematurely; this is a "watch and revisit" item, not a "fix now" item).

---

## 9. Testing & QA

### 9.1 Strong backend unit/integration coverage; frontend coverage is comparatively thin
**Issue:** Backend has 100 test functions across 19 files covering RBAC, workflow, sessions, rate limiting, evidence validation, PDF security, notifications, scheduled jobs — genuinely comprehensive. The frontend has only a handful of test files (`ScoreForm.test.tsx`, `ui.test.tsx`, `client.test.ts`) covering a small fraction of the ~40+ components/pages.
**Why it's a problem:** The frontend carries substantial business logic (client-side score preview computation mirroring the server formula, evidence word-count validation, role-based route/UI gating) that currently has much thinner regression protection than its backend counterpart.
**Best professional solution:** Prioritize tests for: (a) `computePreview`'s parity with the backend formula (a drift here would show users an incorrect preview), (b) role-based conditional rendering in `EvaluationDetailPage` (the `isSupervisorDraft`/`canHrApprove`/etc. boolean logic is exactly the kind of "many similar-looking conditions" code that silently breaks when one branch is edited), (c) the `AuthContext` refresh-token-recovery flow.
**Implementation strategy:** Add Testing-Library tests asserting that for each `(role, status, assignee)` combination, the correct action buttons render — table-driven tests mapping directly onto the existing `TRANSITIONS` dict on the backend, so the two suites stay conceptually in sync.

### 9.2 No mutation testing / coverage-threshold enforcement in CI
**Issue:** CI runs `pytest -v` and `vitest run` but does not report or enforce a minimum coverage percentage, nor run mutation testing to check whether the existing tests actually catch introduced bugs.
**Why it's a problem:** Test *count* (100 functions) doesn't guarantee test *effectiveness*; without a coverage gate, coverage can silently erode as new code is added without matching tests.
**Best professional solution:** Add `pytest-cov`/`vitest --coverage` with an enforced minimum threshold (e.g., 80% lines) that fails CI if breached, focused especially on `app/services/` and `app/api/routers/` (business logic) rather than boilerplate.
**Implementation strategy:** Add `--cov=app --cov-fail-under=80` to the CI `pytest` step; add `coverage: { thresholds: { lines: 75 } }` to `vitest.config.ts`.

### 9.3 No load/stress testing artifacts
**Issue:** No `locust`/`k6`/`artillery` scripts exist to validate behavior under concurrent load (e.g., the evaluation-period rush when many supervisors submit simultaneously).
**Why it's a problem:** Several of the concurrency findings above (§4.5, §8.3) are exactly the kind of issue that only surfaces under real concurrent load; without a load-testing harness, the team is flying blind on how the system behaves at, say, 50 concurrent users all submitting evaluations in the last hour before a deadline (a very plausible real-world usage spike for this specific product).
**Best professional solution:** Add a small `k6` script simulating a realistic "deadline day" burst (N supervisors logging in and submitting, M HR staff approving) against a staging environment.
**Implementation strategy:** Add `load-tests/deadline_day.js` (k6), run manually before major releases or the first real evaluation cycle in production; not necessarily gating every CI run.

---

## 10. DevOps / CI / Deployment

### 10.1 CI doesn't build/push a versioned Docker image or scan it
**Issue:** `.github/workflows/ci.yml` runs lint/test/build for both backend and frontend but does not build the actual Docker images defined in `backend/Dockerfile`/`frontend/Dockerfile`, nor scan them for vulnerabilities, nor publish artifacts.
**Why it's a problem:** "Tests pass" and "the Docker image that will actually run in production builds cleanly and is free of known CVEs in its base image/dependencies" are two different guarantees; today only the first is checked in CI.
**Best professional solution:** Add a CI job that builds both Docker images on every PR (catching Dockerfile drift early) and runs a vulnerability scanner (Trivy/Grype) against them, failing on high/critical findings.
**Implementation strategy:** Add a `docker-build` job to `ci.yml` using `docker/build-push-action`, followed by `aquasecurity/trivy-action` scanning both images; on `main`, additionally push to a registry (GHCR) tagged with the commit SHA for traceability/rollback.

### 10.2 No automated dependency-vulnerability scanning
**Issue:** No `dependabot.yml`/`renovate.json` config, and no `pip-audit`/`npm audit`/`safety` step in CI.
**Why it's a problem:** With `requirements.txt` and `package-lock.json` pinned, the project is stable but will silently accumulate known-CVE dependencies over time with no automated signal.
**Best professional solution:** Enable Dependabot (or Renovate) for both `pip` and `npm` ecosystems, plus a CI step that fails on known-critical vulnerabilities.
**Implementation strategy:** Add `.github/dependabot.yml` with weekly checks for `pip` (backend) and `npm` (frontend); add `pip-audit` and `npm audit --audit-level=high` as CI steps (non-blocking initially, then enforced once the existing dependency tree is clean).

### 10.3 No staging environment / blue-green or canary deploy story documented
**Issue:** The README documents local dev and a single `docker compose up -d --build` production path; there's no mention of a staging environment, migration rollback plan, or zero-downtime deployment strategy (the backend's `docker-entrypoint.sh` runs Alembic migrations automatically on startup, which is convenient for a single instance but risky without a staging gate).
**Why it's a problem:** Auto-running migrations on container start is fine for a single, low-traffic internal tool today, but is exactly the kind of shortcut that causes an incident once the app is business-critical: a bad migration on the only environment goes straight to production data with no rehearsal.
**Best professional solution:** Introduce a staging environment (even a lightweight one — a second `docker compose` stack against a separate DB) that migrations and releases pass through first; decouple "run migrations" from "start the app" into an explicit release step (`alembic upgrade head` as a separate CI/CD job gated by manual approval for production) rather than an automatic container-boot side effect.
**Implementation strategy:** Split `docker-entrypoint.sh` into a `migrate` mode and a `serve` mode; wire a CD pipeline that runs `migrate` as its own step (with an approval gate for production), then rolls out new `serve` containers only after migration succeeds.

### 10.4 No documented backup/restore or disaster-recovery procedure
**Issue:** README covers local setup and Docker deployment thoroughly but has no section on Postgres backup cadence, retention, or a tested restore procedure — and the finalized-PDF `EvaluationDocument.pdf_bytes` are stored **inside** Postgres (as bytea), meaning a database backup is also the document backup, which is good for consistency but means DB backup size/time will grow with PDF volume.
**Why it's a problem:** For a system that produces legally significant, QR-verifiable documents, "we have never tested restoring from backup" is a real business risk that's easy to defer indefinitely without an explicit prompt.
**Best professional solution:** Document and periodically *test* (not just configure) an automated backup schedule (e.g., `pg_dump`/WAL archiving to object storage) with a defined RPO/RTO, and a quarterly restore drill.
**Implementation strategy:** Add a `deploy/BACKUP.md` documenting the chosen strategy (e.g., nightly `pg_dump` + WAL-G/pgBackRest to S3-compatible storage), a cron job or managed-DB feature implementing it, and a checklist for a quarterly "restore into a scratch environment and verify a known evaluation's PDF/hash still matches" drill.

### 10.5 Consider externalizing large binary blobs (PDFs) out of the primary OLTP database
**Issue:** Related to 10.4 — `EvaluationDocument.pdf_bytes` stores full PDF binaries directly in Postgres.
**Why it's a problem:** This is a defensible, simple choice for correctness (one transactional store, easy backup story) at moderate scale, but as the archive grows (years of finalized evaluations × potentially large PDFs with embedded fonts/QR images), it will inflate the primary database's size, backup time, and replication lag disproportionately compared to storing a reference (S3/object storage key) and keeping only the hash + metadata in Postgres.
**Best professional solution:** If/when database size becomes a concern, migrate to object storage (S3-compatible) for the PDF bytes, keeping `sha256` and a storage key in Postgres — preserving the exact same integrity-verification properties (hash still proves authenticity) without bloating the transactional store.
**Implementation strategy:** Not urgent at current scale; revisit if `pg_dump` time or database disk usage becomes a measured pain point. Document the threshold and migration plan (`ARCHITECTURE_DECISIONS.md`) now so it isn't a scramble later.

---

## 11. Observability

### 11.1 No centralized error tracking / APM
**Issue:** The custom `request_context` middleware in `main.py` is a genuinely nice touch (per-request ID, structured logging, safe 500 responses hiding tracebacks from clients) — but logs currently go to stdout/local logs only; there's no integration with an error-tracking service (Sentry, etc.) or an APM (Datadog/New Relic/OpenTelemetry).
**Why it's a problem:** Right now, diagnosing a production issue means SSH-ing into a container or grepping raw logs by request ID after the fact; there's no proactive alerting when error rates spike, no latency percentile tracking, and no way to correlate a frontend error report with the exact backend request that caused it.
**Best professional solution:** Adopt OpenTelemetry instrumentation (vendor-neutral) exporting traces/metrics/logs to whatever backend is chosen (self-hosted Grafana/Tempo/Loki stack, or a SaaS APM), plus a frontend error-tracking SDK (Sentry's browser SDK, or similar) wired to the new error boundary (§5.1).
**Implementation strategy:** Add `opentelemetry-instrumentation-fastapi` + `opentelemetry-instrumentation-sqlalchemy` to the backend; propagate the existing `request_id` as a trace attribute so logs and traces correlate; add the frontend SDK's `beforeSend` to include the currently logged-in role (not username/PII) for context without leaking sensitive data into a third-party error-tracking vendor.

### 11.2 No structured metrics/dashboards for operational health
**Issue:** No `/metrics` (Prometheus) endpoint or equivalent; the only health signals are the two liveness/readiness endpoints.
**Why it's a problem:** There's no visibility into request-rate, error-rate, p95/p99 latency, DB connection-pool saturation, or scheduler-sweep outcomes over time — all of which matter once this moves from "a few dozen users" to "the whole organization depends on this during every renewal cycle."
**Best professional solution:** Expose Prometheus-format metrics (request counts/latencies by route, DB pool stats, scheduled-sweep counters already returned by `run_all_sweeps`) and build a small Grafana dashboard.
**Implementation strategy:** Add `prometheus-fastapi-instrumentator`; emit the `run_all_sweeps` summary dict as gauge metrics in addition to the existing audit-log entry, so sweep health is visible on a dashboard, not just discoverable by querying the audit log.

---

## 12. Internationalization / Localization
(See §5.3 for the primary finding; additional notes below.)

### 12.1 Persian digit formatting is handled ad hoc per component
**Issue:** `.toLocaleString("fa-IR")` and a `_PERSIAN_DIGITS` translation table (backend `pdf.py`) both convert Western to Persian numerals, implemented independently in at least two places (frontend `SegmentedScore`, backend PDF rendering) rather than through one shared utility.
**Why it's a problem:** If the org ever needs an English-locale mode, every one of these ad hoc call sites needs to be found and made conditional; a single shared `formatNumber(value, locale)` utility would make that a one-line change instead of a grep-and-replace exercise.
**Best professional solution:** Centralize number/date formatting behind small shared utilities on both frontend (`utils/format.ts`) and backend (already partially done via `utils/jalali.ts`/`pdf.to_jalali`, just needs consolidation), consumed everywhere instead of ad hoc `.toLocaleString` calls.
**Implementation strategy:** Introduce `formatNumber(value)`/`formatPercent(value)` in `utils/dates.ts`'s sibling; migrate the handful of existing `.toLocaleString("fa-IR")` call sites to use it.

---

## 13. Documentation

### 13.1 README is dev-setup-focused; no architecture/ADR documentation
**Issue:** The (excellent, thorough) README covers local setup, Docker deployment, and seed users in detail, but there's no `ARCHITECTURE.md` explaining the workflow state machine, the manager-path special case, the snapshot/PDF-archival design, or the security model (token strategy, CSP rationale) as a single consolidated reference — this knowledge currently lives scattered across code comments (which are genuinely good, just not centralized).
**Why it's a problem:** A new engineer (or the "another AI model" this very audit is meant to hand off to) has to reconstruct the system's mental model by reading comments across a dozen files rather than one onboarding document.
**Best professional solution:** Add an `ARCHITECTURE.md` consolidating: the workflow state diagram (states × transitions × roles, directly derived from `TRANSITIONS`), the auth/session security model, the PDF archival/verification design, and the "manager path" business rule with its rationale.
**Implementation strategy:** A single new Markdown file; much of the content can be extracted nearly verbatim from the excellent existing Persian code comments, translated/consolidated into one narrative document (bilingual FA/EN recommended given likely future contributors).

### 13.2 No CONTRIBUTING.md / coding-standards doc
**Issue:** `ruff` and `oxlint` configs enforce *some* standards mechanically, but there's no human-readable contribution guide (branch naming, commit conventions, PR checklist, "how to add a new workflow transition safely").
**Why it's a problem:** Institutional knowledge about *why* certain patterns exist (e.g., "always use the `Transition` dataclass pattern for new workflow states, never hand-roll a new status check") currently lives only in the judgment of whoever wrote it.
**Best professional solution:** Add a short `CONTRIBUTING.md` with the project's key conventions and a "how to add X" cookbook section (new indicator type, new role, new workflow transition, new notification type) — this is exactly the highest-leverage documentation for an evolving internal tool.
**Implementation strategy:** Start with 4–5 "recipe" sections mirroring the architecture patterns already established (declarative transitions, `notify_once` dedup pattern, Alembic migration checklist).

---

# Part 2 – Premium Upgrade Roadmap

*The items below assume unlimited engineering capacity and describe how to take this from "a very well-built internal tool" to "an outstanding, enterprise-grade HR performance platform." Each includes what to build, why it matters, and a concrete implementation approach.*

## A. Architecture & Platform

### A.1 Event-driven architecture for workflow transitions
**What:** Replace the current in-request `notify_for_workflow_action` side-effect call with a proper event bus (e.g., publish a `EvaluationStatusChanged` event to Postgres's `LISTEN/NOTIFY`, Redis Streams, or a lightweight outbox pattern) that notifications, audit logging, webhooks, and future integrations (Slack/Teams/email) all subscribe to independently.
**Why:** Today, adding a new side effect to a workflow transition (say, "also post to a Slack channel") means editing `notify_for_workflow_action` directly, coupling unrelated concerns. An event-driven design lets each concern (in-app notification, email, Slack, analytics, webhook to an external HRIS) subscribe independently without touching the workflow code.
**How:** Implement the transactional outbox pattern: `apply_transition` writes an `OutboxEvent` row in the same transaction as the status change (guaranteeing at-least-once delivery even across restarts); a separate worker process polls/streams the outbox and dispatches to registered handlers (in-app notify, email, webhook). This also naturally solves multi-instance scheduling concerns from §8.1.

### A.2 Multi-tenancy support
**What:** Add a `tenant_id`/`organization_id` dimension across the schema, allowing this product to serve multiple organizations (e.g., if DbsPulse becomes a shared SaaS offering rather than a single-org internal tool).
**Why:** The current single-tenant design is the right choice for "one company's internal tool," but if there's any ambition to offer this to multiple client organizations (a very natural evolution for a well-built HR product), retrofitting multi-tenancy onto a live single-tenant schema is far more painful than designing it in early.
**How:** Add `organization_id` to every top-level table (`personnel`, `users`, `evaluation_periods`, `indicators`), scope every query through a `require_roles`-style dependency that also injects the current user's `organization_id` into every `WHERE` clause (ideally via Postgres Row-Level Security policies as a defense-in-depth backstop, not just application-layer filtering), and add an organization-admin role above HR.

### A.3 Pluggable approval-chain configuration (beyond the fixed 4-stage flow)
**What:** Generalize the currently hardcoded 4-stage chain (Supervisor → HR → Deputy → CEO, with the special manager-path variant) into a configurable approval-chain definition per role/department/personnel-type, so different organizational units or personnel grades can have different numbers of approval stages.
**Why:** The current design elegantly handles exactly one variant (the "manager path"); real organizations often need more variants over time (e.g., a 2-stage chain for junior contractors, a 5-stage chain including a board member for C-suite evaluations). A hardcoded `TRANSITIONS` dict, however cleanly designed, caps flexibility.
**How:** Model an `ApprovalChainTemplate` (ordered list of stage definitions: role required, optional "is scorer" flag) assignable per personnel record or personnel category; generalize `TRANSITIONS`/`apply_transition` to walk an arbitrary ordered chain instead of a fixed dict — this is a significant rewrite of `workflow.py`, best done as a major-version change with the existing 100 backend tests as a regression safety net (many of today's tests should still pass conceptually once ported to "the default 4-stage template").

### A.4 GraphQL or tRPC layer alongside REST (optional, evaluate need first)
**What:** For heavier future frontend needs (custom reporting builders, complex nested dashboards), consider a typed query layer.
**Why:** As the dashboard/reporting surface grows (see B.3 below), REST's fixed response shapes (`DashboardOverview`, etc.) will require an ever-growing number of bespoke endpoints for each new report variant; a typed query layer lets the frontend request exactly the shape it needs.
**How:** Only pursue this if reporting needs actually explode in variety; otherwise the current REST design (already clean, with Pydantic-validated schemas) remains the better choice for a team of this size. Flagging as a "watch and reconsider" item, not a "must build."

## B. Feature Roadmap

### B.1 Employee self-assessment stage
**What:** Add an optional pre-stage where the employee fills in a self-assessment (self-scored on the same indicators, with their own evidence) before the supervisor's evaluation, shown side-by-side to the supervisor during scoring.
**Why:** Self-assessment is one of the highest-value, most commonly requested features in performance-management tools — it surfaces perception gaps ("employee rates themselves a 5 on collaboration, supervisor rates a 3") that are exactly the conversations a renewal-decision process should surface early, not after the fact.
**How:** Add a new `EvaluationStatus.self_assessment_pending` initial state (or a parallel `SelfAssessment` table linked 1:1 to the evaluation record) with an `employee`-role-gated endpoint to submit it; surface it read-only alongside the supervisor's scoring UI.

### B.2 Goal-setting / OKR integration between evaluation cycles
**What:** Extend `ImprovementPlan` (which already exists for post-evaluation remediation) into a general goal-tracking feature usable proactively, not just reactively — employees and supervisors set quarterly goals, tracked and referenced during the next evaluation cycle.
**Why:** The current `ImprovementPlan` model is reactive (created after a low score); a mature performance system closes the loop by tracking goals continuously, so the *next* evaluation naturally references "did you hit the goals set last quarter."
**How:** Generalize `ImprovementPlan` into a `Goal` entity with a `source` field (`improvement_plan` | `proactive`), link goals to evaluation periods, and surface "goals from last period" directly inside the next evaluation's scoring UI as context for the evaluator.

### B.3 Rich, exportable, drillable analytics beyond the current fixed dashboard
**What:** A proper BI-style reporting builder: custom date ranges, cross-filtering by org unit/role/indicator, exportable charts, saved report definitions, and trend comparisons across multiple evaluation periods (year-over-year, not just per-person trend as today).
**Why:** The current `DashboardOverview` is a fixed, valuable, but non-customizable snapshot ("top 5 lowest of X, all-time"). HR leadership and executives (CEO role already exists!) typically want to slice this data many different, unpredictable ways for board reporting and workforce planning.
**How:** Either integrate a lightweight embedded BI tool (Metabase/Superset pointed at a read-replica of the Postgres DB, with row-level security scoping by role) for maximum flexibility with minimal custom-dashboard-code investment, or build a custom filter/drill UI on top of a properly indexed reporting schema (a `evaluation_facts` denormalized table refreshed by the existing scheduled-sweep mechanism) if a fully native in-app experience is preferred.

### B.4 Calibration sessions / cross-evaluator normalization
**What:** A structured "calibration" feature where HR can compare score distributions across different supervisors/units to catch systematic leniency/harshness bias (the `by_evaluator` dashboard stat is a first step toward this, but there's no workflow *around* it — e.g., flagging outlier evaluators, facilitating a calibration meeting, adjusting/re-scoring with a documented rationale).
**Why:** Cross-evaluator score inconsistency is one of the most common, most damaging fairness problems in real performance-management processes (an employee's renewal outcome shouldn't depend on which supervisor happened to score them); today's dashboard *shows* the averages but provides no tool to act on the finding.
**How:** Add a "calibration session" workflow: HR flags a set of evaluations for review, a calibration view shows all flagged scores side by side grouped by indicator, and any adjustment requires a documented reason logged to the audit trail (extending the existing `return`/comment infrastructure rather than inventing something new).

### B.5 Native mobile-friendly / offline-capable scoring
**What:** A PWA (installable, offline-capable) mode for supervisors who evaluate in the field (e.g., site visits, no reliable connectivity) — draft scores/evidence saved locally (IndexedDB) and synced when connectivity returns.
**Why:** Not every supervisor works at a desk with a stable connection; an evaluator on a factory floor or remote site benefits enormously from an app that doesn't lose 20 minutes of typed evidence to a dropped connection.
**How:** Add a service worker (Vite has first-class PWA plugin support), cache the app shell + in-progress draft data in IndexedDB, and implement a background-sync reconciliation strategy (last-write-wins is likely fine here given the single-evaluator-per-draft invariant already enforced server-side).

### B.6 Email digests, in addition to in-app notifications
**What:** Optional daily/weekly email digest of pending actions ("You have 3 evaluations awaiting your approval") alongside the existing in-app `NotificationBell`.
**Why:** In-app-only notifications require the user to remember to open the app; for a workflow with real deadline pressure (contract renewals), a periodic email nudge closes the loop for people who don't check the app daily.
**How:** Add an email-sending integration (any transactional email provider), a per-user notification-preference setting (in-app only / +email digest / +immediate email for finalize events), and a scheduled job (again reusing the `scheduled.py` sweep pattern) that batches pending notifications into a digest.

## C. UI/UX Redesign Ideas

### C.1 Command palette (⌘K) for power users
**What:** A global fuzzy-search command palette (à la Linear/Notion/GitHub) letting any user jump to "Ali Mohammadi's evaluation," "Users page," "Change password," etc. from anywhere with a keyboard shortcut.
**Why:** With 8+ HR nav items alone and cross-linked entities (personnel ↔ evaluations ↔ users), a command palette dramatically speeds up navigation for daily power users (especially HR).
**How:** A lightweight implementation using `cmdk` (React library), backed by a debounced search hitting existing list endpoints (`personnel?q=`, `evaluations?q=`) plus a static list of known routes; bind to `Cmd/Ctrl+K`.

### C.2 Timeline/activity view per evaluation
**What:** A visual, chronological timeline component on the evaluation detail page showing every status change, comment, and return with actor + timestamp, rather than (or in addition to) the current tabular comment list — essentially a changelog/audit view scoped to one record, reusing the already-rich `AuditLog` data that today is only browsable HR-wide on a separate page.
**Why:** For a document this consequential (affects someone's job renewal), a clear "here is exactly what happened and when, and by whom" narrative view builds trust and speeds up understanding for anyone re-entering the record after a return/delay.
**How:** A new `GET /api/evaluations/{id}/timeline` endpoint joining `AuditLog` + `EvaluationComment` filtered to that record, rendered as a vertical timeline component (icon per event type, relative + absolute Jalali timestamps).

### C.3 Visual workflow/status stepper
**What:** Replace the current text `StatusBadge` + `STAGE_LABELS` pairing with a horizontal stepper component (Supervisor → HR → Deputy → CEO → Finalized) showing the current stage highlighted, completed stages checked, and — for the manager path — the supervisor step visually collapsed/skipped with an explanatory tooltip.
**Why:** A visual stepper communicates "where is this in the process, and what's left" far faster than a status badge + separate stage label text, and makes the manager-path special case self-explanatory in the UI rather than something users have to learn from documentation.
**How:** A small reusable `<WorkflowStepper stages={...} current={...} />` component; derive its state directly from the existing `status`/`stage` fields already returned by the API.

### C.4 Dark mode
**What:** A theme toggle (light/dark/system), implemented via Tailwind's `dark:` variant and a persisted preference.
**Why:** Standard modern-app expectation; also genuinely reduces eye strain for HR staff who may have this dashboard open for extended review sessions during evaluation season.
**How:** Tailwind v4 dark-mode support + a `ThemeContext` persisting to a first-party cookie or (per the artifact/browser-storage rules elsewhere) an authenticated user preference stored server-side rather than `localStorage`, so it follows the user across devices.

### C.5 Guided onboarding / first-run tour for each role
**What:** A short, skippable, role-specific product tour on first login for each of the 5 roles, highlighting the 2–3 things that role does most often (e.g., for `unit_supervisor`: "here's your list, here's how to start an evaluation, here's the evidence rule").
**Why:** With 5 distinct roles and a workflow that isn't obvious from a blank screen, a first-run tour meaningfully reduces support burden and time-to-productivity for new hires taking on an evaluator role.
**How:** A lightweight tour library (e.g., `react-joyride` or a hand-rolled spotlight overlay), triggered once per user via a `has_seen_onboarding` flag on the user record (or a `localStorage`-plus-server-fallback pattern), with role-specific step definitions.

## D. Developer Experience

### D.1 Adopt a monorepo task runner (Turborepo/Nx) or at least a root `Makefile`
**What:** A single entry point (`make dev`, `make test`, `make lint`) that orchestrates both `backend/` and `frontend/` commands, rather than requiring developers to `cd` into each and remember two different tool invocations (`uvicorn` vs `npm run dev`, `pytest` vs `vitest run`).
**Why:** Small friction, but compounds daily; also gives CI a single, DRY entry point instead of duplicating `working-directory:` blocks per job.
**How:** A root `Makefile` (or `justfile`) with `dev`, `test`, `lint`, `build`, `migrate` targets that fan out to the appropriate sub-project commands; CI jobs call the same `make` targets for parity between local dev and CI.

### D.2 Seed/fixture data generator for realistic demo/staging data
**What:** A script generating a large, realistic dataset (hundreds of personnel across many org units, multiple completed evaluation cycles with varied score distributions) beyond the current handful of seed users — useful for performance testing (§9.3), demoing the analytics dashboard meaningfully, and UI testing with realistic list lengths.
**Why:** The current seed data (a few sample users/personnel per the README) is great for functional testing but can't exercise pagination, dashboard aggregate realism, or performance characteristics.
**How:** A `scripts/generate_demo_data.py` using `Faker` (with Persian locale support) to generate N personnel, realistic multi-cycle evaluation histories with correlated-but-varied scores, runnable against a scratch database for demos/load-testing/staging.

### D.3 Storybook for the shared UI component library
**What:** Document `ui/Button.tsx`, `ui/Modal.tsx`, `ui/Card.tsx`, `ui/Meters.tsx`, `SegmentedScore`, `StatusBadge`, etc. in Storybook with all their states (loading, error, disabled, RTL) as isolated, visually-reviewable stories.
**Why:** These are exactly the components reused everywhere; a living style guide makes it obvious what already exists (reducing duplicate one-off components) and gives designers a reviewable surface without needing to run the full app.
**How:** Standard Storybook + Vite integration; wire the CI visual-regression tooling from §5.5 to run against these stories too, which is typically cheaper/faster than full-page E2E visual diffs.

### D.4 Typed API client generation from the OpenAPI schema
**What:** Instead of hand-written `types.ts` mirroring backend Pydantic schemas (a manual sync point that can silently drift), generate the frontend's TypeScript types (and ideally a typed API client) directly from the backend's `/openapi.json` using `openapi-typescript` or similar.
**Why:** Manual type duplication between `backend/app/schemas/*.py` and `frontend/src/types.ts` is a classic source of silent drift — a backend field rename or type change won't be caught by TypeScript until a real API response actually differs at runtime.
**How:** Add an `npm run generate:types` script running `openapi-typescript` against a locally running backend's `/openapi.json` (or a checked-in schema snapshot updated in CI), replacing hand-maintained interfaces with generated ones; keep hand-written wrapper types only for frontend-only concerns (e.g., UI-only derived state).

## E. Security Hardening (beyond Part 1's findings)

### E.1 WebAuthn/passkey support for HR and executive roles
**What:** Optional passwordless/second-factor authentication (WebAuthn) for the highest-privilege roles (`hr`, `ceo`, `deputy`), who can approve/finalize consequential HR decisions.
**Why:** These roles are the highest-value targets for account takeover (an attacker controlling the `ceo` account can finalize fraudulent evaluations); passwords alone, even with the excellent Argon2/rotation hygiene already in place, remain phishable.
**How:** Add WebAuthn registration/authentication endpoints (e.g., via `py_webauthn`), make it mandatory (or strongly encouraged with periodic reminders) for `hr`/`deputy`/`ceo` roles, keep password+TOTP as a fallback for broader roles if full WebAuthn rollout isn't immediately feasible everywhere.

### E.2 Field-level encryption for the most sensitive PII, if regulatory requirements demand it
**What:** Encrypt especially sensitive free-text fields (evidence text, comments) at the application layer (e.g., using `pgcrypto` or application-side AES-GCM with a KMS-managed key) in addition to at-rest disk encryption.
**Why:** Only relevant if the organization's regulatory environment or a customer's contractual requirements demand encryption-at-the-field-level beyond standard disk/volume encryption; not a default recommendation for every deployment, but worth having a documented decision either way.
**How:** If required, use a KMS (AWS KMS/HashiCorp Vault) to manage a data-encryption key, encrypt `evidence_text`/`comment_text` before insert, decrypt on read in the application layer (accepting the tradeoff that full-text search on these fields becomes harder — plan accordingly, e.g., maintain a separate searchable-but-redacted index if needed).

### E.3 Formal third-party penetration test before go-live at scale
**What:** Commission an external pentest once the app handles real organizational data at scale, covering the auth flow, the public verify endpoint (post-fix from §1.1), file/PDF handling, and RBAC boundary conditions.
**Why:** This audit is thorough but is a single-pass static/manual review; a dedicated external pentest with dynamic testing tools and adversarial creativity will find categories of issues (timing side-channels, subtle RBAC bypass chains across multiple endpoints, business-logic abuse) that a code read alone cannot guarantee catching.
**How:** Standard practice — budget for an annual (or pre-major-release) external pentest once the user base and data sensitivity justify the cost; feed findings back into the same audit-and-remediate cycle this document represents.

## F. Compliance & Data Governance

### F.1 Formal data-retention and privacy policy, enforced in code
**What:** A documented data-retention policy (how long is evaluation data kept post-employment, how long are audit logs kept, what's the erasure process) directly tied to the technical implementation from §2.2/§2.4.
**Why:** Performance evaluation data is sensitive personal data in most jurisdictions (GDPR-adjacent obligations even outside the EU are increasingly common in data-protection law generally); "we technically could delete data" isn't the same as "we have a policy and an enforced process."
**How:** Draft the policy with HR/legal input, then implement it as the scheduled sweeps described in §2.2/§2.4 — retention isn't complete until it's automated, not just documented.

### F.2 Consent and transparency notices for employees
**What:** A clear, accessible notice to employees (surfaced in the `employee`-role `MyEvaluationsPage`/"کارنامه من") explaining what data is collected about them, who can see it, and how long it's retained — beyond just showing them their finalized scores.
**Why:** Transparency isn't just a compliance checkbox; it's core to employee trust in a system that materially affects their employment. The product already goes out of its way to let employees "acknowledge" their evaluation (`acknowledged_at`) — a natural place to also surface this transparency information.
**How:** Add a lightweight, versioned "privacy notice" component shown once (and re-shown on material policy changes, tracked by a version number) before an employee views their first evaluation.

---

## Closing Notes for the Implementing Engineer/Model

This codebase reflects careful, security-conscious, well-tested engineering — the findings above are deliberately weighted toward genuine gaps rather than restating what's already done well. When implementing from this document:

1. **Prioritize §1.1 (public enumeration leak) and §1.2 (leaked local credential rotation) first** — these are the only findings with immediate real-world exposure risk.
2. **Prioritize §6.1/§6.2 (autosave/unsaved-changes) and §6.3 (modal focus trap) next** — these are the highest-impact, lowest-effort user-facing fixes.
3. Treat Part 2 as a backlog to sequence against actual product/business priorities, not a mandate to build everything — several items (multi-tenancy, GraphQL, field-level encryption) are explicitly flagged as "only if X becomes true" rather than unconditional recommendations.
4. Every finding in Part 1 was verified against the actual source in this archive; where an item notes uncertainty (e.g., §7.4's Recharts accessibility, which depends on exact chart configuration not fully re-derived here), treat it as "verify, then fix" rather than "assumed broken."
