I now have a thorough understanding of the product's UX. I have enough evidence to write the audit. I'll write the full report in English (the user asked in English), citing Persian UI strings where relevant.

DbsPulse — UX & Product Usability Audit

Product context: DbsPulse is a Persian (RTL) organizational performance-evaluation system built around a chained approval workflow — Supervisor scores → HR reviews → Deputy approves → CEO finalizes — feeding contract-renewal decisions, with hashed/QR-verifiable PDF scorecards, an audit log, improvement plans, objections, and self-assessment. Frontend: React + Tailwind, Vazirmatn font, dir="rtl".

This audit is based on a direct reading of the frontend source (routing, layout, every role page, forms, dialogs, tables, meters, notification, PDF generation) and the README. It deliberately ignores code quality except where code shape determines user experience.

Overall Impression

DbsPulse is unusually thoughtful for an internal tool — it has skeleton loading states, permission-aware UI, a skip-to-content link, prefers-reduced-motion support, live evidence-word counters, explicit empty states, optimistic conflict handling ("already has an open evaluation → navigate to it"), and workflow states communicated with plain-language copy. Many of its "weaknesses" are the opposite of most systems: it over-explains and over-confirms in places. The core problems are concentrated in terminology ambiguity ("رؤیت"), one-confirm destructive actions, notification/comment silos, bulk-operation discoverability, and a few accessibility gaps around motion and charts.

1. Employee

