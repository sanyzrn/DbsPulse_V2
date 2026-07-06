# UIUX_audit.md — DbsPulse

## Methodology Disclosure (read this first)

I need to be upfront about what I actually did here, because the request was to run the app and click through it as a real user, and **I could not do that** — verified directly, not assumed:

- This environment has **no network egress** for the sandbox (`pip install fastapi` → `ERROR: No matching distribution found`; the `npm` registry is blocked). None of the backend's dependencies (FastAPI, SQLAlchemy, WeasyPrint, etc.) can be installed, and there is no PostgreSQL server available.
- There is **no browser-automation tool** available (no Playwright/Selenium/screenshot-and-click capability) — even if the servers were running, there is no way to literally click a button and observe pixels or a real console/network tab.

So the app was not run, and this document does not pretend otherwise. What was done instead — the most rigorous substitute actually available — was a **precise, line-level trace of the real frontend and backend source** for every role: simulating exactly what each component renders, what each click calls, what each API endpoint permits, and cross-checking frontend conditions against backend permission logic. Every finding below is backed by an exact file/line that was read, not a guess. This will not catch CSS rendering glitches, actual browser console errors, or visual RTL bugs — but it reliably catches the category originally asked about: **logic that's reachable in theory but broken or inconsistent in practice**, and several strong, concrete examples of exactly that were found.

If a true click-through report with screenshots and real console/network output is needed, that requires either network+browser tool access, or running it locally and sharing what appears on screen.

---

# PART 1 — Deep Functional & UX Audit (code-traced, not click-tested)

## Roles identified
From `backend/app/models/enums.py`: **`unit_supervisor`** (مسئول واحد), **`hr`**, **`deputy`** (معاونت), **`ceo`** (مدیرعامل), **`employee`**. Each maps to exactly one nav configuration in `frontend/src/components/Layout.tsx`'s `NAV_BY_ROLE`.

## 1. Bugs (broken / erroring / incorrect behavior)

### B1 — CEO's entire application is a single hardcoded status filter with no path to history
**Role:** `ceo`. **Page:** `/ceo` (the CEO's *only* nav item, per `Layout.tsx`'s `NAV_BY_ROLE.ceo`).

**Code:** `frontend/src/pages/ceo/CeoHomePage.tsx` is exactly:
```tsx
export function CeoHomePage() {
  return <EvaluationList title="پرونده‌های در انتظار تأیید نهایی" statusFilter="deputy_approved" />;
}
```
**Expected:** After a CEO finalizes an evaluation, they should still be able to find it — to re-check the decision, re-download the PDF, or re-verify a printed QR code that a manager brings back to them.

**Actual:** `EvaluationList` (`components/EvaluationList.tsx`) has **no status-filter UI at all** — only a text search box (`جست‌وجو`) and pagination. The `statusFilter` prop is fixed by the parent page and never exposed to the user. The moment a CEO clicks "تأیید نهایی" (finalize), the record's status flips to `finalized`, and it **permanently disappears from the only page the CEO role has**. There is also no route like `/ceo/history`, no notification sent to the CEO for their own finalize action (`notifications.py`: `ceo_finalize` sends to `evaluator_id`, not the CEO), and no `/personnel` or generic browse page in the CEO's nav.

