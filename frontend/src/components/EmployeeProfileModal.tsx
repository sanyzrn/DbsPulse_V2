import type { ReactNode } from "react";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Area,
  AreaChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { usePersonRadar, usePersonTrend, usePersonnelDetail } from "../api/queries";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { formatDate } from "../utils/dates";

const BRAND_FROM = "#b61615";
const BRAND_TO = "#374151";
const GRID_STROKE = "#eef0f4";
const AXIS_STROKE = "#e5e7eb";
const TICK_STYLE = { fontSize: 11, fill: "#6b7280", fontFamily: "Vazirmatn, Tahoma, sans-serif" };
const TOOLTIP_STYLE = {
  direction: "rtl" as const,
  fontFamily: "Vazirmatn, Tahoma, sans-serif",
  fontSize: 12,
  borderRadius: 12,
  border: "1px solid #eef0f4",
  boxShadow: "0 12px 40px rgba(0,0,0,0.12)",
  background: "rgba(255,255,255,0.95)",
  backdropFilter: "blur(8px)",
};
function tooltipNumber(value: unknown): string {
  return typeof value === "number" ? value.toLocaleString("fa-IR") : String(value);
}

function InfoRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="mt-0.5 font-medium text-gray-800">{value}</p>
    </div>
  );
}

/** پروفایل همیشه‌دردسترس پرسنل: اطلاعات پایه + رادار شایستگی + روند امتیاز نهایی.
 * توسط HR (از فهرست پرسنل/برنامه‌های بهبود) و ارزیاب‌ها (مسئول واحد/معاونت از فهرست
 * افراد زیرمجموعه) استفاده می‌شود؛ بک‌اند دسترسی ارزیاب را به افراد حوزهٔ خودش محدود
 * می‌کند. شناسه پرسنل کافی است — خود مودال جزئیات را می‌گیرد، پس فراخوان‌ها لازم
 * نیست از قبل شیء کامل Personnel را در دست داشته باشند. */
export function EmployeeProfileModal({
  personnelId,
  personName,
  onClose,
}: {
  personnelId: number;
  /** برای نمایش عنوان مودال پیش از رسیدن پاسخ personnel detail (تجربه سریع‌تر) */
  personName?: string;
  onClose: () => void;
}) {
  const { data: personnel } = usePersonnelDetail(personnelId);
  const { data: radar = [] } = usePersonRadar(personnelId);
  const { data: trend = [] } = usePersonTrend(personnelId);

  if (!personnel) {
    return (
      <Modal
        title={`پروفایل پرسنل${personName ? `: ${personName}` : ""}`}
        onClose={onClose}
        size="lg"
        footer={<Button onClick={onClose}>بستن</Button>}
      >
        <div className="space-y-3 py-4">
          <div className="skeleton h-24" />
          <div className="skeleton h-64" />
        </div>
      </Modal>
    );
  }

  return (
    <Modal title={`پروفایل پرسنل: ${personnel.full_name}`} onClose={onClose} size="lg" footer={<Button onClick={onClose}>بستن</Button>}>
      <div className="space-y-5 py-2">
        <div className="grid grid-cols-1 gap-3 rounded-2xl bg-gray-50 p-4 text-sm sm:grid-cols-2">
          <InfoRow label="کد پرسنلی" value={personnel.personnel_code} />
          <InfoRow label="عنوان شغلی" value={personnel.job_title} />
          <InfoRow label="واحد سازمانی" value={personnel.org_unit} />
          <InfoRow
            label="وضعیت"
            value={
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  personnel.status === "active" ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-600"
                }`}
              >
                <span
                  aria-hidden
                  className={`h-1.5 w-1.5 rounded-full ${personnel.status === "active" ? "bg-green-500" : "bg-gray-400"}`}
                />
                {personnel.status === "active" ? "فعال" : "غیرفعال"}
              </span>
            }
          />
          <InfoRow label="شروع قرارداد" value={formatDate(personnel.contract_start_date)} />
          <InfoRow label="پایان قرارداد" value={formatDate(personnel.contract_end_date)} />
          {personnel.is_manager && (
            <div className="sm:col-span-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-gradient-to-bl from-amber-50 to-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700">
                پرسنل مدیریتی (ارزیابی مستقیم توسط معاونت)
              </span>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div>
            <h3 className="mb-3 text-sm font-semibold text-gray-600">میانگین امتیاز هر شاخص (از ۵)</h3>
            <div style={{ height: 260 }}>
              {radar.length === 0 ? (
                <p className="pt-16 text-center text-sm text-gray-400">داده‌ای برای این فرد یافت نشد.</p>
              ) : (
                <ResponsiveContainer>
                  <RadarChart data={radar} margin={{ top: 12, right: 24, bottom: 12, left: 24 }}>
                    <defs>
                      <linearGradient id="profile-radar-fill" x1="0" y1="0" x2="1" y2="1">
                        <stop offset="0%" stopColor={BRAND_FROM} stopOpacity={0.5} />
                        <stop offset="100%" stopColor={BRAND_TO} stopOpacity={0.2} />
                      </linearGradient>
                    </defs>
                    <PolarGrid stroke={GRID_STROKE} />
                    <PolarAngleAxis dataKey="category" tick={{ ...TICK_STYLE, fontSize: 10 }} />
                    <PolarRadiusAxis domain={[0, 5]} tickCount={6} tick={TICK_STYLE} stroke={GRID_STROKE} axisLine={false} />
                    <Radar
                      dataKey="avg_score"
                      name="میانگین امتیاز"
                      stroke={BRAND_FROM}
                      strokeWidth={2}
                      fill="url(#profile-radar-fill)"
                      dot={{ r: 3.5, fill: BRAND_TO, strokeWidth: 0 }}
                    />
                    <Tooltip contentStyle={TOOLTIP_STYLE} formatter={tooltipNumber} />
                  </RadarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
          <div>
            <h3 className="mb-3 text-sm font-semibold text-gray-600">روند امتیاز نهایی (٪)</h3>
            <div style={{ height: 260 }}>
              {trend.length === 0 ? (
                <p className="pt-16 text-center text-sm text-gray-400">روندی برای این فرد ثبت نشده است.</p>
              ) : (
                <ResponsiveContainer>
                  <AreaChart data={trend} margin={{ top: 12, right: 16, bottom: 12, left: 0 }}>
                    <defs>
                      <linearGradient id="profile-trend-fill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={BRAND_FROM} stopOpacity={0.4} />
                        <stop offset="100%" stopColor={BRAND_TO} stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="4 4" stroke={GRID_STROKE} vertical={false} />
                    <XAxis dataKey="evaluation_code" tick={TICK_STYLE} tickLine={false} axisLine={{ stroke: AXIS_STROKE }} />
                    <YAxis domain={[0, 100]} tick={TICK_STYLE} tickLine={false} axisLine={false} width={36} />
                    <Tooltip contentStyle={TOOLTIP_STYLE} formatter={tooltipNumber} />
                    <Area
                      type="monotone"
                      dataKey="final_weighted_pct"
                      name="امتیاز نهایی"
                      stroke={BRAND_FROM}
                      strokeWidth={2.5}
                      fill="url(#profile-trend-fill)"
                      dot={{ r: 4, fill: "#fff", strokeWidth: 2.5, stroke: BRAND_TO }}
                      activeDot={{ r: 6, fill: BRAND_TO, strokeWidth: 2, stroke: "#fff" }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </div>
      </div>
    </Modal>
  );
}
