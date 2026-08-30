// `support` عمداً هیچ جایگاهی در زنجیرهٔ ارزیابی ندارد؛ اختیاراتش فقط از
// مجوزهای اداری می‌آید (نیمهٔ دوم P0-03).
export type UserRole =
  | "unit_supervisor"
  | "hr"
  | "deputy"
  | "ceo"
  | "employee"
  | "support";

export const ROLE_LABELS: Record<UserRole, string> = {
  unit_supervisor: "مسئول واحد",
  hr: "منابع انسانی",
  deputy: "معاونت",
  ceo: "مدیرعامل",
  employee: "کارمند",
  support: "پشتیبانی فنی",
};

export interface CurrentUser {
  id: number;
  username: string;
  // همیشه پر است: اگر نامی روی حساب ثبت نشده باشد، بک‌اند خودِ نام کاربری را
  // برمی‌گرداند.
  display_name: string;
  role: UserRole;
  personnel_id: number | null;
  must_change_password: boolean;
}

export type PersonnelStatus = "active" | "inactive";

/** چرا این فرد دیگر در سازمان نیست. «غیرفعال» به‌تنهایی این را نمی‌گفت، و
 *  استعفا با پایان قرارداد در هیچ گزارشی یک چیز نیست. */
export type SeparationReason =
  | "resignation"
  | "dismissal"
  | "contract_end"
  | "retirement"
  | "other";

export const SEPARATION_REASON_LABELS: Record<SeparationReason, string> = {
  resignation: "استعفا",
  dismissal: "اخراج",
  contract_end: "پایان قرارداد",
  retirement: "بازنشستگی",
  other: "سایر",
};

export interface Personnel {
  id: number;
  personnel_code: string;
  full_name: string;
  job_title: string;
  is_manager: boolean;
  org_unit: string;
  contract_start_date: string;
  contract_end_date: string;
  status: PersonnelStatus;
  separation_date: string | null;
  separation_reason: SeparationReason | null;
  /** نام کاربریِ حساب این فرد، اگر دارد. null یعنی هنوز نمی‌تواند وارد شود. */
  account_username: string | null;
  /** وضعیت خودارزیابیِ پروندهٔ باز — تعیین می‌کند دکمهٔ دعوت چه بگوید. */
  self_assessment_state: SelfAssessmentState;
  open_evaluation_id: number | null;
  created_at: string;
  updated_at: string;
}

/** «دعوت نشده» و «دعوت شده ولی انجام نداده» و «پرونده‌ای نیست» سه چیز متفاوت‌اند
 *  و هرکدام به کنشِ متفاوتی می‌رسند — پس یک بولین کافی نبود. */
export type SelfAssessmentState =
  | "no_case"
  | "no_account"
  | "closed"
  | "pending"
  | "invited"
  | "submitted";

/** میانگین سازمان در یک دورهٔ ارزیابی — یک نقطه از «روند میانگین زمانی». */
export interface PeriodTrendPoint {
  period_id: number | null;
  name: string;
  starts_on: string | null;
  /** `null` یعنی جمعیتِ دوره کمتر از حداقلِ ناشناس‌ماندن بوده است. */
  avg_final_pct: number | null;
  count: number;
}

export interface OrgUnitCatalogueItem {
  id: number;
  site: string | null;
  name: string;
  /** همان رشته‌ای که در `personnel.org_unit` می‌نشیند. */
  full_name: string;
  is_active: boolean;
  display_order: number;
  personnel_count: number;
}

export interface EvaluationAccess {
  id: number;
  personnel_id: number;
  unit_supervisor_user_id: number | null;
  deputy_user_id: number;
  ceo_user_id: number;
  updated_by_user_id: number | null;
  updated_at: string;
}

