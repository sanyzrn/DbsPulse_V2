> **DbsPulse V2 — Product, Architecture, Workflow, Security & UX Audit**  
> Repository: <https://github.com/sanyzrn/DbsPulse_V2> · Branch `main` · Commit `ef0166b091d2d167d808702e084c079e5143e307`  
> Site section: 1. Product Reality — hero, verdict and review basis

# DbsPulse V2 — product reality audit

An evidence-based assessment of an Iranian organizational performance-evaluation platform whose output is a contract-renewal recommendation. Judged as a commercial performance-management product: every claim below is traced to a file in commit `ef0166b`, and anything the repository cannot prove is labelled as such.

| Attribute | Value |
|---|---|
| Subject | DbsPulse V2 — سامانه ارزیابی عملکرد شرکت نفس زیست فارمد |
| Repository | https://github.com/sanyzrn/DbsPulse_V2 |
| Branch | `main` |
| Commit reviewed | `ef0166b091d2d167d808702e084c079e5143e307` |
| Commit detail | Bug Fix — sanyzrn — Mon Jul 13 11:26:32 2026 +0330 |
| Commits in history | 79 |
| Application version | 0.2.0 (frontend/src/appInfo.ts) |
| Review date | 2026-07-31 |
| Tenancy | Single-organization |

## Headline result

| Metric | Value |
|---|---|
| **Overall maturity score** | **64 / 100** |
| Verdict | Solid internal tool — not yet a commercial performance-management product |
| Findings | 41 |
| P0 blockers | 8 |
| Capabilities mapped | 21 |
| Workflow checks | 15 |

**Score methodology.** Overall = Σ (area score × weight). Area scores are assigned from inspected source evidence only: a capability scores where it is provably enforced in backend code or the database schema, not where the UI or README claims it.

## This is a real implementation, not a prototype

A repository-wide search for TODO / FIXME / XXX / HACK / mock / dummy / placeholder / 'coming soon' / 'به‌زودی' / 'not implemented' returned only React Query's placeholderData option and HTML placeholder attributes. There is no mock data layer, no stubbed service, no fake API. Scores, transitions, PDF archiving, hashing, notifications and audit entries are all backed by real database writes. The one exception is a fully-built backend capability hidden from the UI by a feature flag (see W-07 / P1-07) — which is a release-management gap, not a fake feature.

## Runtime verification was not possible

PostgreSQL is not available in the review environment (no postgres / psql / pg_ctl binaries; /usr/lib/postgresql absent). DbsPulse hard-requires PostgreSQL features (JSONB columns, partial unique indexes, sequences, SELECT … FOR UPDATE OF), so the 152 backend tests could not be executed. Test-suite health is reported from the CI definition only (.github/workflows/ci.yml), never as a passing result observed by this audit. Every finding below is derived from static reading of actual source files.

## Tenancy determination

**Verdict:** Single-organization · **Confidence:** High

No tenant / organization / company column exists on any of the 12 SQLAlchemy models (users, personnel, evaluation_records, evaluation_scores, evaluation_comments, evaluation_access, indicators, evaluation_periods, improvement_plans, improvement_plan_goals, notifications, audit_log, auth_sessions). Every query is global to the single deployment. The product is therefore a single-company internal system, not multi-tenant and not multi-tenant ready: adding tenancy would require a schema change plus a scoping predicate on every query, export, analytics aggregation, background sweep, document fetch and audit-log read.

---

Audit of `sanyzrn/DbsPulse_V2` — branch `main`, commit `ef0166b091d2d167d808702e084c079e5143e307`. Findings derive from static inspection of source files in that commit. No application code was modified. Items that cannot be confirmed from the repository are labelled *Not verifiable from the repository*.