**Reproduction (traced):** Log in as `ceo1` → approve/finalize any evaluation → it vanishes from `/ceo` → there is no click path anywhere in the UI to see it again. The record is still reachable at `/evaluations/{id}` via direct URL (backend's `_ensure_can_view` allows it, since `ceo_user_id` is in the allowed set regardless of status) — but nothing in the UI ever shows that URL to the user. This is precisely "reachable in theory, unreachable in practice."

**Severity:** High — this affects the most senior role in the approval chain and blocks re-printing/re-verifying legally significant documents.

### B2 — Deputy has the identical defect, plus a silent dead data-fetch
**Role:** `deputy`. **Page:** `/deputy` (also their only nav item).

**Code:** `frontend/src/pages/deputy/DeputyHomePage.tsx`:
```tsx
<EvaluationList title="پرونده‌های در انتظار بررسی معاونت" statusFilter="hr_approved" />
```
Same defect as B1: once a deputy approves a case (→ `deputy_approved`), it's gone from their view forever, with no history page.

**Additional bug on the same page:** the component calls `usePersonnelList({ accessible_to_me: true, ... })` and then does `const managers = (data?.items ?? []).filter((p) => p.is_manager)` — it fetches **all** personnel accessible to this deputy (both manager-path and regular subordinates whose chain includes this deputy as final approver context), but then **only renders the `is_manager` subset**. The non-manager personnel this deputy has downstream visibility into are fetched over the network and then silently discarded — never shown anywhere on the page.

**Reproduction:** Log in as `dep1` → approve "حسین رضایی" (the manager-path sample) → case vanishes from `/deputy` with no way back to it.

### B3 — HR's "Queue" is the only generic evaluations page in the entire HR nav, and it's hardcoded to one status
**Role:** `hr`. **Page:** `/hr/queue`.

**Code:** `frontend/src/pages/hr/QueuePage.tsx`:
```tsx
export function QueuePage() {
  return <EvaluationList title="صف بررسی منابع انسانی" statusFilter="submitted" />;
}
```
**Expected:** HR's own backend comment literally says *"hr می‌بیند همه را"* (HR sees everything) — `list_evaluations` in `evaluations.py` applies no role-based filter for HR. So the backend fully supports HR browsing evaluations at any status.

**Actual:** every page in HR's nav (`/hr/personnel`, `/hr/users`, `/hr/indicators`, `/hr/queue`, `/hr/periods`, `/hr/improvement-plans`, `/hr/dashboard`, `/hr/audit-log`) was checked — **none of them is a general-purpose "browse all evaluations, filter by status/period/person" screen.** `/hr/dashboard` only exposes fixed top-5 aggregate lists (lowest performers, lowest units), not a searchable record browser. So HR — the role with the widest backend permissions in the system — has no UI path to, say, "find every `draft` evaluation that's been sitting for 3 weeks" or "pull up a specific finalized record to reprint its PDF" without either (a) using the bulk Excel export and grepping it, or (b) guessing/knowing the exact evaluation ID.

**Severity:** High — this is the role most likely to need ad hoc lookup capability, and it's the one role for which this gap is most damaging operationally.

### B4 — `EvaluationList`'s status-filtering capability exists in the API contract but is architecturally unreachable by the user in 3 of its 4 usages
This is the root cause tying B1–B3 together, called out as its own structural bug rather than three coincidences: `useEvaluations()` (`api/queries.ts`) happily accepts a `status` param and the backend happily filters on it — but `EvaluationList.tsx` takes `statusFilter` as a **prop from the parent page**, not as user-controlled state, and renders no dropdown/tabs/toggle to change it. Every one of its 4 call sites either hardcodes a single status (`hr_approved`/`deputy_approved`/`submitted`) or passes nothing (only `SupervisorHomePage`'s second list, "ارزیابی‌های من", does this — and that one, correctly, shows every status). **The fix belongs in the shared component, not in each page**, because otherwise every future page reusing `EvaluationList` will reproduce the same defect by default.

### B5 — Personnel/subordinate names are inert plain text almost everywhere except HR's PersonnelPage — no profile, no history, no click target
**Roles affected:** `unit_supervisor`, `deputy`, and (for a different list) `hr` on the Improvement Plans page.

**Code, `SupervisorHomePage.tsx`:**
```tsx
<td className="px-3 py-2.5 font-medium text-gray-700">{p.full_name}</td>
```
No `onClick`, no `<Link>`. The only interactive element in that row is "شروع ارزیابی جدید" (start new evaluation). Identical pattern in `DeputyHomePage.tsx`, and again in `pages/hr/ImprovementPlansPage.tsx` (`{item.personnel_full_name}` and `{p.personnel_full_name}` rendered as plain `<td>` text, lines 71/227 — only the *plan* itself is a link, via `<Link to={/hr/improvement-plans/${p.id}}>`, not the person).

**Contrast — HR's `PersonnelPage.tsx` does this correctly**, and even documents the intent in a Persian code comment worth quoting precisely because it states the exact principle originally asked about:
> *"پروفایل پرسنل با کلیک روی نام از همین فهرست همیشه در دسترس است؛ به هیچ مرحله‌ای از گردش‌کار ارزیابی (مثل بازکردن یک پرونده خاص) گره نخورده است."*
> ("Clicking the name always opens the profile from this list; it isn't tied to any evaluation-workflow stage like opening a specific case.")

That's genuinely well-engineered — for HR only. A supervisor, deputy, or CEO gets no equivalent: their **only** way to see anything about a subordinate is to open a specific evaluation record via `EvaluationDetailPage`, which fetches `usePersonnelDetail(evaluation.subject_personnel_id)` — meaning a person's basic info (job title, org unit, contract dates) is visible to their evaluator **only in the context of a specific evaluation record that already exists**, never as a standalone, always-available profile view. If no evaluation has ever been started for someone, a supervisor literally cannot look up their contract end date or job title anywhere in the UI.

**Severity:** High — this is exactly the "clicking a name only works during certain workflow steps" pattern originally described, confirmed to actually exist, in three different places.

### B6 — Performance trend/radar charts (`EmployeeProfileModal`) are HR-only at the API layer, even though evaluators are the ones who need them most
**Code:** `backend/app/api/routers/dashboard.py` — `GET /api/dashboard/personnel/{id}/radar` and `/trend` are both gated `Depends(require_roles(UserRole.hr))`. `PersonnelPage.tsx`'s `EmployeeProfileModal` is the only frontend consumer.

**Consequence:** A `unit_supervisor` about to evaluate someone for the third year running has no way to see that person's prior scores/trend before scoring them — not through any UI, and not even by guessing a URL, because the backend itself 403s any non-HR role. Only HR (who isn't the one actually scoring people) can see the trend chart. This seems backwards for a tool whose entire purpose is informed evaluation.

### B7 — Notification inbox is capped at 15 items with zero pagination or "view all" page
**Code:** `frontend/src/api/queries.ts`:
```tsx
queryFn: async () => (await apiClient.get<NotificationPage>("/notifications", { params: { limit: 15 } })).data,
```
The dropdown (`NotificationBell.tsx`) renders exactly what this returns, in a `max-h-80 overflow-y-auto` scrollable `<ul>` — which reads like a "scroll for more" affordance but isn't; it's just CSS overflow on a fixed 15-item list. There is no pagination call, no "view all notifications" link, and no dedicated notifications page anywhere in any role's nav. If a user (most likely `hr`, who receives contract-expiry + SLA + acknowledgment notifications constantly) accumulates more than 15 items without reading them, the 16th-oldest-and-beyond notifications are **permanently unreachable** through the UI, even though they still exist in the database and are marked unread server-side.

### B8 — Employee cannot download or view their own official evaluation PDF anywhere in the app
**Role:** `employee`. **Page:** `/me` ("کارنامه من").

**Code:** `backend/app/api/routers/me.py`'s module docstring states the design explicitly: *"کارمند... به پرونده کامل دسترسی ندارد... فقط خلاصه نتیجه نهایی‌شده را می‌بیند"* (the employee doesn't get the full record — only a summary). `_ensure_can_view` in `evaluations.py` (used by both `GET /evaluations/{id}` and `/summary.pdf`) checks membership in `{unit_supervisor_user_id, deputy_user_id, ceo_user_id}` — an `employee`'s own user ID is never in that set, so **the employee-role user literally cannot hit the PDF endpoint for their own evaluation; it will 403.** `MyEvaluationsPage.tsx` has no PDF/download/print button anywhere in `MyEvaluationCard`.

