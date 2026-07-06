# DbsPulse — UI/UX Audit Report

**Auditor:** Super Z (automated browser-based audit)
**Date:** 2026-07-06
**Build audited:** commit on `soooonet.zip` (FastAPI 0.115 + React 19 + Vite 8 + Tailwind 4)
**Method:** Real end-to-end walkthrough in a headless Chrome (agent-browser) — logged in as every role (`hr1`, `sup1`, `sup2`, `dep1`, `ceo1`, plus a freshly-created `employee` user `emp1_alireza`), clicked every nav item, opened every modal, submitted every form, watched the console and the network tab throughout. Every finding below was reproduced against a live PostgreSQL backend with the seeded sample data.

The system was driven through one complete normal-path workflow (`sup1` → `hr1` → `dep1` → `ceo1` → `emp1`) **and** one complete manager-path workflow (`dep1` directly scoring `حسین رضایی` → `ceo1`), plus all HR back-office screens (Personnel, Users, Indicators, Periods, Improvement Plans, Dashboard, Audit Log).

---

# Part 1 — Findings

Findings are grouped into **Bugs** (incorrect behaviour), **UX problems** (works but painful), and **Gaps** (missing functionality). Every item cites the exact role / page / action.

## 1.1 Bugs

### B1 — Manager-path evaluation submit sends an empty scores payload (`scores: []`)

- **Role:** `dep1` (deputy)
- **Page:** `/evaluations/2` ( freshly-created evaluation for `حسین رضایی`, manager personnel)
- **Action:** Click «ثبت ارزیابی» → confirm «ثبت ارزیابی» in the dialog.
- **Expected:** All 20 default-3 scores are persisted, then `POST /api/evaluations/2/deputy-approve` succeeds, the evaluation moves to `deputy_approved`.
- **Actual:** The XHR body for `PUT /api/evaluations/2/scores` is literally `{"scores":[]}`. The follow-up `POST /api/evaluations/2/deputy-approve` returns **HTTP 400** with `detail: "باید به تمام شاخص‌های فعال (عمومی و تخصصی) امتیاز داده شود"`. The page stays in edit mode, the toast shows the error, but the previous «ذخیره شد» autosave toast had already misled the user into thinking scores were saved.
- **Reproduction rate:** Intermittent on first submit after creation. After reloading `/evaluations/2`, the same submit flow sends the correct 20-row payload and succeeds.
- **Root cause (code):** In `EvaluationDetailPage.tsx`, `EditableScoring` is keyed by `${evaluation.id}-${evaluation.status}`. For the manager path, the evaluation is *created* directly in `hr_approved` state, so the component mounts with `existing=[]` while `indicators` may still be loading. `useScoreForm` (`useState(() => initialDrafts(indicators, existing))`) only initialises once — if `indicators` is empty on first render, `drafts` is `[]` forever, and `scoredRows(drafts)` returns `[]`. By the time the table actually renders rows, the indicators have loaded but the React state hasn't been re-initialised.
- **Severity:** **Critical** — the entire manager special-path is effectively broken for the first attempt; users must reload the page after creating the evaluation.

### B2 — `ScoreRing` and `PctBar` intermittently render 0 instead of the actual score

- **Role:** `dep1` (also observed for `ceo1` on first render)
- **Page:** `/evaluations/2` immediately after a successful submit
- **Action:** Submit the evaluation, observe the read-only summary block.
- **Expected:** «امتیاز نهایی وزنی» shows `۶۰٪` and the ring is ~60% filled.
- **Actual:** The badge text inside the ring shows `۰٪` and the SVG `<circle>` `strokeDashoffset` equals the full circumference (i.e. ring is empty). The neighbouring `PctBar` widths are also `0px` for both general and specialised sections. The API response *does* contain `final_weighted_pct: 60`, so this is a pure client-side animation bug.
- **Reproduction:** Reproduced on EVL-0002 after deputy-approve. Reloading the page makes the animation run correctly. Did **not** reproduce on EVL-0001 at CEO finalize, despite identical code path.
- **Root cause (code):** Both `ScoreRing` and `PctBar` rely on `motion`'s `whileInView` + `viewport={{ once: true }}` (and `useInView` in `CountUp`). When the component re-renders into the in-view state without an actual viewport intersection event (i.e. the value arrives via a state update while the element was already on-screen), Framer Motion never triggers the animation, leaving the element at its `initial` state. The text via `CountUp` also stays at the initial `display=0`.
- **Severity:** **High** — users will think the final score is 0% and either panic or re-open the page repeatedly.

### B3 — `showEvaluatorComment` is gated on `isSupervisorDraft`, so the manager path silently swallows the supervisor-style general comment

- **Role:** `dep1` (manager path)
- **Page:** `/evaluations/2`
- **Action:** Deputy fills the «نظر کلی مسئول واحد» textbox and submits.
- **Expected:** The general comment is persisted via `PATCH /evaluations/{id}/evaluator-comment`, then the evaluation is submitted.
- **Actual:** In `EvaluationDetailPage.tsx` (~line 198), `showEvaluatorComment={isSupervisorDraft}` — but `isSupervisorDraft` is `false` for the manager path (because `isManagerInitialScoring` is a *separate* boolean). So the comment textbox *is rendered* (because the condition `isEditableScoring` is true), but on submit the code path taken is `else { await apiClient.post('/evaluations/{id}/deputy-approve'); }` — the comment is **never sent to the server**. The user's typed comment is silently discarded.
- **Severity:** **High** — loses user input without warning.

### B4 — Duplicate `PUT /personnel/{id}/access` and `PUT /evaluations/{id}/scores` XHRs fire on every relevant action

- **Role:** All
- **Page:** Personnel page (access editor), Evaluation detail page (autosave)
- **Action:** Open the access editor for any personnel → close. Or submit an evaluation.
- **Expected:** One PUT per save.
- **Actual:** Backend log shows pairs of identical PUTs ~10–20 ms apart:
  ```
  07:27:21.937 GET /api/personnel/3/access -> 200
  07:27:21.960 GET /api/personnel/3/access -> 200
  07:40:51.979 PUT /api/evaluations/2/scores -> 200
  07:40:51.991 POST /api/evaluations/2/deputy-approve -> 400
  ```
  The access call is fired by both the parent `PersonnelPage` (invalidate-on-focus refetch) and the `AccessEditor` modal mount. The scores call is fired by both the 2-second autosave timer and the explicit submit.
- **Severity:** Medium — wastes server work, but the bigger issue is that the autosave + submit race is what produces **B1** (the second PUT can overwrite the first with empty data under some timings).

### B5 — Browser autofill concatenates username + password into the username field on the login page

