import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { apiClient } from "./client";
import {
  DEFAULT_APP_CONFIG,
  type AppConfig,
  type AppNotification,
  type AppUser,
  type AuditLogPage,
  type DashboardOverview,
  type EvaluationDetail,
  type EvaluationRecord,
  type EligibleEvaluation,
  type EvaluationPeriod,
  type EvaluationStatus,
  type ExpiringContract,
  type ImprovementPlan,
  type ImprovementPlanDetail,
  type ImprovementPlanStatus,
  type Indicator,
  type InProgressEvaluation,
  type MyEvaluation,
  type NotificationPage,
  type Page,
  type PeriodProgress,
  type Personnel,
  type PipelineStat,
  type RadarPoint,
  type RoleOverview,
  type TrendPoint,
  type UserRole,
} from "../types";

/** مقدار ورودی را با تأخیر برمی‌گرداند تا هر کلید تایپ‌شده یک درخواست جست‌وجو نشود. */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}

/** قوانین کسب‌وکار از سرور (یک‌بار در هر نشست)؛ تا رسیدن پاسخ، مقادیر پیش‌فرض همان قوانین فعلی‌اند. */
export function useAppConfig(): AppConfig {
  const { data } = useQuery({
    queryKey: ["config"],
    queryFn: async () => (await apiClient.get<AppConfig>("/config")).data,
    staleTime: Infinity,
  });
  return data ?? DEFAULT_APP_CONFIG;
}

export interface EvaluationListParams {
  q?: string;
  status?: EvaluationStatus;
  /** فیلترهای پیشرفتهٔ HR — همگی اختیاری و ترکیب‌پذیر */
  org_unit?: string;
  created_from?: string;
  created_to?: string;
  min_final_pct?: number;
  max_final_pct?: number;
  subject_personnel_id?: number;
  was_returned?: boolean;
  limit: number;
  offset: number;
}

/** مقادیر خالی/undefined را حذف می‌کند تا query string تمیز بماند. */
function compactParams(params: object): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
  );
}

export function useEvaluations(params: EvaluationListParams) {
  return useQuery({
    queryKey: ["evaluations", params],
    queryFn: async () =>
      (
        await apiClient.get<Page<EvaluationRecord>>("/evaluations", {
          params: compactParams(params),
        })
      ).data,
    placeholderData: keepPreviousData,
  });
}

/** واحدهای سازمانی متمایز (فقط HR) — گزینه‌های فیلتر «واحد». */
/** محل‌ها — سه محلِ رسمیِ سازمان، به‌علاوهٔ هرچه در داده هست.
 *
 *  از سرور می‌آید و نه از روی `org_unit`ها ساخته می‌شود: محلی که هنوز کسی در آن
 *  ثبت نشده باید در فهرست باشد، وگرنه ثبتِ اولین نفرش ممکن نیست.
 */
export function useSites(enabled: boolean) {
  return useQuery({
    queryKey: ["personnel", "sites"],
    queryFn: async () => (await apiClient.get<string[]>("/personnel/sites")).data,
    enabled,
    staleTime: 300_000,
  });
}

export function useOrgUnits(enabled: boolean) {
  return useQuery({
    queryKey: ["personnel", "org-units"],
    queryFn: async () => (await apiClient.get<string[]>("/personnel/org-units")).data,
    enabled,
    staleTime: 300_000,
  });
}

export function useEvaluationDetail(id: number | null) {
  return useQuery({
    queryKey: ["evaluation", id],
    queryFn: async () => (await apiClient.get<EvaluationDetail>(`/evaluations/${id}`)).data,
    enabled: id !== null,
    retry: false,
  });
}

export interface PersonnelListParams {
  accessible_to_me?: boolean;
  q?: string;
  /** فیلترهای پیشرفتهٔ HR — همگی اختیاری و ترکیب‌پذیر */
  status?: "active" | "inactive";
  org_unit?: string;
  is_manager?: boolean;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
  limit: number;
  offset: number;
}

export function usePersonnelList(params: PersonnelListParams) {
  return useQuery({
    queryKey: ["personnel", params],
    queryFn: async () =>
      (
        await apiClient.get<Page<Personnel>>("/personnel", {
          params: compactParams(params),
        })
      ).data,
    placeholderData: keepPreviousData,
  });
}

export function usePersonnelDetail(id: number | null) {
  return useQuery({
    queryKey: ["personnel", "detail", id],
    queryFn: async () => (await apiClient.get<Personnel>(`/personnel/${id}`)).data,
    enabled: id !== null,
    retry: false,
  });
}