**Why this is worth flagging even though it's "intentional":** the finalized-evaluation PDF (with QR code) is the actual official, printable artifact this whole system exists to produce — and the one person it's *about* has no way to get a copy of it from the app they're required to log into and click "رؤیت شد" (acknowledge) on. They can acknowledge a document they can never actually see the full rendered form of.

## 2. UX problems (technically working, but confusing/inconsistent/frustrating)

### U1 — No autosave and no unsaved-changes warning on the scoring form
`ScoreForm.tsx`/`useScoreForm` keeps all evidence text in local React state only; no debounced call to the existing draft-save endpoint (`PUT /evaluations/{id}/scores`) exists anywhere in `EditableScoring`. A supervisor writing detailed 15-plus-word evidence for a dozen indicators (the evidence-length rule is enforced hard by the backend — see `validate_evidence`) can lose all of it to an accidental back-button, a sleeping laptop, or a session timeout, with zero warning. There's also no `beforeunload`/router-blocking guard.

### U2 — Inconsistent "what happens to a case after I act on it" mental model across roles
Combining B1–B4: a `unit_supervisor` who submits an evaluation *can* still track it afterward (their "ارزیابی‌های من" list shows all statuses) — but a `deputy` or `ceo` who approves/finalizes a case cannot. The same underlying `EvaluationList` component silently behaves completely differently depending on which page happens to be embedding it, which will read as arbitrary/broken to users who compare notes across roles ("my supervisor can still see old cases, why can't I?").