export interface AppUser {
  id: number;
  username: string;
  role: UserRole;
  is_active: boolean;
  personnel_id: number | null;
  created_at: string;
  full_name: string | null;
  // همیشه پر است؛ بک‌اند ترتیب «نام پرسنل ← نام حساب ← نام کاربری» را اعمال
  // می‌کند تا هر صفحه لازم نباشد خودش این تصمیم را دوباره بگیرد.
  display_name: string;
}

export type IndicatorSection = "general" | "specialized";

export interface Indicator {
  id: number;
  section: IndicatorSection;
  category: string;
  description: string;
  display_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  // به این شاخص در چند ارزیابی نمره داده شده (P1-05). تفاوت «۰» و «۲۳۰» تفاوت
  // یک ویرایش بی‌ضرر و بازنویسی معنای دو سال تاریخ است.
  usage_count: number;
}

/** نسخهٔ چارچوب شاخص‌ها و اثرِ تغییر بعدی (P1-05). */
export interface FrameworkImpact {
  version: number;
  member_count: number;
  /** پرونده‌های بازی که امتیاز خورده‌اند — با نسخهٔ فعلی خودشان بسته می‌شوند */
  frozen_open_records: number;
  /** پرونده‌های بازِ دست‌نخورده — به نسخهٔ تازه منتقل می‌شوند */
  movable_open_records: number;
}

export type EvaluationStage =
  | "supervisor_scoring"
  | "hr_review"
  | "deputy_review"
  | "ceo_final";

export type EvaluationStatus =
  | "draft"
  | "submitted"
  | "hr_approved"
  | "deputy_approved"
  | "finalized"
  | "cancelled";

export interface EvaluationRecord {
  id: number;
  evaluation_code: string;
  subject_personnel_id: number;
  subject_full_name: string;
  period_id: number | null;
  unit_supervisor_user_id: number | null;
  deputy_user_id: number;
  ceo_user_id: number;
  // مسئولِ منابع انسانیِ این پرونده؛ null یعنی هنوز در صف مشترک HR است
  hr_user_id: number | null;
  hr_username: string | null;
  // null برای پروندهٔ لغوشده — در هیچ مرحله‌ای از زنجیره نیست
  stage: EvaluationStage | null;
  status: EvaluationStatus;
  general_score_pct: number | null;
  specialized_score_pct: number | null;
  /** امتیازِ فرم پیش از افزودن امتیاز ویژه */
  base_weighted_pct: number | null;
  final_weighted_pct: number | null;
  /** امتیاز ویژه: نمرهٔ اختیاری بابت کاری خارج از شرح وظایف (null یا صفر = ندارد) */
  bonus_points: number | null;
  bonus_reason: string | null;
  recommendation: string | null;
  evaluator_comment: string | null;
  created_at: string;
  finalized_at: string | null;
  acknowledged_at: string | null;
  was_returned: boolean;
  objection_at: string | null;
  objection_reason: string | null;
  objection_resolved_at: string | null;
  objection_resolution: string | null;
}

export interface MyEvaluation {
  id: number;
  evaluation_code: string;
  subject_full_name: string;
  period_id: number | null;
  general_score_pct: number | null;
  specialized_score_pct: number | null;
  base_weighted_pct: number | null;
  final_weighted_pct: number | null;
  bonus_points: number | null;
  bonus_reason: string | null;
  recommendation: string | null;
  finalized_at: string | null;
  acknowledged_at: string | null;
  // مسیر اعتراض — «رؤیت» یعنی دیدم، نه یعنی پذیرفتم
  objection_at: string | null;
  objection_reason: string | null;
  objection_resolved_at: string | null;
  objection_resolution: string | null;
}

/** نمای «وضعیت‌فقط» از پروندهٔ در جریان — عمداً بدون هیچ امتیازی. */
export interface MyOpenEvaluation {
  id: number;
  evaluation_code: string;
  status: EvaluationStatus;
  created_at: string;
  stage_entered_at: string;
  self_assessment_submitted_at: string | null;
  stage_label: string;
  /** شاخص‌های همین پرونده (P1-05) — فرم خودارزیابی از روی این ساخته می‌شود. */
  indicator_ids: number[];
  /** آیا پنجرهٔ خودارزیابی هنوز باز است — سرور تصمیم می‌گیرد، نه فرانت. */
  self_assessment_open: boolean;
}

