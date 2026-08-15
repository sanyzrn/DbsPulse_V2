> **DbsPulse V2 — Product, Architecture, Workflow, Security & UX Audit**  
> Repository: <https://github.com/sanyzrn/DbsPulse_V2> · Branch `main` · Commit `ef0166b091d2d167d808702e084c079e5143e307`  
> Site section: 1.5 · Reviewed scope

# Reviewed scope — repository inventory and system boundaries

What was inspected, and the boundaries of the claim. Backend routers, services, models, migrations, core configuration, Docker and CI artifacts, frontend routing, authentication, API client, feature flags and permission logic were read as source. Areas not read are named below rather than implied to be covered.

## Inventory

| Measure | Value |
|---|---|
| Files in repository | 215 |
| Source lines (.py / .ts / .tsx) | ~22,600 |
| Backend routers | 16 |
| API endpoints | 72 |
| Database entities | 12 |
| Alembic migrations | 19 |
| Service modules | 11 |
| Backend tests | 152 |
| Frontend tests | 29 |
| DB indexes created by migrations | 15 |

## Technology under review

### backend

```text
FastAPI 0.115.6 · SQLAlchemy 2.0.36 (typed Mapped[]) · Alembic 1.14.0 · PostgreSQL 16 · psycopg 3.2.3 · Pydantic 2.10.4 · PyJWT 2.10.1 · argon2-cffi 23.1.0 · WeasyPrint 63.1 + Jinja2 · slowapi 0.1.10 · jdatetime 5.3.0 · openpyxl 3.1.5 · qrcode 8.2 · uvicorn 0.34.0
```

### frontend

```text
React 19 · TypeScript ~6.0 · Vite 8 · Tailwind CSS 4 (full RTL) · TanStack Query 5 · React Router 7 · Recharts 3 · axios · motion · @fontsource/vazirmatn · oxlint + vitest
```

### infra

```text
Docker Compose (db / backend / frontend) · nginx reverse proxy with CSP, X-Frame-Options, nosniff, Referrer-Policy · GitHub Actions CI (ruff, pytest, oxlint, vitest, tsc) · deploy/nginx-https.conf.example
```

## Tenancy determination

**Verdict:** Single-organization · **Confidence:** High

No tenant / organization / company column exists on any of the 12 SQLAlchemy models (users, personnel, evaluation_records, evaluation_scores, evaluation_comments, evaluation_access, indicators, evaluation_periods, improvement_plans, improvement_plan_goals, notifications, audit_log, auth_sessions). Every query is global to the single deployment. The product is therefore a single-company internal system, not multi-tenant and not multi-tenant ready: adding tenancy would require a schema change plus a scoping predicate on every query, export, analytics aggregation, background sweep, document fetch and audit-log read.

## Not inspected / not verifiable

- `deploy/nginx-https.conf.example` — referenced by the README for TLS; not read, so HSTS and cipher configuration there are not verifiable
- `setup_and_run.bat` — Windows helper script; not read
- Runtime behaviour of the 152 backend tests — PostgreSQL unavailable in the review environment; CI definition verified, results not observed
- Monitoring, alerting, backup, restore and TLS termination in the live environment — external infrastructure, not verifiable from the repository
- Exact leftmost/rightmost X-Forwarded-For selection in uvicorn 0.34.0 — inferred, not read from source; P0-04 is therefore Medium confidence

## Runtime verification

**Runtime verification was not possible.** PostgreSQL is not available in the review environment (no postgres / psql / pg_ctl binaries; /usr/lib/postgresql absent). DbsPulse hard-requires PostgreSQL features (JSONB columns, partial unique indexes, sequences, SELECT … FOR UPDATE OF), so the 152 backend tests could not be executed. Test-suite health is reported from the CI definition only (.github/workflows/ci.yml), never as a passing result observed by this audit. Every finding below is derived from static reading of actual source files.

## Implementation authenticity

**This is a real implementation, not a prototype.** A repository-wide search for TODO / FIXME / XXX / HACK / mock / dummy / placeholder / 'coming soon' / 'به‌زودی' / 'not implemented' returned only React Query's placeholderData option and HTML placeholder attributes. There is no mock data layer, no stubbed service, no fake API. Scores, transitions, PDF archiving, hashing, notifications and audit entries are all backed by real database writes. The one exception is a fully-built backend capability hidden from the UI by a feature flag (see W-07 / P1-07) — which is a release-management gap, not a fake feature.

---

Audit of `sanyzrn/DbsPulse_V2` — branch `main`, commit `ef0166b091d2d167d808702e084c079e5143e307`. Findings derive from static inspection of source files in that commit. No application code was modified. Items that cannot be confirmed from the repository are labelled *Not verifiable from the repository*.