### U3 — The "return case" flow gives no visibility into consequences before confirming
`ReturnBox` in `EvaluationDetailPage.tsx` requires a reason (good — the submit button is `disabled={sending || !reason.trim()}`), but there is no confirmation dialog on this action (unlike approve/finalize, which correctly use `useConfirm()`). A `return` sends the case back a full workflow stage and notifies people — arguably as consequential as an approval, yet it has less friction/confirmation than approving does.

### U4 — Manager-path special case is invisible in the UI until you already understand the business rule
The `is_manager` flag on Personnel triggers a genuinely different workflow (deputy scores directly, no supervisor stage) — documented extensively in backend comments, but on the frontend it surfaces only as a small amber "مدیر" pill next to the job title in HR's `PersonnelPage`, and as the *absence* of a supervisor-related field elsewhere. Nothing in `EvaluationDetailPage`'s status/stage display explains *why* a given case skipped the supervisor stage.

### U5 — Two visually distinct search/filter idioms with no filter for the thing users most likely want to filter by
`EvaluationList` has a single text search box covering both evaluation code and personnel name. It has no way to filter by org unit, by evaluator, or by date range — for HR trying to answer "show me everyone in Sales still in `draft`," today's only lever is that fixed status per page (which, per B1-B4, HR can't even change) plus free text.

### U6 — Password-change "forced" state and normal state look nearly identical
`ChangePasswordPage.tsx` shows a single amber sentence of copy difference between "your password is temporary, you must change it" (forced) and normal voluntary password change — no distinct visual treatment (banner color, icon, disabled navigation elsewhere) beyond that one line of text, even though `Layout.tsx` is silently hard-redirecting the user here and blocking all other navigation.

### U7 — PDF button appears/disappears based on status with no explanation of when it *will* appear
In `EvaluationDetailPage.tsx`, the "چاپ / خروجی PDF" button is conditionally rendered only `evaluation.status === "finalized"`. For any other status, the button simply doesn't exist — there's no disabled/greyed-out version with a tooltip like "available once finalized," so a user checking back on a pending case has no visual cue that this feature exists at all until the exact moment it appears.

## 3. Gaps / missing functionality

- **No global "search everything" or command palette** — finding a specific person or case requires knowing which role-specific page to be on and (per B1–B4) often can't be done at all if the case has moved past that page's hardcoded status.
- **No bulk actions anywhere.** HR approving during a deadline crunch, or a supervisor starting evaluations for many subordinates at once, must do so one row/one modal at a time.
- **No case timeline/activity view.** `EvaluationDetailPage` shows the current comment thread but not a unified chronological history of every status change (that data already exists richly in `AuditLog`, browsable HR-wide on a separate page, but not surfaced per-record).
- **No keyboard shortcuts** for the repetitive approve/return/comment review loop.
- **No confirmation-dialog consistency** — approve/finalize use `useConfirm()`, return does not (see U3); worth a full audit pass for consistency once this is running live.
- **No visible focus management in `Modal.tsx`** — no focus trap, no restore-on-close — directly undermines a "click every button with a keyboard" test.
- **No "why can't I do X" messaging.** Every gating check traced (role, status, assignee) fails with a generic 403/400 toast (`extractErrorMessage`) rather than a contextual explanation baked into the disabled UI state itself.
- **No employee-facing PDF/export** (see B8) — worth listing here too as a missing feature, distinct from the bug framing above.
- **No org-unit/date/evaluator filters** on any evaluation list (see U5).

---

# PART 2 — Comprehensive UI/UX Upgrade Plan

## A. Prioritized Roadmap

**Tier 0 — Critical, fix immediately (breaks core workflows for the top of the org chart)**
1. **Fix B4 (root cause) → cascades to fixing B1, B2, B3.** Turn `EvaluationList`'s `statusFilter` into user-controlled state (a segmented control or tabs: "در انتظار من / همه / نهایی‌شده") instead of a prop the parent page locks. This single component fix repairs the CEO's, Deputy's, and HR's biggest functional hole in one place.
2. **Give every role a persistent, always-available personnel profile view (fix B5/B6).** Extract HR's `EmployeeProfileModal` pattern into a shared component, and open the trend/radar endpoints to `unit_supervisor`/`deputy`/`ceo` scoped to *their own* subordinates (not all personnel) — a straightforward backend permission change (`require_roles` → a custom dependency checking `EvaluationAccess`/`EvaluationRecord` involvement, mirroring `_can_view_personnel`'s existing logic in `personnel.py`).
3. **Give the employee role a PDF download (fix B8).** Add a narrowly-scoped endpoint (or reuse `/summary.pdf` with an employee-specific permission branch) so the person the evaluation is *about* can get their own official document.