export interface SelfAssessmentScoreRow {
  indicator_id: number;
  score: number;
  note: string | null;
}

export interface SelfAssessment {
  submitted_at: string | null;
  note: string | null;
  scores: SelfAssessmentScoreRow[];
}

export interface EvaluationScoreRow {
  id: number;
  indicator_id: number;
  score: number;
  evidence_text: string | null;
}

export type CommentStage = "hr_review" | "deputy_review" | "ceo_final";

export interface EvaluationCommentRow {
  id: number;
  commenter_user_id: number;
  commenter_username: string | null;
  parent_comment_id: number | null;
  stage: CommentStage;
  comment_text: string;
  created_at: string;
}

export interface EvaluationDetail extends EvaluationRecord {
  scores: EvaluationScoreRow[];
  comments: EvaluationCommentRow[];
  // دیدگاه خودِ فرد، کنار امتیاز ارزیاب. null یعنی چیزی ثبت نکرده (کاملاً مجاز).
  self_assessment: SelfAssessment | null;
  // شاخص‌های *این* پرونده، نه شاخص‌های فعالِ امروز (P1-05).
  //
  // فرم باید از روی این ساخته شود. فیلترکردن با `is_active` — کاری که پیش از
  // این می‌کردیم — همان خرابیِ سمت سرور را در مرورگر تکرار می‌کند: ارزیاب
  // سؤالی می‌بیند که پرونده‌اش نمی‌خواهد، یا سؤالی نمی‌بیند که برای ثبت لازم است.
  indicator_ids: number[];
  indicator_framework_version: number | null;
}

/** وضعیت → مرحله. آینهٔ `_STAGE_BY_STATUS` در `schemas/evaluation.py`.
 *
 * `cancelled` عمداً این‌جا نیست: پروندهٔ لغوشده در هیچ مرحله‌ای «نیست» و
 * نسبت‌دادن یک مرحله به آن گمراه‌کننده است.
 */
export const STAGE_BY_STATUS: Partial<Record<EvaluationStatus, EvaluationStage>> = {
  draft: "supervisor_scoring",
  submitted: "hr_review",
  hr_approved: "deputy_review",
  deputy_approved: "ceo_final",
  finalized: "ceo_final",
};

export const STAGE_LABELS: Record<EvaluationStage, string> = {
  supervisor_scoring: "امتیازدهی مسئول واحد",
  hr_review: "بررسی منابع انسانی",
  deputy_review: "بررسی معاونت",
  ceo_final: "تأیید نهایی مدیرعامل",
};

export interface UnitStat {
  org_unit: string;
  // null = سرکوب‌شده: جمعیت این واحد کمتر از آستانهٔ کوهورت است (P1-08)
  avg_final_pct: number | null;
  count: number;
  /** تفکیک همان میانگین به دو بخشِ فرم — واحدی که کلش خوب است ممکن است در یکی
   *  از دو بخش ضعیف باشد و عددِ کل آن را پنهان کند. */
  avg_general_pct: number | null;
  avg_specialized_pct: number | null;
  site: string | null;
}

export interface EvaluatorStat {
  evaluator_user_id: number;
  username: string;
  full_name: string | null;
  avg_final_pct: number | null;
  subordinate_count: number;
  evaluation_count: number;
}

export interface IndicatorStat {
  indicator_id: number;
  category: string;
  /** شرح خودِ شاخص — چند شاخص می‌توانند یک «دسته» داشته باشند. */
  description: string;
  avg_score: number | null;
}

export interface PersonStat {
  personnel_id: number;
  full_name: string;
  final_weighted_pct: number;
  org_unit: string;
  site: string | null;
}