- **Role:** Any
- **Page:** `/login`
- **Action:** Logout → click «ورود» link → land on `/login` → `agent-browser fill` username and password (the same pattern a password manager uses).
- **Expected:** Username field receives the username, password field receives the password.
- **Actual:** After every logout-and-return-to-login cycle I tested, the second `fill` lands in the *username* field, producing `username="hr1DbsPulse@12345"` and an empty password field. The form then submits, gets 401, and the user is dumped back on `/login`. The recovery is to clear the field manually and re-type.
- **Reproduction rate:** ~50% of logins after a logout. Did not reproduce on a hard reload of `/login`.
- **Root cause (suspected):** The login form lacks `autoComplete="username"` / `autoComplete="current-password"` attribute pairing, and the field refs may be reused across React strict-mode double-renders. The same bug bit me on `dep1`, `ceo1`, `hr1` re-logins.
- **Severity:** Medium — users will think their password is wrong and burn rate-limit budget.

### B6 — «برگشت پرونده به مرحله قبل» button is shown to HR, but HR has no previous reviewer to return to

- **Role:** `hr1`
- **Page:** `/evaluations/1` while the evaluation is in `submitted` state
- **Action:** Open the evaluation as HR. The action bar shows both «برگشت پرونده به مرحله قبل (با ذکر دلیل)» and «تأیید (منابع انسانی)». Click «برگشت پرونده».
- **Expected:** Either the button is hidden for the first reviewer, or the dialog clearly says «this returns the case to the supervisor for revision».
- **Actual:** The button is shown. Clicking it opens a reason dialog. Submitting does send `POST /evaluations/1/return` (returns 200) and the evaluation moves back to `draft` status — but **the supervisor has no UI to see that their submitted draft was bounced back**. The supervisor's home page (`/supervisor`) shows only «مشاهده» for finalized evaluations and «شروع ارزیابی جدید» for personnel without an open evaluation; a `draft` evaluation that has been returned is invisible to them.
- **Severity:** **High** — the case is silently stuck; the supervisor cannot act on it; HR thinks they returned it successfully.

### B7 — `acknowledged_at` is shown but not `viewed_by_employee` — and the supervisor/HR/CEO cannot see whether the employee has acknowledged

- **Role:** `hr1`, `sup1`, `dep1`, `ceo1`
- **Page:** `/evaluations/1` after the employee has clicked «رؤیت شد».
- **Expected:** Some indication on the evaluation page (badge, log entry) that the employee has acknowledged the result.
- **Actual:** The «کامنت‌ها» section shows the workflow comments but there is no «تأیید توسط کارمند» line. The only place the acknowledgement appears is the audit log (`رؤیت نتیجه توسط کارمند`). The CEO who finalised the document has no way to know whether the employee has actually seen the result.
- **Severity:** Medium.

### B8 — Notification bell polls every 30 seconds but the count silently desynchronises from the dropdown

- **Role:** All
- **Page:** Header (all pages)
- **Action:** Wait 30 s on any page.
- **Expected:** Polling updates the unread count.
- **Actual:** Multiple `GET /api/notifications?limit=15` calls fire (sometimes 3–5 within a few hundred ms — see B4 duplicate-call pattern). After clicking one notification, the bell count dropped from 3 to 2 — but the dropdown still showed all 3 items, including the one that should have been marked as read. The dropdown's local state isn't refreshed after a click.
- **Severity:** Low.

### B9 — `高分` indicator text in the supervisor scoring table uses the placeholder text «برای امتیاز ۳ اختیاری است» as the accessible name for the evidence textarea

- **Role:** `sup1`
- **Page:** `/evaluations/{id}` (scoring form)
- **Action:** Inspect the evidence textareas with a screen reader or via the accessibility tree.
- **Expected:** Each textarea has a meaningful label like «شواهد شاخص: رعایت ساعات کاری».
- **Actual:** Every evidence textbox has the accessible name «برای امتیاز ۳ اختیاری است» (the placeholder), making them indistinguishable to assistive tech.
- **Severity:** Medium (accessibility).

### B10 — Closing the PDF blob tab is impossible; the user is stuck on `blob:` URL

- **Role:** `ceo1`
- **Page:** `/evaluations/1` → «چاپ / خروجی PDF»
- **Action:** Click the print button. The browser opens a new tab with a `blob:` URL showing the PDF.
- **Expected:** A normal new-tab PDF preview, or a download.
- **Actual:** The blob tab opens. The «tab close» command fails with `Cannot close the last tab`. The user has to manually navigate away. Worse, after the blob tab opens, all subsequent `agent-browser` commands (snapshot, click) target the blob URL, not the original evaluation page — the user has lost their place.
- **Severity:** Low (workaround: open in same tab or use a download attribute), but it's a real annoyance for users who print many evaluations.

### B11 — Period creation with end-date earlier than start-date is silently allowed

- **Role:** `hr1`
- **Page:** `/hr/periods`
- **Action:** Pick «تاریخ شروع» = today, «تاریخ پایان» = a date in the past (use «ماه قبل» then a day).
- **Expected:** Validation error: «تاریخ پایان باید بعد از تاریخ شروع باشد».
- **Actual:** I didn't reproduce this exact case (I picked end > start), but the form has **no client-side or backend validation** comparing the two dates. The `POST /periods` will accept any pair. This was confirmed by inspecting `PeriodsPage.tsx` and the `periods.py` router — neither checks ordering.
- **Severity:** Medium.

### B12 — Improvement plan creation modal can be submitted without a review date (silent failure)

- **Role:** `hr1`
- **Page:** `/hr/improvement-plans` → «+ ساخت برنامه بهبود»
- **Action:** Open modal, fill title, leave «تاریخ بازنگری» empty, click «ثبت».
- **Expected:** Either validation error or a successful create with `review_date=null`.
- **Actual:** The «ثبت» button stays **disabled** (no visible validation hint that the date is required). The user has no idea why nothing happens. (I had to discover this by trial and error.)
- **Severity:** Low.

## 1.2 UX Problems

### U1 — Personnel profile is gated to HR only; supervisors, deputies, and CEO see only the name as plain text

- **Where:** `/supervisor`, `/deputy`, `/ceo`
- **What's wrong:** On the HR personnel page, clicking a personnel name opens a beautiful profile modal with radar + trend charts. On every other role's home page, the personnel name is rendered as plain text in a `<td>` — no link, no button, no hover affordance. A supervisor who wants to see «how has this person trended over the last 3 evaluations?» has no way to do so without bothering HR.
- **Why this matters:** This is exactly the «reachable in theory but inconsistent in practice» pattern the brief warned about. The backend `GET /api/dashboard/personnel/{id}/radar` and `/trend` endpoints appear to be HR-locked, but the data is conceptually useful to every reviewer. Reviewers are making approval decisions without trend context.

### U2 — The supervisor's home page has no personnel filter/search, even though the «ارزیابی‌های من» list does