**Tier 1 — High-value UX fixes**
4. Autosave for evidence/scoring (U1) + unsaved-changes guard.
5. Confirmation dialog on "return case" (U3), matching approve/finalize.
6. Notification inbox pagination + a dedicated "all notifications" view (fix B7).
7. Modal focus trap + focus restoration.

**Tier 2 — Visual/design modernization**
8. Design system consolidation (below).
9. Visual workflow stepper replacing text status badges.
10. Manager-path explanatory UI (U4).

**Tier 3 — Nice-to-haves**
11. Command palette, bulk actions, keyboard shortcuts, case timeline view, dark mode, richer filters (org unit/date/evaluator).

## B. Structural issue to call out explicitly

**Permission/visibility logic is tied to hardcoded per-page workflow-stage props, not to role-level capability.** This is the single deepest issue Part 1 surfaced, and it's a pattern, not a one-off bug: `EvaluationList` is a generic, capable, well-built component (search + pagination + backend-supported status filtering) that three different pages neuter by locking it to one status via a prop. The fix isn't "add a history page to each of Deputy and CEO" (that would just create three more slightly-different bespoke pages) — it's **moving the filter control into the shared component itself**, so that "what can this role see" is answered once, consistently, everywhere `EvaluationList` is used. The same underlying pattern (a capability that exists at the API/data layer being exposed through only one narrow, hardcoded lens on the frontend) also explains B5/B6 (personnel profile data exists and is fetched, but only one page renders it) and B7 (notification data exists, only 15 are ever surfaced). Treat "audit every place a component silently narrows what the backend actually allows" as a standing engineering principle coming out of this review, not just three isolated tickets.

## C. Proposed Design System

