export type UserRole = "unit_supervisor" | "hr" | "deputy" | "ceo" | "employee";

export const ROLE_LABELS: Record<UserRole, string> = {
  unit_supervisor: "مسئول واحد",
  hr: "منابع انسانی",
  deputy: "معاونت",
  ceo: "مدیرعامل",
  employee: "کارمند",
};

export interface CurrentUser {
  id: number;
  username: string;
  role: UserRole;
  personnel_id: number | null;
  must_change_password: boolean;
}

export type PersonnelStatus = "active" | "inactive";

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
  created_at: string;
  updated_at: string;
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
  final_weighted_pct: number | null;
  recommendation: string | null;
  evaluator_comment: string | null;
  created_at: string;
  finalized_at: string | null;
  acknowledged_at: string | null;
  was_returned: boolean;
}

export interface MyEvaluation {
  id: number;
  evaluation_code: string;
  subject_full_name: string;
  period_id: number | null;
  general_score_pct: number | null;
  specialized_score_pct: number | null;
  final_weighted_pct: number | null;
  recommendation: string | null;
  finalized_at: string | null;
  acknowledged_at: string | null;
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
}

export const STAGE_LABELS: Record<EvaluationStage, string> = {
  supervisor_scoring: "امتیازدهی مسئول واحد",
  hr_review: "بررسی منابع انسانی",
  deputy_review: "بررسی معاونت",
  ceo_final: "تأیید نهایی مدیرعامل",
};

export interface UnitStat {
  org_unit: string;
  avg_final_pct: number;
  count: number;
}

export interface EvaluatorStat {
  evaluator_user_id: number;
  username: string;
  avg_final_pct: number;
  subordinate_count: number;
  evaluation_count: number;
}

export interface IndicatorStat {
  indicator_id: number;
  category: string;
  avg_score: number;
}

export interface PersonStat {
  personnel_id: number;
  full_name: string;
  final_weighted_pct: number;
}

export interface DashboardOverview {
  total_evaluations: number;
  avg_final_pct: number | null;
  by_org_unit: UnitStat[];
  by_evaluator: EvaluatorStat[];
  lowest_by_indicator: IndicatorStat[];
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
  avg_score: number;
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
  avg_score: number;
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
};

export const STATUS_LABELS: Record<EvaluationStatus, string> = {
  draft: "پیش‌نویس",
  submitted: "ثبت‌شده",
  hr_approved: "تأییدشده توسط HR",
  deputy_approved: "تأییدشده توسط معاونت",
  finalized: "نهایی‌شده",
  cancelled: "لغوشده",
};

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
}

export const DEFAULT_APP_CONFIG: AppConfig = {
  evidence_min_words: 3,
  evidence_max_words: 40,
  evidence_required_scores: [1, 5],
  general_section_weight: 0.6,
  specialized_section_weight: 0.4,
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
  not_started: NotStartedPersonnel[];
}