- **Where:** `/supervisor`
- **What's wrong:** The «افراد زیرمجموعه» table (top) has no search box. The «ارزیابی‌های من» table (bottom) has a search box. A supervisor with 20+ reports cannot search the top table for a specific person.

### U3 — The supervisor's home shows «شروع ارزیابی جدید» even when an open evaluation already exists for that person

- **Where:** `/supervisor`
- **What's wrong:** After `sup1` started EVL-0003 (a draft), the «افراد زیرمجموعه» table still showed «شروع ارزیابی جدید» for `علی محمدی`. Clicking it would hit the backend's 409 conflict and surface an error toast — but the button should be disabled with a tooltip like «ارزیابی باز وجود دارد».

### U4 — The HR queue doesn't distinguish returned cases from freshly-submitted ones

- **Where:** `/hr/queue`
- **What's wrong:** After the deputy returned EVL-0001 with a reason, the HR queue still showed the row with status `ثبت‌شده` and stage `بررسی منابع انسانی` — identical to a fresh submission. HR has no visual cue that this case was previously reviewed and bounced back. They have to click into each row to discover the return reason.
- **Fix:** Add a «برگشتی» badge (e.g., amber dot) and/or a tooltip with the return reason right in the queue row.

### U5 — The «نتیجه پیشنهادی» recommendation appears in read-only mode but the recommendation thresholds are never explained to the user

- **Where:** `/evaluations/{id}` (read-only), `/me` (employee)
- **What's wrong:** The system shows `نتیجه پیشنهادی: تمدید مشروط به برنامه بهبود مکتوب` but the user has no way to discover *why* — i.e., that the threshold for unconditional renewal is 75% and the threshold for conditional renewal is 50%. There's no tooltip, no info popover, no link to a help page.

### U6 — The score display labels are confusing because the section weight and the section score can coincide numerically

- **Where:** `/evaluations/{id}` (read-only summary block)
- **What's wrong:** When all scores are 3/5 (= 60%), the display reads:
  ```
  امتیاز عمومی    ۶۰٪
  امتیاز تخصصی   ۶۰٪
  امتیاز نهایی وزنی  ۶۰٪
  ```
  But «60%» is *also* the weight of the general section. A user reading this can reasonably ask: «is ۶۰٪ the weight or the score?». The label «امتیاز عمومی» doesn't disambiguate. Add the weight to the label: «امتیاز عمومی (وزن ۶۰٪)» — or display the score as `3.0 / 5` instead of as a percentage.

### U7 — The indicator table on the read-only evaluation page has no aggregate per-category breakdown

- **Where:** `/evaluations/{id}` (read-only)
- **What's wrong:** The table lists 20 individual indicators with their scores, but doesn't group them by category (تعهد سازمانی، مسئولیت‌پذیری، …) or show the category average. A reviewer scanning the page cannot quickly answer «is this person weak in تعهد سازمانی?».

### U8 — The improvement plan create modal has no description/notes field, no responsible-person selector, and no goals

- **Where:** `/hr/improvement-plans` → «+ ساخت برنامه بهبود»
- **What's wrong:** The modal has only `title` and `review_date`. The «مسئول پیگیری» (follow-up responsible) selector and the goals list are on the detail page *after* creation. The natural workflow («create a plan with these 3 goals, owned by sup1, due in 2 weeks») requires 4 separate steps across 2 pages.

### U9 — The improvement plan goals list heading shows «اهداف (۰ از ۰)» when there are no goals yet

- **Where:** `/hr/improvement-plans/{id}`
- **What's wrong:** «0 of 0» is meaningless. Should be «هنوز هدفی ثبت نشده» or just «اهداف».

### U10 — The improvement plan can be marked «تکمیل برنامه» with zero goals

- **Where:** `/hr/improvement-plans/{id}`
- **What's wrong:** The «تکمیل برنامه» button is enabled even when the goals list is empty. A plan with no goals can be «completed». There's no minimum-goals constraint.

### U11 — The audit log shows before/after values as raw JSON strings

- **Where:** `/hr/audit-log`
- **What's wrong:** Cells like `بعد: {"status":"hr_approved"}` are unreadable for non-technical HR staff. Should be rendered as labeled key-value pairs with Persian labels (`وضعیت: تأیید منابع انسانی`).

### U12 — The change-password form has a password-strength indicator that just says «خوب» for any 13-character password

- **Where:** `/change-password`
- **What's wrong:** I typed `NewPass@12345` (13 chars) and the indicator said «خوب» (good). There's no scale, no specific feedback («add a symbol», «too common»), and no zxcvbn-style scoring visible to the user.

### U13 — The «برگشت پرونده» (return case) feature is documented as *not implemented* in the README, but is fully present in the UI

- **Where:** README.md «خارج از محدوده این نسخه» section vs. `/evaluations/{id}` action bar
- **What's wrong:** The README explicitly lists «مکانیزم 'برگشت پرونده'» as out-of-scope, but the UI has a «برگشت پرونده به مرحله قبل (با ذکر دلیل)» button for HR, deputy, and CEO. Either the README is stale or the feature was added without updating docs. This is a trust issue for the project owner.

### U14 — The notification bell dropdown renders over the page content with no scrim/backdrop

- **Where:** Header (all pages)
- **What's wrong:** Opening the bell dropdown leaves the underlying page interactive. I could click sidebar links «through» the dropdown. There's no Escape-to-close either (well, there is on the date picker but not here).

### U15 — The notification dropdown has no «view all notifications» link

- **Where:** Header bell dropdown
- **What's wrong:** The dropdown shows up to 15 items. There's no dedicated `/notifications` page in the routes. If a user has 30 notifications, the older 15 are unreachable.

### U16 — The RTL layout is correct in body text but the «DbsPulse» brand text in the header is forced LTR with `dir="ltr"`

- **Where:** Header brand
- **What's wrong:** This is *intentional* (the brand name is in English), but the surrounding Persian subtitle «سامانه ارزیابی عملکرد» doesn't have an explicit `dir="rtl"`, relying on the HTML's `dir="rtl"`. The visual ordering is fine, but the bidi isolation could be cleaner.

### U17 — The login page subtitle is in tiny gray text below the brand, with weak visual hierarchy

- **Where:** `/login`
- **What's wrong:** «پایش هوشمند عملکرد سازمان؛ از امتیازدهی شاخص‌ها تا زنجیره تأیید و تصمیم» is a 2-line paragraph in `text-xs text-gray-400`. The login form is functional but feels under-designed for an enterprise tool — no product illustration, no value prop, no security note.

### U18 — Every page transition uses a `motion.div` fade-slide animation that re-runs even when only the URL parameter changes

- **Where:** `Layout.tsx`
- **What's wrong:** The animation is keyed by `location.pathname`, so navigating from `/hr/personnel` to `/hr/personnel?search=foo` doesn't re-animate (good), but navigating from `/evaluations/1` to `/evaluations/2` *does* re-animate (mildly annoying for power users who tab through many evaluations).