/** چند درصد افراد کجای طیف‌اند. مرزها از خودِ «طرح نمره‌دهی» می‌آیند، نه از
 *  عددی که در رابط نوشته شده باشد. */
export interface OutcomeMix {
  strong_pct: number | null;
  needs_improvement_pct: number | null;
  strong_threshold_pct: number;
  improvement_threshold_pct: number;
  people_counted: number;
}

export interface DashboardOverview {
  total_evaluations: number;
  avg_final_pct: number | null;
  outcome_mix: OutcomeMix;
  by_org_unit: UnitStat[];
  by_evaluator: EvaluatorStat[];
  lowest_by_indicator: IndicatorStat[];
  highest_by_indicator: IndicatorStat[];
  lowest_by_specialized_indicator: IndicatorStat[];
  highest_by_specialized_indicator: IndicatorStat[];
  lowest_by_unit: UnitStat[];
  lowest_by_person: PersonStat[];
}

export interface RadarPoint {
  category: string;
  avg_score: number;
}

// ─────────── گزارش‌های تحلیلی فیلترشوندهٔ HR ───────────

export interface ReportFilters {
  period_id?: number;
  org_unit?: string;
  personnel_id?: number;
  created_from?: string;
  created_to?: string;
  /** وضعیت پرسنل */
  status?: PersonnelStatus;
  contract_end_from?: string;
  contract_end_to?: string;
}

export interface IndicatorReportStat {
  indicator_id: number;
  category: string;
  description: string;
  section: IndicatorSection;
  avg_score: number | null;
  count: number;
}

export interface ReportSummary {
  total_evaluations: number;
  avg_final_pct: number | null;
  by_org_unit: UnitStat[];
  by_indicator: IndicatorReportStat[];
}

export interface UnitIndicatorStat {
  org_unit: string;
  avg_score: number | null;
  count: number;
}

export interface IndicatorBreakdown {
  indicator_id: number;
  category: string;
  description: string;
  overall_avg: number | null;
  count: number;
  by_org_unit: UnitIndicatorStat[];
}

export interface EmployeeEvaluationPoint {
  evaluation_code: string;
  finalized_at: string;
  final_weighted_pct: number;
}

export interface EmployeeVsUnit {
  personnel_id: number;
  full_name: string;
  org_unit: string;
  employee_avg: number | null;
  unit_avg: number | null;
  evaluation_count: number;
  unit_evaluation_count: number;
  per_evaluation: EmployeeEvaluationPoint[];
}

export interface TrendPoint {
  evaluation_code: string;
  finalized_at: string;
  final_weighted_pct: number;
}