export function useUsersList({
  enabled = true,
  ...params
}: {
  role?: UserRole;
  q?: string;
  is_active?: boolean;
  limit: number;
  offset?: number;
  /** فهرست کاربران endpointای مخصوص HR است؛ صفحه‌هایی که نقش‌های دیگر هم بازشان
   *  می‌کنند باید بتوانند این واکشی را خاموش کنند تا ۴۰۳ بی‌مورد نگیرند. */
  enabled?: boolean;
}) {
  return useQuery({
    queryKey: ["users", params],
    queryFn: async () =>
      (
        await apiClient.get<Page<AppUser>>("/users", {
          params: compactParams(params),
        })
      ).data,
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function useIndicators(options?: { section?: "general" | "specialized"; includeInactive?: boolean }) {
  return useQuery({
    queryKey: ["indicators", options ?? {}],
    queryFn: async () =>
      (
        await apiClient.get<Indicator[]>("/indicators", {
          params: {
            section: options?.section,
            include_inactive: options?.includeInactive ?? false,
          },
        })
      ).data,
  });
}

export function useAuditLog(params: {
  event_type?: string;
  created_from?: string;
  created_to?: string;
  actor_user_id?: number;
  personnel_id?: number;
  org_unit?: string;
  contract_end_from?: string;
  contract_end_to?: string;
  limit: number;
  offset: number;
}) {
  return useQuery({
    queryKey: ["audit-log", params],
    queryFn: async () =>
      (
        await apiClient.get<AuditLogPage>("/audit-log", {
          params: compactParams(params),
        })
      ).data,
    placeholderData: keepPreviousData,
  });
}

export function useDashboardOverview() {
  return useQuery({
    queryKey: ["dashboard", "overview"],
    queryFn: async () => (await apiClient.get<DashboardOverview>("/dashboard/overview")).data,
  });
}

export function usePersonRadar(personnelId: number | null) {
  return useQuery({
    queryKey: ["dashboard", "radar", personnelId],
    queryFn: async () =>
      (await apiClient.get<RadarPoint[]>(`/dashboard/personnel/${personnelId}/radar`)).data,
    enabled: personnelId !== null,
  });
}

export function usePersonTrend(personnelId: number | null) {
  return useQuery({
    queryKey: ["dashboard", "trend", personnelId],
    queryFn: async () =>
      (await apiClient.get<TrendPoint[]>(`/dashboard/personnel/${personnelId}/trend`)).data,
    enabled: personnelId !== null,
  });
}

export function useRoleOverview() {
  return useQuery({
    queryKey: ["dashboard", "role-overview"],
    queryFn: async () => (await apiClient.get<RoleOverview>("/dashboard/role-overview")).data,
    staleTime: 30_000,
  });
}

export function usePersonInProgress(personnelId: number | null) {
  return useQuery({
    queryKey: ["dashboard", "in-progress", personnelId],
    queryFn: async () =>
      (
        await apiClient.get<InProgressEvaluation | null>(
          `/dashboard/personnel/${personnelId}/in-progress`
        )
      ).data,
    enabled: personnelId !== null,
  });
}

export function useNotifications() {
  return useQuery({
    queryKey: ["notifications"],
    queryFn: async () =>
      (await apiClient.get<NotificationPage>("/notifications", { params: { limit: 15 } })).data,
    // اعلان‌ها با polling می‌آیند، پس «تأخیر» همان فاصلهٔ دو درخواست است. دو
    // چیز آن را بی‌دلیل بزرگ می‌کرد:
    //
    // ۱. فاصله ثابت ۱۰ ثانیه بود، حتی وقتی کاربر مستقیم به صفحه نگاه می‌کند.
    // ۲. React Query تایمر را وقتی پنجره فوکوس ندارد *متوقف* می‌کند (مگر با
    //    refetchIntervalInBackground). یعنی تبی که در پس‌زمینه رها شده بود
    //    اصلاً به‌روز نمی‌شد و کاربر با برگشتن، صفی از اعلان‌های عقب‌مانده
    //    می‌دید — همان چیزی که «با تأخیر می‌آیند» حس می‌شود.
    //
    // حالا وقتی تب دیده می‌شود ۵ ثانیه، و در پس‌زمینه ۶۰ ثانیه. بار سرور تقریباً
    // همان است (پاسخ ۱۵ ردیفی)، ولی چیزی که کاربر می‌بیند تازه می‌ماند.
    // invalidate پس از اقدام‌های خودِ کاربر هم سر جایش است.
    refetchInterval: () => (document.visibilityState === "visible" ? 5_000 : 60_000),
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
  });
}

/** «کارنامه من»: نتایج نهایی‌شده ارزیابی خود کارمند (نقش employee). */
export function useMyEvaluations() {
  return useQuery({
    queryKey: ["me", "evaluations"],
    queryFn: async () => (await apiClient.get<Page<MyEvaluation>>("/me/evaluations")).data,
  });
}

/** پروندهٔ در جریانِ خود کارمند — فقط وضعیت، بدون امتیاز. */
export function useMyOpenEvaluations() {
  return useQuery({
    queryKey: ["me", "evaluations", "open"],
    queryFn: async () =>
      (await apiClient.get<import("../types").MyOpenEvaluation[]>("/me/evaluations/open")).data,
  });
}

/** برنامه‌های بهبودِ بازِ خود کارمند (فقط خواندنی). */
export function useMyImprovementPlans() {
  return useQuery({
    queryKey: ["me", "improvement-plans"],
    queryFn: async () =>
      (await apiClient.get<ImprovementPlanDetail[]>("/me/improvement-plans")).data,
  });
}

export function useImprovementPlans(params: {
  status?: ImprovementPlanStatus;
  q?: string;
  limit: number;
  offset: number;
}) {
  return useQuery({
    queryKey: ["improvement-plans", params],
    queryFn: async () =>
      (
        await apiClient.get<Page<ImprovementPlan>>("/improvement-plans", {
          params: { ...params, q: params.q || undefined },
        })
      ).data,
    placeholderData: keepPreviousData,
  });
}

export function useImprovementPlanDetail(id: number | null) {
  return useQuery({
    queryKey: ["improvement-plan", id],
    queryFn: async () =>
      (await apiClient.get<ImprovementPlanDetail>(`/improvement-plans/${id}`)).data,
    enabled: id !== null,
    retry: false,
  });
}

export function useEligibleEvaluations() {
  return useQuery({
    queryKey: ["improvement-plans", "eligible"],
    queryFn: async () =>
      (await apiClient.get<EligibleEvaluation[]>("/improvement-plans/eligible")).data,
  });
}

export function usePeriods() {
  return useQuery({
    queryKey: ["periods"],
    queryFn: async () => (await apiClient.get<EvaluationPeriod[]>("/periods")).data,
  });
}

export function usePeriodProgress(periodId: number | null) {
  return useQuery({
    queryKey: ["periods", "progress", periodId],
    queryFn: async () =>
      (await apiClient.get<PeriodProgress>(`/periods/${periodId}/progress`)).data,
    enabled: periodId !== null,
  });
}

export function useReportSummary(filters: import("../types").ReportFilters) {
  return useQuery({
    queryKey: ["dashboard", "report", "summary", filters],
    queryFn: async () =>
      (
        await apiClient.get<import("../types").ReportSummary>("/dashboard/report/summary", {
          params: compactParams(filters),
        })
      ).data,
    placeholderData: keepPreviousData,
  });
}

export function useIndicatorBreakdown(
  indicatorId: number | null,
  filters: import("../types").ReportFilters
) {
  return useQuery({
    queryKey: ["dashboard", "report", "indicator", indicatorId, filters],
    queryFn: async () =>
      (
        await apiClient.get<import("../types").IndicatorBreakdown>(
          `/dashboard/report/indicator/${indicatorId}`,
          { params: compactParams(filters) }
        )
      ).data,
    enabled: indicatorId !== null,
    placeholderData: keepPreviousData,
  });
}

export function useEmployeeVsUnit(
  personnelId: number | null,
  filters: { period_id?: number; created_from?: string; created_to?: string }
) {
  return useQuery({
    queryKey: ["dashboard", "report", "employee-vs-unit", personnelId, filters],
    queryFn: async () =>
      (
        await apiClient.get<import("../types").EmployeeVsUnit>("/dashboard/report/employee-vs-unit", {
          params: compactParams({ ...filters, personnel_id: personnelId ?? undefined }),
        })
      ).data,
    enabled: personnelId !== null,
    placeholderData: keepPreviousData,
  });
}

export function usePipeline() {
  return useQuery({
    queryKey: ["dashboard", "pipeline"],
    queryFn: async () => (await apiClient.get<PipelineStat[]>("/dashboard/pipeline")).data,
  });
}

export function useExpiringContracts(days: number) {
  return useQuery({
    queryKey: ["dashboard", "expiring-contracts", days],
    queryFn: async () =>
      (
        await apiClient.get<ExpiringContract[]>("/dashboard/expiring-contracts", {
          params: { days },
        })
      ).data,
    placeholderData: keepPreviousData,
  });
}

// AppNotification فقط برای type-export مصرف‌کنندگان این ماژول لازم است
export type { AppNotification };