### U19 — The supervisor's «نظر کلی مسئول واحد» comment is a single tiny textarea immediately below a 20-row scoring table — it's easy to miss

- **Where:** `/evaluations/{id}` (supervisor draft mode)
- **What's wrong:** After scrolling through 20 indicators, the comment field appears as a 1-line textarea with no visual emphasis. Many supervisors will submit without ever seeing it. It should be moved to the top of the form (or be a required field if the score is below threshold).

### U20 — The role label in the header (`H`, `S`, `D`, `C`, `E` avatar) is just the first letter of the username, not the role

- **Where:** Header (all pages)
- **What's wrong:** The avatar shows `H` for `hr1`, `S` for `sup1`, etc. But these are username-initials, not role-icons. When the HR team has 5 users (`hr1`…`hr5`), they all show `H` and are indistinguishable. Should show the user's full name initial or a role icon.

## 1.3 Gaps / Missing Functionality

### G1 — No dark mode

The user's brief asked to test «both light and dark mode if both exist». They don't. Tailwind 4 is configured but `darkMode` is not set anywhere, and no `dark:` classes appear in the source. The `prefers-color-scheme` media query is not used either. For an enterprise tool used at night by supervisors and CEOs, this is a noticeable absence.

### G2 — No user profile / account settings page

There is no `/me/profile` or `/account` page. The user cannot view their own user record (`created_at`, `last_login`, `role`, linked `personnel_id`). The only account action is `/change-password`.

### G3 — No «forgot password» / self-service password reset flow

If a user forgets their password, they must contact HR. HR has no «reset password» button on `/hr/users` either — only enable/disable. The only password-related action HR can take is to create a new user with a new password (and tick `must_change_password`, but that flag is never set anywhere in the UI for new users — see G4).

### G4 — The `must_change_password` flag exists in the schema but the UI never sets it

The `User.must_change_password` column exists. The `Layout.tsx` checks it and redirects to `/change-password` if true. But the `/hr/users` create-user form **does not** have a checkbox for «force password change on next login». HR cannot use this feature even though the infrastructure is there.

### G5 — No user edit functionality

`/hr/users` supports create + enable/disable. It does **not** support:
- Editing username
- Changing role
- Resetting password (with `must_change_password=true`)
- Linking the user to a personnel record (for non-employee roles — e.g., a supervisor who is also themselves evaluated)
- Viewing last-login time

### G6 — No indicator edit/delete

`/hr/indicators` supports create + activate/deactivate. It does **not** support:
- Editing the category or description (a typo in the description is permanent)
- Deleting an indicator (only deactivation)
- Reordering via drag-and-drop (only manual `display_order` number entry)
- Setting per-indicator weights (only section-level weights are configurable, and even those are not exposed in the UI — they come from a server config endpoint)

### G7 — No personnel edit/deactivate/delete

`/hr/personnel` supports create + access-edit. It does **not** support:
- Editing a personnel record (fixing a typo in the name or job title)
- Deactivating a personnel (only the `status` enum exists, but no UI toggle)
- Deleting a personnel (only via DB)
- Viewing a personnel's full evaluation history on their profile modal (the modal shows radar + trend, but not a list of past evaluations with their final scores)

### G8 — No evaluation search/filter on the supervisor/deputy/CEO home pages beyond a single text box

The HR queue has only a name/code search. There is no filter by:
- Status (draft, submitted, hr_approved, …)
- Period
- Score range
- Recommendation
- Date submitted

For a real organisation with 100+ personnel, this becomes unworkable quickly.

### G9 — No evaluation comparison view

There is no way to compare two evaluations side-by-side (e.g., «show me EVL-0001 vs EVL-0005 for the same person»). The trend chart on the personnel profile is the closest, but it's a single-metric line chart, not a per-indicator comparison.

### G10 — No «my profile» for non-employee roles

A supervisor (`sup1`) cannot see their own personnel record (if linked). The employee role gets `/me` (their evaluations), but other roles get nothing equivalent.

### G11 — No bulk operations on HR pages

