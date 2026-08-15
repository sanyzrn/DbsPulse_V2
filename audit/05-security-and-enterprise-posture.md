> **DbsPulse V2 — Product, Architecture, Workflow, Security & UX Audit**  
> Repository: <https://github.com/sanyzrn/DbsPulse_V2> · Branch `main` · Commit `ef0166b091d2d167d808702e084c079e5143e307`  
> Site section: 1.4 · Security posture and enterprise readiness

# Security posture and enterprise readiness — where the deployment stands

Summarised from the security, authorization, observability and deployment findings in section 2. External infrastructure — monitoring backends, backup jobs, TLS termination outside the shipped configuration — is outside the repository and is marked *Not verifiable from the repository* rather than reported as missing.

## Authentication & sessions — Strong foundation

**In place**

- Argon2 hashing with a dummy-hash timing defence
- Access token in memory only — never localStorage
- Refresh rotation, 60s grace, reuse detection, family revocation
- token_version invalidates every token on password change

**Gaps**

- No MFA
- No per-account lockout
- No user-visible session list or self-revocation

## Authorization — Record-level, with one hole

**In place**

- require_roles on every protected route
- _ensure_can_view is a genuine record-level (BOLA-resistant) check
- Transition assignee checks bind action to the named user
- Employee list branch returns only own finalized records

**Gaps**

- HR transitions have no assignee — any HR user acts on any record
- HR is also super-admin: no separation of duties
- Improvement plans are HR-only; the named owner has no access

## Data protection — Partly addressed

**In place**

- Public verification uses an unguessable token, not the sequential code
- PDF template escapes output and restricts URL fetching to local templates
- nginx sets CSP, X-Frame-Options DENY, nosniff, Referrer-Policy
- Production config refuses default secrets and non-HTTPS origins

**Gaps**

- No minimum-cohort suppression in analytics or exports
- No retention, deletion, legal-hold or subject-access capability
- Excel exports do not neutralise formula prefixes
- No HSTS in the shipped nginx template

## Operations — Weakest area

**In place**

- Health and readiness endpoints exist
- Request-ID middleware with a non-leaking 500 handler
- Idempotent PDF archiving with graceful degradation
- 15 purposeful indexes across hot query paths

**Gaps**

- Scheduler is in-process, off by default, unsafe with >1 replica
- No metrics, tracing or error tracking
- Migrations applied automatically on every container boot
- Backend container runs as root
- Backup and DR: not verifiable from the repository

## Related findings

Full evidence, fixes, impact, difficulty, dependencies and confidence for every point above are in `07-gap-analysis-findings.md`.

---

Audit of `sanyzrn/DbsPulse_V2` — branch `main`, commit `ef0166b091d2d167d808702e084c079e5143e307`. Findings derive from static inspection of source files in that commit. No application code was modified. Items that cannot be confirmed from the repository are labelled *Not verifiable from the repository*.