**Color:**
- Primary brand gradient (already established): `pulse-500 → pulse-violet-600`. Keep as the single "primary action" identity — don't introduce a second brand hue.
- Semantic status colors need a documented, enforced palette instead of ad hoc Tailwind classes scattered per component: `draft` = gray, `submitted`/`hr_approved`/`deputy_approved` = amber (in-progress family, differentiated by icon/label not new hues), `finalized` = green, `returned` = red/amber blend. Every one of these must pair color with a text label and an icon — never color alone.
- Establish a neutral gray scale as the base for all cards/borders (already mostly `gray-50`–`gray-100`/`gray-800` — just needs a documented token list, e.g. in a `tailwind.config`/CSS-vars sheet, so future components don't reinvent slightly-off grays).

**Typography:** Vazirmatn (already self-hosted, good RTL choice) at three weights (400/500/700) is sufficient — codify a type scale: `text-xs` (11–12px) for meta/labels, `text-sm` for body/table content, `text-base`/`text-lg`/`text-xl` for headers, `font-bold` reserved for page titles and key numbers only.

**Spacing:** The existing `rounded-2xl`/`rounded-xl` + `shadow-card` card idiom, `p-4`/`p-5` card padding, and `gap-2`/`gap-3` between elements are consistent across the pages traced — formalize these as named tokens (`--radius-card`, `--shadow-card`, `--space-card-padding`) rather than repeated literal Tailwind classes, so a future redesign is a token change, not a find-and-replace across 40 files.

**Component patterns to standardize (directly from what was found inconsistent):**
- **One `<EntityList>` pattern** (search + optional status/filter controls + pagination + empty state) that `EvaluationList`, `PersonnelPage`'s table, and `UsersPage` all consume, instead of three parallel hand-rolled tables.
- **One `<ProfileModal>`** (the HR `EmployeeProfileModal` pattern) reused for any role permitted to see it, rather than being HR-page-specific code.
- **One confirmation pattern** for *every* destructive/consequential action (approve, finalize, return, deactivate-user) — audit and apply `useConfirm()` uniformly.
- **One status representation** — replace the `StatusBadge` + separate `STAGE_LABELS` text pairing with the visual stepper proposed below, used identically on `EvaluationDetailPage`, `EvaluationList` rows, and the HR dashboard's pipeline widget.

## D. Redesign proposals for the weakest screens

**1. `EvaluationList` (and by extension `CeoHomePage`/`DeputyHomePage`/`QueuePage`):**
Replace the current fixed-title-plus-hardcoded-filter pattern with a single reusable page shape:
- Segmented tabs at the top: **در انتظار من** (default, current behavior) / **همه پرونده‌های من** / **نهایی‌شده**. Each tab maps to a `status` value (or `undefined` for "all") passed into the *existing* `useEvaluations` hook — no backend change needed, since it already supports arbitrary status filters per role.
- Add an org-unit dropdown and a date-range picker (Jalali, reusing the existing `JalaliDatePicker`) next to the search box.
- Row click anywhere (not just the "مشاهده" button) navigates to detail — reduces target-size frustration.

**2. Supervisor/Deputy "personnel" tables (`SupervisorHomePage`, `DeputyHomePage`):**
- Make `full_name` a real link/button opening the shared `<ProfileModal>` (identical to HR's), showing job title, org unit, contract dates, and — once B6 is fixed — the radar/trend charts scoped to that supervisor's own subordinate.
- Add a small inline status chip per row: "ارزیابی باز دارد" / "بدون ارزیابی فعال" / "ارزیابی این دوره تکمیل شده" so the "شروع ارزیابی جدید" button's behavior (new vs. resume) is predictable before clicking, not discovered via a 409 redirect after the fact.

**3. `EvaluationDetailPage`'s action area:**
- Add the visual stepper (Supervisor → HR → Deputy → CEO → Finalized) at the top, with the manager-path variant explicitly shown as a collapsed/skipped step with a small "چون این فرد «مدیر» است، این مرحله حذف شده" tooltip — directly resolving U4.
- Wrap "برگشت پرونده" (return) in the same `useConfirm()` pattern as approve/finalize (resolving U3), and add a live character/word counter to the reason textarea mirroring the evidence-field UX already built for scoring.
- Show a disabled "چاپ / خروجی PDF" button with a tooltip ("پس از نهایی‌سازی در دسترس است") at every stage instead of omitting it entirely, resolving U7.

**4. `MyEvaluationsPage` (employee):**
- Add a "دانلود PDF رسمی" button per finalized card once B8's backend permission is added.
- Consider surfacing the QR-verification link itself here too, since it's already public — there's no reason the employee shouldn't get the same "share/verify" link that ends up on their printed document.

**5. `NotificationBell`:**
- Add a "مشاهده همه اعلان‌ها" link at the bottom of the dropdown routing to a real `/notifications` page with its own pagination, resolving B7, and reconcile the unread badge count against what's actually fetched so the badge number can never exceed what's clickable.

## E. UX pattern changes stemming directly from Part 1

- **Filter/visibility state must live in shared components, not page-level props** — see section B above; this is the biggest single architectural change to make.
- **Every gating decision needs a *visible* reason, not just an absent control or a post-click error toast.** Concretely: prefer "disabled button + tooltip explaining why" over "button doesn't render," and prefer "button doesn't render + explanatory empty state" over "button renders, click fails with a generic toast."
- **Confirmation-dialog usage needs a single rule, applied uniformly:** any action that changes workflow state, sends a notification, or is irreversible gets `useConfirm()` — no exceptions decided page-by-page.
- **Any list showing a person's name should make that name a live entry point to a profile view, full stop** — this should be a lint-able/reviewable convention going forward given how many places independently violated it.

## F. Additional polish for a "professional, modern enterprise tool" feel

- **Case timeline component** reusing the already-rich `AuditLog` + `EvaluationComment` data, rendered as a vertical activity feed on `EvaluationDetailPage` — this alone would make the tool feel significantly more transparent and trustworthy for a process this consequential to someone's job.
- **Command palette (⌘K)** given how role-siloed navigation currently is — most valuable for HR, who juggles the most sections.
- **Bulk-approve** for HR's queue once B3 is fixed and a real "browse all" view exists — batch-approving a stack of well-scored, unremarkable cases during a renewal deadline is exactly the workflow this tool should optimize for and currently doesn't at all.
- **Dark mode**, given how long HR staff likely have this dashboard open during evaluation season.
- **A visible "why can I / can't I do this" affordance pattern app-wide**, since nearly every UX finding above ultimately traces back to *invisible* permission/state logic rather than *broken* permission/state logic — the backend rules are almost all correct and well-tested; the frontend simply doesn't surface them legibly enough for users to build an accurate mental model of the system.