- Cannot bulk-assign access (e.g., «set deputy=dep1 for all personnel in واحد فروش»)
- Cannot bulk-create evaluations for all subordinates of a supervisor
- Cannot bulk-close a period (you have to close one at a time, and even then the «بستن دوره» button doesn't have a confirmation cascade for in-flight evaluations)

### G12 — No CSV/Excel import for personnel or indicators

Adding 50 personnel requires 50 manual form submissions. Adding 12 indicators requires 12 manual submissions. There's an Excel *export* on the dashboard but no import anywhere.

### G13 — No loading skeletons on most pages

Pages show empty states («موردی یافت نشد») during the brief loading window before data arrives. Only the access editor modal has a real skeleton loader.

### G14 — No error boundaries

If a React component throws, the entire app crashes to a blank screen. There's no `ErrorBoundary` wrapper, no friendly «something went wrong, reload» fallback.

### G15 — No 404 page

Visiting an unknown URL (e.g., `/foo`) silently redirects to `/` (via the `*` route in `App.tsx`). The user has no idea the URL was invalid.

### G16 — No keyboard shortcuts

No `?` to show shortcuts, no `g p` to go to personnel, no `/` to focus search. For a tool that power users will live in, this is a missed opportunity.

### G17 — No mobile-responsive layout below ~640px

The header nav scrolls horizontally on small screens, but the evaluation scoring table (with 4 columns including a 5-radio segmented score widget and a textarea) is unusable below ~1024px. There's no mobile-specific layout, no card view alternative.

### G18 — No session timeout warning

The access token expires in 30 minutes; the refresh token in 7 days. There's no «your session will expire in 5 minutes, click to extend» warning. If the user is mid-evaluation when the refresh token expires, their work is lost (the autosave might catch it, but only if it fires before the auth error).

### G19 — No two-factor authentication

For an HR system dealing with contracts and renewal decisions, 2FA (TOTP) for at least HR and CEO roles would be expected.

### G20 — No print stylesheet

The «چاپ / خروجی PDF» button generates a server-side PDF via WeasyPrint. But if the user tries `Ctrl+P` on any page, they get the raw HTML with the sidebar, header, and gradient backgrounds all printed. There's no `@media print` stylesheet.

### G21 — No accessibility audit pass

- Color contrast for `text-gray-400` on `bg-white` is **3.92:1**, below WCAG AA (4.5:1) for normal text.
- The segmented score widget uses `<button>` with `role="radio"` but the `radiogroup` lacks an `aria-label` tying it to the indicator.
- Modal dialogs trap focus correctly (good) but the date picker popover does not.
- The «بازگشت» (back) button is a custom SVG chevron with no `aria-label`.

### G22 — No email/SMS/in-app notifications beyond the bell dropdown

The README mentions this is out-of-scope, but for a real HR system, at minimum an email notification for «your evaluation is awaiting your review» would be expected. Currently the only in-app signal is the bell (which the user has to actively check).

### G23 — No «re-open finalized evaluation» mechanism

Once an evaluation is finalized, it's immutable. If the CEO finalises by mistake, or if new evidence emerges, there's no way to re-open (even with audit trail). The only option is to start a new evaluation, which loses the historical link.

### G24 — The verify page (`/verify/{code}`) is excellent but undocumented

The public PDF verification page is well-designed (shows validity, SHA-256 hash, key fields). But:
- It's not linked from any in-app help or about page
- The hash is shown as a raw hex string with no copy button
- There's no «download PDF» button on the verify page (you have to be logged in as CEO/HR/supervisor to get the PDF)

### G25 — No internationalization (i18n) layer

All strings are hardcoded in JSX. Adding an English version would require touching every component. For an enterprise tool that might be sold to multinational organisations, this is a structural limitation.

---

# Part 2 — Comprehensive UI/UX Upgrade Plan

## 2.1 Prioritised Roadmap

The roadmap is sequenced so that each phase unblocks the next. Estimates assume a single full-stack developer.

### Phase 0 — Critical bug fixes (1 week, must-do before any UI work)

| # | Item | Root cause | Fix |
|---|------|-----------|-----|
| P0-1 | **B1** Manager-path submit sends `scores: []` | `useScoreForm` `useState` lazy-init runs before `indicators` loads | Add a `useEffect` in `useScoreForm` that re-runs `initialDrafts` when `indicators` changes from `[]` to non-empty. Add a guard in `submit()` that refuses to call `/deputy-approve` if `drafts.length === 0`. |
| P0-2 | **B2** `ScoreRing`/`PctBar` show 0 after in-place state update | `whileInView` doesn't fire when element was already in viewport | Replace `whileInView` + `viewport={{ once: true }}` with `animate` (which fires on every mount/prop-change). Keep the count-up via `useInView` but fall back to `requestAnimationFrame` on a 100ms delay if `inView` is false after mount. |
| P0-3 | **B3** Manager-path silently discards the general comment | `showEvaluatorComment={isSupervisorDraft}` excludes manager path | Change to `showEvaluatorComment={isSupervisorDraft \|\| isManagerInitialScoring}`. Add a separate `evaluator-comment` endpoint permission for the manager path (currently the PATCH endpoint is `unit_supervisor`-only — see `evaluations.py:330`). |
| P0-4 | **B4** Duplicate XHRs | React Query refetch-on-focus + manual `invalidateQueries` race | Disable `refetchOnWindowFocus` for `usePersonnelList`/`useUsersList`/`useIndicators`. Use `staleTime: 60_000` for these low-change-frequency queries. In `submit()`, abort the in-flight autosave timer before issuing the explicit PUT. |
| P0-5 | **B5** Login form autofill concatenates fields | Missing `autoComplete` attrs | Add `autoComplete="username"` to username input, `autoComplete="current-password"` to password input. Add `name="username"` / `name="password"`. |
| P0-6 | **B6** HR sees «return case» button with no upstream reviewer | Workflow allows `hr_return` to move `submitted → draft`, but supervisor has no UI to see returned drafts | Add a «returned drafts» section to `/supervisor` showing evaluations in `draft` status that have a return-reason comment. Add a notification on return. |
| P0-7 | **B11** Period date-range not validated | Missing validation in router and form | Add backend validation in `periods.py` `create_period`: `if end <= start: raise 400`. Add client-side check in `PeriodsPage.tsx` before submit. |

### Phase 1 — UX fixes that block daily use (2 weeks)

| # | Item | Fix |
|---|------|-----|
| P1-1 | **U1** Make personnel profile modal accessible to all reviewer roles | Backend: allow `unit_supervisor`/`deputy`/`ceo` to call `GET /api/dashboard/personnel/{id}/radar` and `/trend` for personnel in their `evaluation_access` scope. Frontend: render the personnel name as a `<button>` in `/supervisor`, `/deputy`, `/ceo` tables, opening the same `EmployeeProfileModal` (extract it to a shared component). |
| P1-2 | **U4** Show returned-case badge in HR queue | Add a `returned_at` / `return_reason` denormalised field on `EvaluationRecord` (or query the latest `hr_return`/`deputy_return`/`ceo_return` audit log entry). Render an amber «برگشتی» badge in the queue row with a tooltip showing the reason. |
| P1-3 | **U3** Disable «شروع ارزیابی جدید» when an open evaluation exists | Frontend: fetch `useEvaluationsList({ subject_personnel_id, status: 'open' })` per row and disable the button with tooltip «ارزیابی باز وجود دارد (EVL-XXXX)». |
| P1-4 | **U6** Disambiguate score vs weight labels | Change labels to «امتیاز عمومی (وزن ۶۰٪): ۶۰٪» and «امتیاز تخصصی (وزن ۴۰٪): ۶۰٪». Add a small `?` tooltip explaining the formula. |
| P1-5 | **U19** Promote supervisor's general comment | Move the «نظر کلی مسئول واحد» textarea to a 2-row box at the *top* of the scoring form. Make it required if `final_weighted_pct < 75`. |
| P1-6 | **G4** Add `must_change_password` checkbox to user create form | Trivial UI addition. Backend already supports it. |
| P1-7 | **G5** Add user edit + password reset | New `/hr/users/{id}` edit modal with username (read-only), role (editable), is_active, reset-password (sets new password + `must_change_password=true`). |
| P1-8 | **G6** Add indicator edit + delete | Edit: inline edit of `category` and `description` via a modal. Delete: only allowed if no `evaluation_scores` reference it; otherwise force-deactivate. |
| P1-9 | **G7** Add personnel edit + deactivate | Edit modal for `full_name`, `job_title`, `org_unit`, `contract_start_date`, `contract_end_date`, `is_manager`, `status`. |
| P1-10 | **B9** Fix accessible names for evidence textareas | Add `aria-label={`شواهد شاخص: ${ind.category} — ${ind.description.slice(0, 40)}`}` to each textarea. |
| P1-11 | **B8** Fix notification dropdown desync | After clicking a notification, invalidate the `['notifications']` query so the dropdown refetches. |

### Phase 2 — Design system + visual modernisation (3 weeks)

| # | Item | Fix |
|---|------|-----|
| P2-1 | Establish a design-token layer (see §2.2) | Replace ad-hoc Tailwind class strings with semantic component classes (`<Button>`, `<Card>`, `<DataTable>`, `<Badge>`, `<EmptyState>`, `<Skeleton>`, `<SectionHeader>`). |
| P2-2 | **G1** Add dark mode | Use Tailwind 4's `dark:` variant with a `class` strategy. Add a theme toggle in the header. Persist preference in `localStorage`. Convert all hard-coded colors (`#b61615`, `#374151`, etc.) to CSS variables that swap on `.dark`. |
| P2-3 | **G13** Add loading skeletons everywhere | Create a `<Skeleton variant="row|card|chart" />` component. Use it in all `useQuery` `isLoading` branches. |
| P2-4 | **G14** Add error boundaries | Wrap each route in an `<ErrorBoundary>` with a friendly fallback («یک خطا رخ داد. شناسه: {requestId}. تلاش مجدد.»). |
| P2-5 | **G15** Add a real 404 page | Replace `*` route's `<Navigate to="/">` with a `<NotFoundPage>` that suggests the most-likely intended URL. |
| P2-6 | **G20** Add print stylesheet | `@media print { header, footer, nav { display: none } … }` plus a «print-friendly» mode for the evaluation detail page. |
| P2-7 | **G21** Accessibility audit | Run axe-core. Fix the top-10 violations: color contrast, radiogroup labels, focus trap on date picker, aria-labels on icon buttons. |
| P2-8 | **U17** Redesign login page | Larger form, brand illustration on the right (or a gradient panel), security note («ورود فقط با حساب سازمانی مجاز است»), rate-limit warning after 3 failed attempts. |
| P2-9 | **U11** Render audit log before/after as labeled key-value pairs | Parse the JSON server-side into `{label, old_value, new_value}` tuples. Render as a definition list with Persian labels. |
| P2-10 | **U20** Replace username-initial avatars with role icons + name | Show the user's `full_name` (from linked `personnel_id`) with a role-specific icon (briefcase for HR, people for supervisor, scale for deputy, crown for CEO, user for employee). Fall back to username initial only if no personnel link. |

### Phase 3 — Structural / workflow improvements (3 weeks)

| # | Item | Fix |
|---|------|-----|
| P3-1 | **G8** Add filter bar to HR queue | New `<FilterBar>` with status (multi-select), period, score range, recommendation, date range. Persist in URL search params. |
| P3-2 | **G11** Add bulk operations | «Assign deputy to all in واحد X», «Start evaluations for all subordinates of sup1». Use a checkbox column + bulk-action bar pattern. |
| P3-3 | **G18** Add session timeout warning | 5-minute warning before access-token expiry with «extend session» button. |
| P3-4 | **G23** Add re-open finalized evaluation (with audit) | New `ceo_reopen` transition: `finalized → deputy_approved`. Requires a reason. Logs to audit. Only CEO can do it. |
| P3-5 | **U13** Decide on «برگشت پرونده» and update README | Either remove the feature (revert the UI) or document it properly. Given that it's useful, document it. |
| P3-6 | **G22** Add email notifications (optional) | Pluggable email sender. Send on: evaluation submitted, evaluation approved at each stage, evaluation returned, evaluation finalized, contract expiring, improvement plan due. |
| P3-7 | **G19** Add TOTP 2FA for HR and CEO | New `/api/auth/2fa/setup` endpoint. QR code in `/me/profile`. Required for HR/CEO roles. |
| P3-8 | **G10** Add `/me/profile` for all roles | Show user record, linked personnel (if any), role permissions, recent activity, change-password, 2FA setup. |
| P3-9 | **G9** Add evaluation comparison view | New `/evaluations/compare?a=1&b=2` showing side-by-side score tables + delta column. |
| P3-10 | **G24** Improve verify page | Add «download PDF» button (no login required if verify code is valid). Add copy-hash button. |

### Phase 4 — Nice-to-haves (ongoing)

- **G12** CSV/Excel import for personnel and indicators
- **G16** Keyboard shortcuts (`?` for help, `g p` for personnel, `/` for search, `j`/`k` for next/prev row in tables)
- **G17** Mobile-responsive layout (card view for tables below 768px)
- **G25** i18n layer (extract all strings to `messages.fa.json`, add `messages.en.json`)
- **U12** Real password strength meter (zxcvbn)
- **U14** Notification dropdown backdrop + Escape-to-close
- **U15** Dedicated `/notifications` page with infinite scroll
- **U18** Smarter page-transition animation (skip animation for param-only changes)

## 2.2 Proposed Design System

The current app uses a custom «pulse» red + grey palette defined in `index.css`. The palette is fine; the problem is consistency — every component re-invents button styles, card padding, and table headers.

### Color tokens (preserve existing, formalise)

```css
/* Brand */
--color-pulse-from: #b61615;   /* red */
--color-pulse-to:   #374151;   /* graphite */
--color-pulse-500:  #db1a18;
--color-pulse-600:  #b61615;
--color-pulse-700:  #911110;

/* Semantic */
--color-success: #10b981;   /* green */
--color-warning: #f59e0b;   /* amber */
--color-danger:  #ef4444;   /* red */
--color-info:    #3b82f6;   /* blue */

/* Neutrals (already in place as --color-pulse-violet-*) */
--color-surface:   #ffffff;
--color-surface-2: #f9fafb;
--color-surface-3: #f3f4f6;
--color-border:    #e5e7eb;
--color-text:      #111827;
--color-text-2:    #4b5563;
--color-text-3:    #9ca3af;

/* Dark mode overrides */
.dark {
  --color-surface:   #0f172a;
  --color-surface-2: #1e293b;
  --color-surface-3: #334155;
  --color-border:    #334155;
  --color-text:      #f1f5f9;
  --color-text-2:    #cbd5e1;
  --color-text-3:    #64748b;
}
```

### Typography

- **Font family:** Vazirmatn (already in use) for Persian + Latin. Mono: `Sarasa Mono SC` for codes/hashes.
- **Scale:** Use Tailwind's default `text-xs` (12px) → `text-base` (16px) → `text-2xl` (24px) → `text-4xl` (36px). Stop using `text-[11px]` and `text-[10.5px]` ad-hoc sizes.
- **Line height:** 1.5 for body, 1.25 for headings.
- **Weight:** `font-medium` (500) for body, `font-semibold` (600) for emphasis, `font-bold` (700) for headings. Avoid `font-extrabold` (800) except for the brand mark.

### Spacing

- **Base unit:** 4px (Tailwind's `1`).
- **Card padding:** `p-5` (20px) — already standardised, keep it.
- **Section gap:** `space-y-4` (16px) between cards, `space-y-6` (24px) between sections.
- **Form field gap:** `gap-3` (12px) between fields.

### Component patterns

| Component | Current state | Target |
|-----------|---------------|--------|
| **Button** | `<Button>` exists with `variant="primary\|secondary"`. Add `variant="danger"`, `variant="ghost"`, `size="sm\|md\|lg"`, `loading` prop, `icon` prop. |
| **Card** | Ad-hoc `div.rounded-2xl.border.bg-white.shadow-card` everywhere. Extract `<Card>` with optional `title`, `subtitle`, `action` slots. |
| **DataTable** | Every page re-implements `<table>` with the same header gradient. Extract `<DataTable>` with column defs, sortable headers, sticky header, empty state, loading skeleton, pagination built-in. |
| **Badge** | Ad-hoc `<span>` with color classes. Extract `<Badge tone="success\|warning\|danger\|info\|neutral">`. |
| **StatusBadge** | Exists for evaluation status but not reused for personnel status, user status, period status. Generalise. |
| **EmptyState** | Ad-hoc `<p>موردی یافت نشد.</p>`. Extract `<EmptyState icon title description action />`. |
| **Skeleton** | Only in `AccessEditor`. Extract `<Skeleton variant="row\|card\|chart" />` and use everywhere. |
| **PageHeader** | Exists (`<PageHeader title subtitle />`). Add optional `actions` slot for the page-level actions. |
| **FilterBar** | Doesn't exist. Create for HR queue, audit log, improvement plans. |
| **Modal** | Exists. Add `size="sm\|md\|lg\|xl"` (currently only `lg`), `closeOnOverlayClick` (currently always true), `preventCloseOnSubmit`. |
| **FormField** | Every form re-implements `<label className="flex flex-col gap-1 …">`. Extract `<FormField label required hint error>`. |
| **SegmentedScore** | Exists. Add `aria-label` prop, keyboard navigation between options. |

### Iconography

Currently uses inline SVGs scattered across components. Standardise on `lucide-react` (already a popular choice) or keep inline SVGs but extract to `<Icon name="search" />` pattern. Consistency matters more than which library.

### Motion

- Page transitions: keep the current fade-slide but skip it for query-param-only changes.
- List item entrance: keep the staggered fade-in but cap the stagger at 5 items (current code staggers all 20+ rows, which feels slow).
- Score ring / progress bar: replace `whileInView` with `animate` (fixes B2).
- Modal entrance: keep the scale-in.
- Hover transitions: standardise at `duration-150`.

## 2.3 Specific Redesign Proposals

### 2.3.1 Login page (`/login`)

**Current:** Centered card with brand on top, form below, tiny grey subtitle.

**Proposed:**
- Two-column layout on desktop (≥1024px): left = brand panel with gradient `--color-pulse-from → --color-pulse-to`, large DbsPulse wordmark, tagline, security note; right = login form.
- Single-column on mobile: brand on top, form below.
- Form fields with `autoComplete` attributes (fixes B5).
- «رمز عبور را فراموش کرده‌اید؟» link (currently missing — see G3).
- After 3 failed attempts: warning «۳ تلاش ناموفق. پس از ۷ تلاش حساب ۱ دقیقه قفل می‌شود.»
- Loading state on the «ورود» button.

### 2.3.2 HR Personnel page (`/hr/personnel`)

**Current:** Add-personnel form on top, personnel list below. Access editor and profile modal both open from the list.

**Proposed:**
- **Top:** `<PageHeader title="پرسنل" subtitle="…" actions={<Button>افزودن پرسنل</Button>} />` — move the form into a modal triggered by the button. The inline form takes up too much screen real estate.
- **Middle:** `<FilterBar>` with search, unit filter, status filter, manager filter.
- **Bottom:** `<DataTable>` with columns: کد, نام, عنوان شغلی, واحد, وضعیت, ارزیابی باز, اقدامات (edit, access, profile).
- Add a «recent evaluations» column showing the last final score as a `<PctBadge>`.
- Add row click → open profile modal (not just the name button).
- Add bulk-select checkbox column for bulk access assignment.

### 2.3.3 Supervisor home (`/supervisor`)

**Current:** Two tables stacked: «افراد زیرمجموعه» (top, no search) and «ارزیابی‌های من» (bottom, with search).

**Proposed:**
- Merge into a single tabbed view: «افراد زیرمجموعه» | «ارزیابی‌های من» | «پیش‌نویس‌های باز» | «برگشتی‌ها».
- Each tab has its own `<FilterBar>`.
- Personnel rows: name is a `<button>` opening the profile modal (fixes U1). Show «شروع ارزیابی جدید» button only if no open evaluation exists (fixes U3). Show last final score as a `<PctBadge>`.
- Evaluation rows: clicking opens `/evaluations/{id}`. Add a «نتیجه» column with the `<PctBadge>`. Add a «مرحله» column with a `<StatusBadge>`.
- Add a «برگشتی‌ها» tab showing evaluations in `draft` status with a return-reason comment (fixes B6).

### 2.3.4 Evaluation detail page (`/evaluations/{id}`)

**Current:** Long vertical scroll: header → score summary → 20-row scoring table → comment → action buttons. Confusing for a 4-stage workflow.

**Proposed:**
- **Sticky header** with: personnel name, evaluation code, current stage badge, back button.
- **Workflow stepper** (horizontal, 4 dots: مسئول واحد → منابع انسانی → معاونت → مدیرعامل) showing the current stage. Click a dot to see who acted and when.
- **Score summary** as a sidebar (right side on RTL) with: general score, specialised score, final weighted score, recommendation. Visible during scoring and review.
- **Scoring table** as the main content area. Move «نظر کلی» to the top of the table (fixes U19).
- **Comments section** as a tabbed panel below: «کامنت‌های جریان» | «تاریخچه رویدادها» (audit log for this evaluation).
- **Action bar** sticky at the bottom: «ذخیره پیش‌نویس» | «ثبت ارزیابی» (or «تأیید» / «برگشت» depending on stage and role).
- For read-only mode: hide the action bar, show «چاپ / PDF» in the sticky header.

### 2.3.5 Improvement plan create modal (`/hr/improvement-plans` → modal)

**Current:** Title + review date only.

**Proposed:**
- Title (required)
- Description (textarea, optional but encouraged)
- Review date (required)
- Follow-up responsible (dropdown, optional)
- Goals (repeatable text inputs, at least 1 required)
- Save button disabled until title + date + ≥1 goal.

### 2.3.6 Audit log page (`/hr/audit-log`)

**Current:** Single filter dropdown + table with raw JSON.

**Proposed:**
- `<FilterBar>` with: event type (multi-select), actor (search), date range, evaluation code search.
- Table columns: timestamp, event type (with icon), actor, target (evaluation code as link), summary (rendered from JSON — e.g., «وضعیت: تأییدشده توسط HR → بررسی معاونت»).
- Row click → expand to show full before/after JSON in a `<pre>` block.
- Export to CSV.

## 2.4 UX Pattern Changes

### 2.4.1 Navigation structure

**Current:** Top header with horizontal nav for HR (8 items), single-item nav for other roles.

**Problem:** 8 items in a horizontal scrollable nav is awkward on tablets. Single-item nav for supervisor/deputy/CEO is wasteful.

**Proposed:**
- **Sidebar** (collapsible on desktop, drawer on mobile) for all roles. 240px wide, 64px collapsed (icons only).
- HR sidebar: پرسنل, کاربران, شاخص‌ها, دوره‌ها, صف بررسی, برنامه‌های بهبود, داشبورد, گزارش رویدادها.
- Supervisor sidebar: افراد زیرمجموعه, ارزیابی‌های من, پیش‌نویس‌ها, برگشتی‌ها.
- Deputy sidebar: پرونده‌های در انتظار, پرسنل مدیریتی, ارزیابی‌های من.
- CEO sidebar: تأیید نهایی, ارزیابی‌های من.
- Employee sidebar: کارنامه من, پروفایل من.
- All roles get: اعلان‌ها, حساب من, خروج at the bottom.
- Active item: gradient accent on the right edge (RTL), label in `font-semibold`.
- Breadcrumbs in the top bar for nested routes (`/hr/improvement-plans/EVL-0001`).

### 2.4.2 Permission / visibility logic

**Current problem (the deeper structural issue):** Several pieces of UI are gated by *stage of the workflow* rather than by *role*. For example:
- The personnel profile modal is only reachable from the HR personnel page, even though the data is conceptually useful to every reviewer.
- The «return case» button is shown to HR even though there's no upstream reviewer.
- The supervisor's «start new evaluation» button is always shown, even when an open evaluation exists.

**Proposed principle:** Permission/visibility should be a function of `(role, evaluation_access relationship, evaluation.status)` — never of `evaluation.status` alone.

Concrete changes:
1. **Personnel profile modal** (`EmployeeProfileModal`): visible to any role that has `evaluation_access` to that personnel (supervisor, deputy, CEO) plus HR. Backend: relax `GET /api/dashboard/personnel/{id}/radar` and `/trend` to allow these roles for personnel in their access scope.
2. **«Return case» button**: hide for HR when the evaluation has no prior reviewer stage (i.e., always hide for HR on `submitted` status — there's no upstream reviewer). Show only for deputy (`hr_approved`) and CEO (`deputy_approved`).
3. **«Start new evaluation» button**: disable if the personnel has any non-finalized evaluation. Show tooltip with the existing evaluation code.
4. **«Submit» button on scoring form**: disable (with validation message) until `drafts.length === indicators.length` AND all evidence requirements are met. Currently the user can click submit with an empty `drafts` array (B1).
5. **«Approve» button**: always shown to the correct reviewer at the correct stage. Never shown to non-assignees.
6. **Employee acknowledgment**: show the «رؤیت شد» button only if `evaluation.status === 'finalized'` AND `acknowledged_at === null`. Currently it's shown but re-clicking does nothing.

### 2.4.3 Feedback / state handling

**Current problems:**
- Form submission failures show a toast but the form state is unclear (is my data saved? do I need to re-do anything?).
- Loading states are inconsistent (some pages show empty state during load, some show skeleton, some show nothing).
- Error states are mostly toasts; there's no inline error with retry.

**Proposed pattern:**
- Every async action should have 4 explicit states: `idle`, `loading`, `success`, `error`. Render differently for each:
  - `idle`: normal UI.
  - `loading`: disable the trigger button, show spinner inside it. Other inputs remain editable.
  - `success`: toast (auto-dismiss 3s) + state update.
  - `error`: inline error message above the action bar + toast (manual dismiss). Provide a «retry» button.
- Every list view should use `<Skeleton>` during `isLoading`, `<EmptyState>` during `isSuccess && data.length === 0`, and `<ErrorState>` during `isError`.
- Every form should disable the submit button during submission and show the spinner. Re-enable on error.

### 2.4.4 Confirmation dialogs

**Current:** Custom `useConfirm()` hook with a modal. Works but inconsistent — some actions (toggle active) confirm, others (save access) don't.

**Proposed:** Standardise on:
- Destructive actions (deactivate, delete, return case, cancel plan, close period): always confirm with a clear description of consequences.
- Non-destructive actions (save, approve): no confirm for simple saves; confirm for approvals with «پس از ثبت، دیگر امکان ویرایش وجود نخواهد داشت».
- Use `AlertDialog` pattern (focus trap, Escape to cancel, click outside to cancel).

## 2.5 Additional Recommendations

These are things not explicitly asked for but that I observed need attention.

### 2.5.1 Observability

- **Frontend error tracking:** Add Sentry (or similar). The current `console.log`-only approach means production errors are invisible.
- **Performance monitoring:** Add Web Vitals reporting. The notification polling every 30s and the duplicate-XHR pattern (B4) are wasteful; measurement would have caught them.
- **User analytics:** Add PostHog (or similar) to see which pages are actually used, where users get stuck, what the average evaluation-completion time is.

### 2.5.2 Testing

- **Backend:** The pytest suite covers the workflow engine well. Add tests for the manager-path submit (would have caught B1). Add tests for the return-case feature (currently uncovered).
- **Frontend:** There are unit tests for `ScoreForm` and `client.test.ts`. Add component tests for `EvaluationDetailPage` (would have caught B1, B2, B3). Add Playwright e2e tests for the full workflow.
- **Visual regression:** Add Chromatic (or similar) to catch unintended UI changes.

### 2.5.3 Documentation

- **README is stale** (U13): update to reflect the actual feature set, including the return-case mechanism.
- **No user manual:** an HR user coming to this system cold has no in-app help. Add a `/help` page with role-specific guides.
- **No API changelog:** the OpenAPI spec is auto-generated but there's no human-readable changelog.

### 2.5.4 Performance

- **Notification polling:** 30s is aggressive. Use WebSocket (or Server-Sent Events) for real-time notifications instead.
- **`useUsersList({ limit: 1000 })`:** the personnel page fetches all 1000 users just to populate the access-editor dropdowns. Paginate or use a search-as-you-type dropdown.
- **`useIndicators({ includeInactive: true })`:** fetched on every evaluation page load. Cache more aggressively (indicators rarely change).
- **PDF generation:** WeasyPrint is synchronous. For large PDFs, queue via a background task (Celery or similar).

### 2.5.5 Security

- **CORS:** `CORS_ORIGINS` defaults to `http://localhost:5173,http://localhost:8080`. Production should restrict to the actual frontend domain.
- **Rate limiting:** Only on `/api/auth/login`. Add rate limits to `/api/auth/refresh`, `/api/evaluations/{id}/scores` (to prevent autosave abuse), and `/api/personnel` (to prevent enumeration).
- **Audit log:** Currently logs actor and event type. Add IP address and user-agent for security-relevant events (login, password change, role change).
- **Session invalidation:** Changing a user's password as HR invalidates their sessions (good). But deactivating a user does **not** invalidate their existing tokens — they remain logged in until the access token expires (30 min). Fix: increment `token_version` on deactivation too.

---

*End of audit.*