Strengths first: The employee view is genuinely well designed — a single "کارنامه من" (my record) page, open-case card that communicates where the file currently is without leaking draft scores, a formal objection path that explicitly states "نتیجه تغییر نمی‌کند" (the result won't change), self-assessment that is framed as "دیدگاه، نه نمرهٔ قطعی" and explicitly "یک‌بار ثبت می‌شود و قابل ویرایش نیست", and a downloadable official PDF scorecard for the employee.

Findings:

- F1 — "رؤیت شد" is ambiguous and irreversible — Severity: High. Screen: MyEvaluationsPage / MyEvaluationCard. Evidence: the confirm dialog reads "تأیید رؤیت نتیجه ارزیابی؟ … این عمل قابل بازگشت نیست" and the button is labeled "رؤیت شد". Problem: in common Persian HR speech, "رؤیت" is understood as "I've seen it", but many employees will read the button as "I confirm/agree" (تأیید). The system deliberately separates seen from agreed, yet the one-word label does not. Why users struggle: an employee clicks it believing it means approval, then learns it only means receipt — or worse, believes clicking it forfeits their right to object (it does not; objection opens after acknowledgment, which is correct but unintuitive). Recommendation: relabel to "مشاهده کردم" or "نتیجه را دیدم", and in the dialog add one sentence: "رؤیت به معنی پذیرش نتیجه نیست؛ پس از آن هم می‌توانید اعتراض ثبت کنید." Impact: prevents the single most consequential misunderstanding in the entire product. Complexity: trivial.
- F2 — Objection affordance is hidden until after acknowledgment — Severity: Medium. Evidence: if (!item.acknowledged_at) return null; in ObjectionSection. Problem: an employee who disagrees before acknowledging sees no objection path at all and no hint that one exists. Why: the UI correctly gates the action but communicates nothing about it; the employee thinks the system offers no recourse and may refuse to click "رؤیت شد" out of fear. Recommendation: when not acknowledged, show a disabled/dimmed line: "امکان ثبت اعتراض پس از مشاهدهٔ نتیجه فعال می‌شود." Impact: removes a standoff that blocks the workflow; Complexity: trivial.
- F3 — Self-assessment is one-shot with a weak warning — Severity: Medium. Evidence: copy says "یک‌بار ثبت می‌شود و قابل ویرایش نیست" but there is no confirmation dialog on submit and the submit button is "ثبت نهایی خودارزیابی". Why users struggle: "ثبت نهایی" is easy to skim; one mis-tap with a half-written note is permanent and visible to the evaluator. Recommendation: confirm dialog on submit summarizing "پس از ثبت قابل ویرایش نیست". Impact: prevents regret on an irreversible action; Complexity: low.
- F4 — Self-assessment has no draft save — Severity: Medium. Screen: SelfAssessmentForm. The evaluator's form autosaves drafts (per comments in ScoreForm); the employee's form lives in local state only. A 20-indicator form with per-indicator notes is lost on refresh/accidental back. Why users struggle: the person with the least power in the system gets the least forgiving form. Recommendation: persist draft to localStorage at minimum. Impact: high for data loss prevention; Complexity: low.
- F5 — "پیشنهاد سامانه" (system recommendation) shown to the employee without provenance — Severity: Medium. Evidence: item.recommendation rendered as "💡 پیشنهاد سامانه: …". Problem: a system-generated recommendation about the employee's future (likely affecting contract renewal) is shown as an anonymous machine judgment. Why users struggle: it reads as a verdict, not a suggestion; in a workplace context this can feel threatening and unaccountable. Recommendation: frame as outcome of the approved rubric ("بر اساس بازهٔ امتیاز شما، پیشنهاد ثبت‌شده: …") and make clear who decided the mapping. Impact: trust and perceived fairness; Complexity: trivial.
- F6 — Workflow progress is text-only for the employee — Severity: Low. The open-case card shows the current stage label and two dates; there is no step indicator of the 4-stage chain. The employee cannot see "2 of 4 done". A simple 4-step progress strip (the stage model already exists: STAGE_LABELS) would make the black box visibly transparent — aligned with the product's own stated goal. Complexity: low.

2. Evaluator / Direct Manager (مسئول واحد)

Strengths: the score form is the best-thought-out surface in the app — null-default forcing function (every indicator must be touched), live evidence word counter ("۲ واژهٔ دیگر لازم است") before submission, autosave drafts, client-side preview of weighted percentages with the same formula as the server, mobile variant that swaps a 4-column table for discrete radio-style buttons (tested, with rationale in comments), keyboard-operable slider (arrows/Home/End), and semantic 1–5 labels ("ضعیف…عالی") on every score choice.

Findings:

- F7 — Desktop scoring uses a drag slider for a 5-point scale — Severity: Medium. Screen: SegmentedScore in ScoreForm. Evidence: pointer-drag thumb on a track; the mobile variant explicitly abandoned dragging as imprecise ("کشیدنِ یک thumb ۲۲ پیکسلی با انگشت … دقیق نیست"), and the same argument applies to mouse users on dense forms. Mis-drags change scores by 1 silently. Recommendation: keep the slider for continuity but add the five labeled stop-buttons as clickable targets (the labels exist), making the control effectively a segmented control. Impact: fewer scoring errors on the highest-stakes input in the system; Complexity: low–medium.
- F8 — Supervisor's personnel list has no search/filter — Severity: Medium. Screen: SupervisorHomePage. The table renders up to 1,000 subordinates (limit: 1000) with no search box, no pagination, no unit filter — just a long table. EvaluationList has excellent search/tabs but the starting list does not. Why users struggle: a supervisor with 60 subordinates scrolls to start an evaluation. Recommendation: add the same debounced search input used elsewhere (component exists). Impact: removes minutes of scrolling per session; Complexity: low.
- F9 — "نمره‌دهی من" (MyScoring) is valuable feedback but its label is ambiguous — Severity: Low. In nav, next to "افراد زیرمجموعه", "نمره‌دهی من" could read as "scores I received". The comments call it "آینهٔ ارزیاب" (evaluator's mirror). Consider "آمار نمره‌دهی من" or "رفتار نمره‌دهی من". Complexity: trivial.
- F10 — Return/برگشت feedback loop relies on scrolling to page bottom — Severity: Medium. Screen: EvaluationDetailPage. When HR/deputy returns a file, the supervisor sees a small "برگشتی" badge with a tooltip saying "کامنت‌های پایین صفحه را ببینید" — the reason for return is a comment at the bottom of a long page. Why users struggle: the one thing they must read before fixing their scores is the least prominent element. Recommendation: when was_returned and the case is in the user's editable stage, surface the latest return-reason comment as an inline banner above the score form. Impact: directly reduces ping-pong cycles; Complexity: low.
- F11 — Two parallel scoring surfaces may confuse (list "شروع ارزیابی جدید" vs. "ادامه ارزیابی باز") — handled well via 409-conflict auto-navigation; however starting disables all rows' buttons while one is being created (disabled={starting}), so a double-click guard blocks other rows for a moment. Minor; acceptable.

3. HR

Strengths: the queue with 7 status tabs + advanced combinable filters + Excel export honoring active filters; the Excel import flow is exemplary (3 steps: file → preview with per-row errors → result with one-time downloadable credentials CSV, with a template download); stuck-case recovery tools (reassign stage owner, HR handover, cancel) with plain-language consequences; HR case-claiming ("برداشتن پرونده") making queue ownership explicit; audit log with human-readable event labels; cohort-size privacy suppression ("محرمانه") clearly distinguished from "no data".

Findings:

- F12 — Queue tabs create redundant navigation; default tab buries the bottleneck — Severity: Low. QueuePage has 7 tabs. HR lands on "در انتظار بررسی منابع انسانی" which is correct, but tab counts are not shown. HR cannot see "3 submitted, 12 in draft" without clicking each tab. Recommendation: badge counts on tabs (the data exists via status-filtered queries; one extra aggregate endpoint). Impact: dashboard-level awareness; Complexity: low–medium.
- F13 — Destructive actions use the *same* confirm dialog as neutral ones — Severity: High. Evidence: ConfirmDialog renders the confirm button with the default primary Button for everything: acknowledge, cancel evaluation (from HrRecoveryBox), complete/cancel improvement plan, deactivate user. The acknowledge confirm ("رؤیت شد") and the cancel-case confirm ("لغو پرونده") look identical. Why users struggle: habituation — after 20 harmless confirms, the 21st (cancel a case with legal/contract consequences) gets the same automatic click. Recommendation: add a danger variant (red button, required reason field for cancel — reason exists in API? if not, add), and for case cancellation require typing the evaluation code or a checkbox "پیامدهای لغو را می‌دانم". Impact: materially reduces catastrophic mis-clicks; Complexity: low–medium.
- F14 — Audit log detail: AuditDetails shows old/new value JSON — readable only to technical users — Severity: Medium. Event labels are translated (good), but the payload diff is raw JSON objects. An HR user auditing "who changed this score" sees {"score": 3} → {"score": 4} at best, and nested objects at worst. Recommendation: a small renderer for the top 8 event types (score change, status change, reassignment) turning them into sentences ("امتیاز شاخص X از ۳ به ۴ تغییر کرد"). Impact: makes the audit log usable by its actual audience; Complexity: medium.
- F15 — User creation and personnel creation are separate silos — partially mitigated. PersonnelPage can create the employee account inline (good design, with suggested username and generated temporary password). But UsersPage can also create users, and the employee-linked creation there requires picking from a 1,000-item personnel dropdown with no search. Recommendation: in UsersPage, replace the personnel ` with the existing PersonPicker`. Complexity: low.
- F16 — Excel export of credentials is CSV while everything else is XLSX — Severity: Low. new-accounts.csv (with BOM, good) vs evaluations.xlsx. HR staff will double-click CSV and hit Excel's encoding/mojibake edge cases on some Windows locales. Minor inconsistency in an otherwise polished flow.
- F17 — No bulk selection in the queue — Severity: Medium. During peak season HR must open each submitted file individually to approve. If the workflow supports batch approve, a checkbox column would help; if deliberately not supported (each file must be read), the UI should say so once ("برای حفظ کیفیت، تأیید گروهی وجود ندارد") — otherwise users hunt for it. Currently it's silent. Complexity: low (copy) or high (feature).
- F18 — Dashboard tabs ("نمای کلی" / "تحلیل و گزارش‌ها") are not reflected in the URL — Severity: Low. Refresh or deep-linking loses the tab state; an HR analyst sharing "the indicator report view" shares a URL that lands on overview. Complexity: trivial (use search params).

4. Deputy / Approver

Strengths: dual nature is handled correctly in IA (deputy both approves the chain and directly scores managers — two nav entries, "پرونده‌های در انتظار" + "نمره‌دهی من"), pending list defaults to their actionable tab, manager scoring path clearly separated with a labeled section.

Findings:

- F19 — Approval decision lacks a structured summary view of what changed — Severity: Medium. Screen: EvaluationDetailPage. The deputy/CEO approves a file by reading the full score table + comments. There is no "executive summary" block at the top (final %, evidence-flagged scores, return history, objection status, self-vs-evaluator gaps). The data all exists on the page but requires scrolling and assembling. Recommendation: a compact "خلاصهٔ تصمیم" card pinned above the fold for approver roles: final score, number of 1s/5s with evidence, return count, gap highlights. Impact: faster, more consistent approvals; Complexity: low–medium (data already in the detail payload).
- F20 — Return action requires a comment? — cannot verify enforcement from frontend alone; the comment panel and return flow appear as separate actions. If return without comment is possible, that's a critical gap (supervisor receives "برگشتی" with no reason — see F10). Recommendation: make returning require a comment, enforced client-side at minimum.
- F21 — Deputy's personnel fetch limit: 1000 then filters is_manager client-side — UX consequence: no feedback while loading and potential stale view; minor. Low severity.

5. CEO

Strengths: minimal, focused surface (pending finalizations + finalized + org analytics), which matches the CEO's attention budget — good restraint.

Findings:

- F22 — The CEO's queue title says "داشبورد مدیرعامل" but shows a list, not a dashboard — Severity: Low (terminology). The actual analytics live under "تحلیل سازمان". The home page is an inbox; calling it a dashboard sets a wrong expectation. Rename to "صندوق تأیید نهایی" or similar. Trivial.
- F23 — Finalization is the single most consequential click in the system (produces a hashed, QR-verifiable, legally meaningful PDF) — confirm dialog should show the final score and employee name, not a generic title. Evidence: CeoHomePage/EvaluationDetailPage confirm flow uses the shared ConfirmDialog. A mis-finalization cannot be edited (by design — a new evaluation is required). Recommendation: dedicated finalize dialog: "نتیجهٔ نهایی ۷۸٪ برای علی رضایی — سند رسمی صادر و قابل تغییر نیست." Complexity: low. Severity: High-by-impact, Low-by-frequency — I rate Medium.
- F24 — Executive analytics: SuppressedValue ("محرمانه") is excellent privacy communication, but chart tooltips/legends should inherit it; if a suppressed unit appears in a bar chart as a gap or zero, the CEO may misread it as "no data" or "score 0". Verify chart paths handle null vs 0 (types show avg_final_pct: number | null, and SuppressedValue exists in tables — charts need the same treatment). Medium.

6. System Administrator

There is no dedicated sysadmin surface beyond what HR gets (users, audit log, scheduler runs endpoint mentioned in README, indicators management).

Findings:

- F25 — Indicator management is high-risk with thin safeguards — Severity: Medium. Deleting/reordering indicators (indicators_reordered, indicator_deleted in audit labels) changes what every future evaluation measures. If delete is hard-delete of an indicator referenced by historical scores, historical PDFs/scorecards may reference missing descriptions (EvaluationDetail uses includeInactive: true for indicators — good sign of soft-delete, but the delete affordance should warn "این شاخص در N ارزیابی گذشته استفاده شده"). Recommendation: consequence-aware delete confirm. Complexity: low–medium.
- F26 — No system health/scheduler visibility in UI — Severity: Low. Scheduler runs exist (/api/admin/scheduler-runs) but README implies it's endpoint-only. An admin has no UI to see "reminders ran/failed". Low priority given the audience.
- F27 — Login security feedback: per-IP rate limiting and account lockout exist (README: "قفل حساب پس از تلاش‌های ناموفق") — verify the *user-facing* message distinguishes "wrong password" from "account locked, wait N minutes / contact HR". A locked-out legitimate user with a generic "ورود ناموفق" error is a support-ticket generator. Medium.

7. Technical Support User

Findings:

- F28 — Error recovery UX is good at the boundary, thin in the middle — Severity: Low. ErrorBoundary with route-keyed remount and "بازگشت به صفحه اصلی" is solid. But inline errors are inconsistent in placement: some pages render red text at top (DeputyHomePage), some inline near the action, some toast-only. Toasts auto-dismiss in 4s — for errors containing actionable info (e.g., "شاخص ۳ شواهد ندارد"), a 4-second disappearing message is an accessibility and usability failure. Recommendation: error toasts should persist until dismissed (keep auto-dismiss for success only). Severity: Medium, Complexity: trivial (one prop).
- F29 — No visible request ID / error reference for support — Severity: Medium. README mentions request_id correlation for error tracking (backend), but if the UI's error messages don't surface a short reference code, a user reporting "it failed" gives support nothing to search. Recommendation: append a truncated request ID to error toasts/details. Complexity: low (if exposed in error responses).
- F30 — Session management page exists (SessionsPage — good), but there's no "session expired" grace pattern visible in this code pass; token refresh is handled, yet if refresh fails mid-form, the autosave-drafts architecture mitigates score loss — good. Verify the redirect preserves the return URL after re-login. Low.

Cross-Cutting Evaluation Areas

Information architecture: Strong. Role-based landing pages, /improvement-plans deliberately not under /hr/ (with a written rationale), legacy redirects preserving old notification links — a level of IA care rarely seen. Weakness: tab state not in URL (F18); disabled features show a friendly page instead of 404 (good pattern, though "دوره‌های ارزیابی" behind a feature flag is dead nav weight when disabled — it's correctly hidden from nav, fine).

Navigation: Wrap-not-scroll RTL nav with a documented rationale; correct RTL arrow directionality throughout (continue = left-pointing, back = right-pointing — verified in code). Missing: breadcrumbs on deep pages (only a "بازگشت" button using navigate(-1) — which breaks when arriving from an external notification link; a user opening a notification URL and pressing "بازگشت" leaves the app or goes somewhere unexpected. Severity: Medium — use a computed parent path fallback instead of bare history back.)

Cognitive load: Role surfaces are minimal by design. Exception: HR dashboard analysis tab stacks 4 tables + charts in one sub-tab — acceptable. Evaluation detail page is long (scores + self-assessment + objection + comments + recovery box) — borderline but justified.

Form design: Best-in-class for the score form; personnel form is long but grouped with inline explanation ("چرا حساب بسازم؟"). The personnel form does appear to be a genuinely long form in a modal — a modal-hosted long form risks accidental close-on-backdrop-click losing data (Modal closes on backdrop mousedown). Severity: Medium — long forms (personnel creation with access chain + account) should warn on dirty-close or disable backdrop-close when dirty.

Confirmation patterns: Uniform but undifferentiated (F13) — the core issue. Positive: initial focus lands on confirm button (keyboard-friendly) — but note: initial focus on the *confirm* button of a destructive action means Enter immediately executes it. For destructive actions, focus should default to Cancel. Severity: Medium.

Empty states: Consistent EmptyState component with icon; messages are plain ("موردی یافت نشد", "فردی زیرمجموعه شما نیست", "هنوز هدفی ثبت نشده است"). Some could be action-oriented ("پرونده‌ای در انتظار شما نیست" is fine, but personnel-empty for HR could offer "افزودن پرسنل" CTA). Low.

Loading states: Skeletons everywhere, including route-level lazy fallback, table skeletons, button-level spinners with text ("در حال ایجاد…"). Excellent. One gap: PageFallback skeleton doesn't match page shapes closely — cosmetic only.

Feedback: Toast system is clean, with role="alert" for errors and role="status" for success (screen-reader correct). Weaknesses: 4s auto-dismiss on errors (F28); success toasts sometimes carry key info ("فایل CSV را دانلود کنید — فقط همین یک بار" — the import flow handles this in-modal, good).

Notifications: Bell with unread badge (fa-IR numerals), mark-all-read, click→navigate→mark-read. No grouping, no filtering, and no "view all" page — a busy HR in appraisal season gets a long undifferentiated dropdown. Also the notification message is the only carrier — if the link target was deleted, user gets the evaluation-not-found page (handled with a decent error card, acceptable). Severity: Low–Medium.

Comments/threading: One-level threading (parent/reply), stage-tagged, reply allowed for all chain roles, employee read-only — deliberate and defensible. Weaknesses: no timestamps shown as relative ("۲ ساعت پیش" vs full datetime — full datetime is fine for legal contexts, acceptable choice); no way to reference a comment from the return action (F20); no edit/delete (defensible for audit, but a typo in a legal-adjacent comment is permanent — consider 5-minute edit window with audit entry).

Dashboard usability: Role-overview tiles with tones (amber for attention — good), count-up animations (respecting reduced-motion via CSS, though CountUp uses requestAnimationFrame — verify it respects reduced motion; CSS media query won't stop JS-driven count-up animation. Severity: Low, accessibility).

Data tables: Horizontal scroll contained in wrapper; skeletons; consistent headers. Missing: no column sorting anywhere — "کمترین میانگین به تفکیک فرد" is server-sorted, fine, but the queue and personnel tables can't be sorted by date/score/name. HR compensates with filters, partially. Severity: Low–Medium.

Filtering/search/pagination: Debounced search, combinable filters with active-count badge, Jalali date pickers (correct for the locale), Persian-numeral pagination ("صفحه ۳ از ۱۲"). Pagination lacks first/last jump and page-size is fixed at 10 — for a 500-row audit log this means 50 clicks; audit log especially needs larger page sizes or date-range-first UX. Low–Medium.

Reports/charts: Recharts lazy-loaded (perf-aware); single-hue charts instead of rainbow (documented decision — good); chart PNG download (ChartDownloadCard). Gaps: charts are images to screen readers — no aria-label/data-table fallback visible for charts (WCAG 1.1.1). Severity: Medium for accessibility. RTL: Recharts axes in RTL are a known pain point — not verifiable statically, flag for visual QA.

PDF/document experience: Hashed + QR-verifiable PDF with a public /verify/:token page using non-enumerable tokens (excellent security-UX design), Vazirmatn embedded for print, employee self-download. This is the product's crown jewel. Weaknesses: PDF opens via ` to /api/...pdf — no loading feedback during generation (WeasyPrint renders can take seconds; user may click repeatedly). Severity: Low–Medium — add a "در حال آماده‌سازی سند…" state or async generation. Also pdf_downloaded` is audit-logged (good).

Mobile responsiveness: Deliberate and tested — mobile score form variant replacing table+slider with cards+radio buttons (with regression tests), tables scroll internally, filters get min-w-0 max-w-full fixes with documented reasoning, PWA manifest for installability. Genuinely strong. Remaining: the sticky 2-row header consumes significant vertical space on small screens; evaluation detail page will be very long on mobile (consider collapsible sections). Low.

RTL quality: Correct arrows, correct slider direction mapping with explicit comments (۵ → ۰٪), dir="ltr" on codes/usernames, ms-/me- logical properties. Strong. One inconsistency: theme-color and favicon still use the old teal/violet branding (#0d9488 gradient) while the design system is red (#B61615) — brand inconsistency that slightly erodes trust/polish. Trivial fix, Low severity, but it is a design-system consistency defect.

Persian typography: Vazirmatn primary with Tahoma/Segoe UI fallback, fa-IR numeral localization everywhere (including counters and pagination), tabular-nums on numerals. Strong. Check: mixed LTR/RTL runs in evaluation codes ("EVL-0001") are handled with dir="ltr" spans in most places — audit the comment thread rendering for bidi safety with mixed Persian/English text. Low.

Accessibility: skip-link, focus-visible outlines, modal focus trap + focus restore + Escape, aria-pressed on score buttons, aria-expanded on bell, role=tab/tablist, aria-labels on icon buttons. Above average. Gaps: (a) charts lack text alternatives; (b) CountUp/motion.js animations are JS-driven and don't honor reduced-motion (the CSS media query only covers CSS animations; framer-motion needs useReducedMotion); (c) semantic color on score slider (red→green) is color-only for the tone — labels exist, so acceptable; (d) :focus-visible uses gray (pulse-violet-400) at 2px — on white cards, gray-400 (#9ca3af) contrast is ~2.8:1, below the 3:1 non-text contrast guideline. Severity: Low–Medium.

Color contrast: red-600 on white (~5.9:1) fine; gray-400/500 placeholder text and text-gray-400 hints at 11–12px sizes will fail 4.5:1 — several hints (.text-[11px] opacity-70 in RoleOverviewCards) are borderline. Low–Medium.

Keyboard navigation: Modal trap, skip link, slider arrows/Home/End, native selects — good. Gap: notification dropdown is not keyboard-complete — Escape-to-close is not visible in NotificationBell (only outside-click), and arrow-key navigation within the list is absent. Low.

Visual hierarchy: Consistent PageHeader with accent rule, card titles, clear primary vs secondary buttons. Exception: the pulse-red primary color is used for both brand emphasis AND errors (error toast is bg-pulse-600 — the brand red IS the error red. A user sees a red toast and can't tell "brand notification" from "error" without reading. Also primary buttons and error states are the same hue family — confusing under stress. Severity: Medium. Recommendation: use a distinct error color or reserve brand red for primary actions only.)

Consistency: Strong (shared Table, Card, Modal, Button, FilterSelect, EmptyState). Exceptions found: filter input class duplicated as string constants in multiple files (minor drift risk); UsersPage search vs EvaluationList search have slightly different widths; CSV vs XLSX (F16).

Permission-aware UI: Exemplary — actions are computed from role+status+ownership and not rendered rather than rendered-then-403 ("دکمه‌ای نشان نمی‌دهیم که به ۴۰۳ ختم شود" is an explicit documented principle). Server enforces independently. Model implementation.

Destructive actions: Confirm dialogs exist for all of them; undo exists nowhere (correct given audit-log philosophy), but differentiation and typed-confirmation are missing (F13), and Enter-to-confirm focus default is risky.

Workflow progress visibility: Stage labels everywhere, was_returned badge, stage_entered_at dates. Missing: no visual stepper of the 4-stage chain anywhere — everyone sees "where it is" but no one sees "where it is in the whole" (F6 applies to all roles). The single best visibility improvement available. Low complexity.

Places where the system behaves correctly but communicates poorly

1. "رؤیت شد" — behaves perfectly (separates seen from agreed); communicates the opposite (F1).
2. Objection gated behind acknowledgment — correct logic, zero explanation before the gate (F2).
3. "برگشتی" badge with a tooltip telling you to scroll down — the reason exists; the UI points vaguely at it (F10).
4. Cohort suppression ("محرمانه") — excellent communication in tables; unclear in charts (F24).
5. Error toasts disappearing in 4s — the system knows the error; the user can't read it in time (F28).
6. No batch approval — possibly a deliberate quality stance, never stated; users will search for it (F17).
7. Brand-red error toasts — semantically correct color, contextually ambiguous (color = brand = error).
8. "داشبورد مدیرعامل" is an inbox, "داشبورد منابع انسانی" is a dashboard — same word, different things (F22).
9. Finalize/cancel confirms identical to trivial confirms — severity invisible at decision time (F13).
10. Old teal favicon/theme-color vs red UI — the shell disagrees with the product.

Top 10 UX Problems

1. "رؤیت شد" terminology ambiguity on an irreversible acknowledgment (F1) — the highest-trust-risk label in the product.
2. Undifferentiated confirm dialogs for trivial vs destructive actions, with initial focus on Confirm (Enter executes) (F13).
3. Return-reason communication — supervisors get a badge and a pointer to the bottom of the page instead of the reason inline (F10 + F20).
4. Error toasts auto-dismiss in 4 seconds, hiding actionable failure details (F28).
5. Desktop score slider is drag-based for a 5-point discrete scale, inviting silent mis-scores (F7).
6. Self-assessment is one-shot with no draft and no submit confirmation for the least powerful user (F3/F4).
7. No workflow stepper anywhere — stage is labeled, but position in the 4-step chain is never visualized (F6).
8. Brand red doubles as error color in toasts, making failure states ambiguous at a glance.
9. Back navigation uses navigate(-1), which misbehaves when arriving via notification/deep links.
10. Charts lack text alternatives and JS animations don't honor reduced-motion — the main accessibility gaps in an otherwise accessible app.

Top 10 UX Strengths

1. Score-form forcing function: null-default scores, live evidence word counters before submission, server-formula preview — error prevention, not just error messages.
2. Excel import flow with preview → per-row errors → one-time credential CSV — a genuinely model bulk-data UX.
3. Permission-aware UI that hides rather than forbids, with server enforcement — no dead-end 403 buttons.
4. Mobile score form redesigned, not just resized — discrete buttons replacing table+slider, protected by regression tests.
5. PDF with hash + QR verification and non-enumerable public verify page — trust engineered into the document experience.
6. Cohort privacy suppression communicated explicitly ("محرمانه" ≠ "no data") — rare honesty in analytics UI.
7. Stuck-case recovery tools (reassign, handover, cancel with reasons) — the workflow can heal itself without SQL.
8. Objection path with parallel-record design and explicit "the result won't change" framing — psychologically and legally literate.
9. Loading/empty/skeleton discipline across every list and route, plus ErrorBoundary with self-healing navigation.
10. RTL correctness as engineering — documented arrow directions, logical properties, fa-IR numerals, Jalali pickers, RTL-aware slider math with explanatory comments.

5 Highest-Impact Improvements

1. Relabel and re-explain "رؤیت": rename to "نتیجه را مشاهده کردم", state in the dialog that acknowledgment ≠ agreement and that objection remains available, and pre-announce the objection path before acknowledgment (F1/F2). Trivial effort, highest trust impact.
2. Introduce a danger-tier confirmation: red confirm button, Cancel-focused by default, and for case cancellation / evaluation finalization show entity name + consequence in the dialog; require a reason where the API supports it (F13/F23). Low–medium effort, prevents the worst mis-clicks.
3. Surface return reasons inline: when a returned case lands in an evaluator's editable stage, render the latest return comment as a banner above the score form, and require a comment on return (F10/F20). Low effort, directly shortens rework loops.
4. Fix feedback persistence & semantics: error toasts persist until dismissed, errors get a distinct hue from the brand red, and PDF generation gets a pending state (F28, color-ambiguity, PDF feedback). Trivial-to-low effort, improves every failure moment in the app.
5. Add a 4-stage workflow stepper (پیش‌نویس → بررسی منابع انسانی → بررسی معاونت → تأیید نهایی) to the evaluation detail header and the employee's open-case card, with current stage highlighted and returned state marked (F6). Low effort, transforms workflow transparency for every role.

Note on scope: findings are based on static review of the repository as of the audit date; items flagged "verify" (chart RTL axes, locked-account messaging, CountUp reduced-motion, PDF generation latency) should be confirmed with a running instance, ideally using the seeded demo accounts (hr1, sup1, dep1, ceo1).