export interface AuditLogEntry {
  id: number;
  evaluation_record_id: number | null;
  evaluation_code: string | null;
  actor_user_id: number;
  actor_username: string | null;
  actor_display_name: string | null;
  event_type: string;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogPage {
  total: number;
  items: AuditLogEntry[];
}

export const AUDIT_EVENT_LABELS: Record<string, string> = {
  status_changed: "تغییر وضعیت",
  score_submitted: "ثبت امتیاز",
  scores_draft_saved: "ذخیره پیش‌نویس امتیاز",
  indicator_created: "افزودن شاخص",
  indicator_updated: "ویرایش شاخص",
  indicators_reordered: "تغییر ترتیب شاخص‌ها",
  indicator_deleted: "حذف شاخص",
  user_created: "ساخت کاربر",
  user_updated: "ویرایش کاربر",
  personnel_created: "افزودن پرسنل",
  personnel_updated: "ویرایش پرسنل",
  access_updated: "تنظیم دسترسی ارزیابی",
  access_supervisor_cleared_on_manager_title: "حذف خودکار مسئول واحد (تغییر عنوان به مدیر)",
  comment_added: "ثبت کامنت",
  comment_reply_added: "ثبت پاسخ به کامنت",
  period_created: "ایجاد دوره ارزیابی",
  period_closed: "بستن دوره ارزیابی",
  scheduled_jobs_run: "اجرای یادآوری‌های خودکار",
  evaluation_returned: "برگشت پرونده",
  evaluation_acknowledged: "رؤیت نتیجه توسط کارمند",
  improvement_plan_created: "ایجاد برنامه بهبود",
  improvement_plan_updated: "ویرایش برنامه بهبود",
  improvement_plan_completed: "تکمیل برنامه بهبود",
  improvement_plan_cancelled: "لغو برنامه بهبود",
  excel_exported: "خروجی Excel ارزیابی‌ها",
  personnel_excel_exported: "خروجی Excel پرسنل",
  users_excel_exported: "خروجی Excel کاربران",
  improvement_plans_excel_exported: "خروجی Excel برنامه‌های بهبود",
  audit_log_excel_exported: "خروجی Excel گزارش رویدادها",
  pdf_downloaded: "دریافت PDF",
  login_succeeded: "ورود موفق",
  login_failed: "ورود ناموفق",
  password_changed_self: "تغییر رمز توسط خود کاربر",
  account_locked: "قفل حساب پس از تلاش‌های ناموفق",
  hr_case_claimed: "برداشتن پرونده توسط منابع انسانی",
  hr_case_handed_over: "واگذاری مسئولیت منابع انسانی",
  evaluation_cancelled: "لغو پرونده",
  stage_owner_reassigned: "تغییر مسئول مرحله",
  self_assessment_submitted: "ثبت خودارزیابی کارمند",
  evaluation_objection_filed: "ثبت اعتراض کارمند",
  evaluation_objection_resolved: "پاسخ به اعتراض کارمند",
  improvement_goal_added: "افزودن هدف برنامه بهبود",
  improvement_goal_updated: "ویرایش هدف برنامه بهبود",
  improvement_goal_deleted: "حذف هدف برنامه بهبود",
  report_excel_exported: "خروجی اکسل گزارش تحلیلی",
};

export const STATUS_LABELS: Record<EvaluationStatus, string> = {
  draft: "پیش‌نویس",
  submitted: "ثبت‌شده",
  hr_approved: "تأییدشده توسط HR",
  deputy_approved: "تأییدشده توسط معاونت",
  finalized: "نهایی‌شده",
  cancelled: "لغوشده",
};

/** وضعیت‌های «باز» — یعنی پرونده هنوز در جریان است.
 *
 *  قرینهٔ `OPEN_STATUSES` در بک‌اند. تا امروز فرانت همه‌جا `status !== "finalized"`
 *  می‌نوشت، که پروندهٔ **لغوشده** را هم «باز» می‌شمرد: نتیجه‌اش دکمهٔ «ادامه
 *  ارزیابی باز» روی فردی بود که هیچ پروندهٔ بازی نداشت و در واقع باید ارزیابی
 *  تازه‌ای برایش شروع می‌شد. وضعیت پایانیِ بعدی فقط همین‌جا اضافه می‌شود.
 */
export const OPEN_STATUSES: EvaluationStatus[] = [
  "draft",
  "submitted",
  "hr_approved",
  "deputy_approved",
];

export const isOpenStatus = (status: EvaluationStatus): boolean =>
  OPEN_STATUSES.includes(status);

export interface Page<T> {
  total: number;
  items: T[];
}

export interface AppConfig {
  evidence_min_words: number;
  evidence_max_words: number;
  /** امتیازهایی که شواهد عینی برایشان اجباری است (پیش‌فرض [۱، ۵]). */
  evidence_required_scores: number[];
  general_section_weight: number;
  specialized_section_weight: number;
  /** سقف امتیاز ویژه در طرح فعال؛ صفر یعنی فرم این بخش را نشان ندهد. */
  bonus_max_points: number;
  /** حداقل تعداد نویسهٔ توضیح، وقتی امتیاز ویژه بیشتر از صفر است. */
  bonus_reason_min_length: number;
}

export const DEFAULT_APP_CONFIG: AppConfig = {
  evidence_min_words: 3,
  evidence_max_words: 40,
  evidence_required_scores: [1, 5],
  general_section_weight: 0.6,
  specialized_section_weight: 0.4,
  bonus_max_points: 5,
  bonus_reason_min_length: 10,
};

export interface AppNotification {
  id: number;
  type: string;
  message: string;
  link: string | null;
  evaluation_record_id: number | null;
  created_at: string;
  read_at: string | null;
}

export interface NotificationPage {
  total: number;
  unread: number;
  items: AppNotification[];
}

export interface ExpiringContract {
  personnel_id: number;
  full_name: string;
  org_unit: string;
  contract_end_date: string;
  days_remaining: number;
  has_open_evaluation: boolean;
}

/** آمار یک شخص در یک مرحله. */
export interface StageOwnerStat {
  name: string;
  total: number;
  active: number;
  closed: number;
  avg_dwell_days: number | null;
  longest_active_days: number | null;
}

/** وضعیت یک مرحله از گردش‌کار. */
export interface StageStat {
  status: EvaluationStatus;
  /** «الان روی میزِ چه کسی است» — نه اینکه چه کسی کارش را کرده. */
  holder: string;
  total: number;
  active: number;
  closed: number;
  /** چند بار ورود به این مرحله رخ داده؛ بیشتر بودنش از total یعنی برگشت. */
  passes: number;
  share_pct: number;
  avg_dwell_days: number | null;
  longest_active_days: number | null;
  by_owner: StageOwnerStat[];
}

export interface PipelineStat {
  status: EvaluationStatus;
  count: number;
  oldest_created_at: string | null;
}

export type PeriodStatus = "open" | "closed";

export interface EvaluationPeriod {
  id: number;
  name: string;
  starts_on: string;
  ends_on: string;
  status: PeriodStatus;
  created_at: string;
  closed_at: string | null;
}

export interface NotStartedPersonnel {
  personnel_id: number;
  full_name: string;
  org_unit: string;
}

export type RoleOverviewTone = "neutral" | "amber" | "pulse" | "green";

export interface RoleOverviewCard {
  key: string;
  label: string;
  value: number;
  tone: RoleOverviewTone;
  hint: string | null;
  /** واحدی که بعد از عدد می‌آید («٪») — تا کاشیِ درصد از کاشیِ تعداد جدا باشد. */
  suffix: string | null;
}

export interface RoleOverview {
  role: UserRole;
  cards: RoleOverviewCard[];
}

export interface InProgressEvaluation {
  evaluation_id: number;
  evaluation_code: string;
  status: EvaluationStatus;
  was_returned: boolean;
  created_at: string;
}

export type ImprovementPlanStatus = "open" | "completed" | "cancelled";

export const IMPROVEMENT_PLAN_STATUS_LABELS: Record<ImprovementPlanStatus, string> = {
  open: "باز",
  completed: "تکمیل‌شده",
  cancelled: "لغوشده",
};

export interface ImprovementGoal {
  id: number;
  description: string;
  is_done: boolean;
  display_order: number;
}

export interface ImprovementPlan {
  id: number;
  evaluation_record_id: number;
  personnel_id: number;
  personnel_full_name: string;
  title: string;
  owner_user_id: number | null;
  status: ImprovementPlanStatus;
  review_date: string;
  summary: string | null;
  follow_up_evaluation_id: number | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface ImprovementPlanDetail extends ImprovementPlan {
  goals: ImprovementGoal[];
}

export interface EligibleEvaluation {
  evaluation_record_id: number;
  evaluation_code: string;
  personnel_id: number;
  personnel_full_name: string;
  final_weighted_pct: number | null;
  finalized_at: string | null;
}

export interface PeriodProgress {
  period: EvaluationPeriod;
  eligible: number;
  started: number;
  finalized: number;
  /** شروع‌شده ولی نهایی‌نشده — نقطهٔ تصمیمِ بستن دوره */
  in_progress: number;
  /** کل شروع‌نشده‌ها؛ `not_started` ممکن است بریده شده باشد */
  not_started_total: number;
  not_started: NotStartedPersonnel[];
  /** پرسنل فعالی که زنجیرهٔ ارزیابی ندارند — شکافی که پیش از این از مخرجِ
   *  پوشش حذف می‌شد و دیده نمی‌شد. */
  without_chain_total: number;
  without_chain: NotStartedPersonnel[];
}

// ── همکار هوشمند (دستیار) ────────────────────────────────────────────────

export interface AiStatus {
  available: boolean;
  /** اگر در دسترس نیست، *چرا* — به زبان قابل‌اقدام. */
  reason: string;
  allow_write_actions: boolean;
  /** بارگذاری فایل برای این کاربر ممکن است یا نه */
  allow_uploads?: boolean;
}

/** @deprecated کنش‌های قدیمی؛ حالا در PendingAction زندگی می‌کنند. */
export interface AiAction {
  name: string;
  /** جمله‌ای که زیرِ دکمهٔ تأیید نوشته می‌شود — به نام، نه به شناسه. */
  summary: string;
  payload: Record<string, unknown>;
}

/** ردِ یک فراخوانیِ ابزار در نوبتِ همکار — «چه کاری واقعاً انجام شد». */
export interface AiStep {
  tool: string;
  status: "ok" | "awaiting_confirmation" | "error" | "confirmed" | "rejected";
  summary: string;
  detail: Record<string, unknown>;
}

/** کنشِ تغییردهندهٔ پیشنهادی که منتظرِ تصمیمِ کاربر است. */
export interface AiPendingAction {
  id: number;
  tool: string;
  summary: string;
  arguments: Record<string, unknown>;
  status: "pending" | "confirmed" | "rejected" | "expired" | "failed";
  result_text?: string;
  expires_at?: string;
}

export interface AiTool {
  name: string;
  description: string;
  category: string;
  read_only: boolean;
  risky: boolean;
}

export interface AiConversation {
  id: number;
  title: string;
  updated_at: string;
}

export interface AiMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  actions: AiAction[];
  steps?: AiStep[];
  pending?: AiPendingAction[];
}

export interface AiUploadInfo {
  id: number;
  filename: string;
  kind: "personnel_import" | "excel" | "file";
  size_bytes: number;
  total_rows: number;
  valid_count: number;
  invalid_count: number;
  committed: boolean;
  note?: string;
}

export interface AiChatTurn {
  conversation_id: number;
  reply: string;
  steps: AiStep[];
  pending: AiPendingAction[];
  usage?: Record<string, unknown>;
}

export interface AiProviderOption {
  id: string;
  label: string;
  base_url: string;
  default_model: string;
  note: string;
}

export interface AiSettings {
  enabled: boolean;
  provider: string;
  /** فهرست سرویس‌های آماده — از سرور می‌آید، نه از یک ثابت در فرانت‌اند. */
  providers: AiProviderOption[];
  base_url: string;
  model: string;
  api_key_hint: string;
  api_key_configured: boolean;
  temperature: number;
  max_tokens: number;
  timeout_seconds: number;
  instructions: string;
  restrict_to_platform: boolean;
  context_record_limit: number;
  allow_write_actions: boolean;
  max_user_chars: number;
  max_tool_iterations: number;
  allow_uploads: boolean;
  max_upload_mb: number;
}

export interface AiUserAccess {
  user_id: number;
  username: string;
  display_name: string;
  role: string;
  enabled: boolean;
  api_key_hint: string;
  api_key_configured: boolean;
  model: string;
  allow_write_actions: boolean;
  daily_message_limit: number;
}
