import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AXIS_STROKE,
  GRID_STROKE,
  SERIES_COLOR,
  TICK_STYLE,
  TOOLTIP_STYLE,
  faNum,
} from "../ui/chartTokens";
import type { PeriodTrendPoint } from "../types";

/** روند میانگین سازمان، دوره به دوره.
 *
 *  یک عددِ امروز نمی‌گوید سازمان دارد بهتر می‌شود یا بدتر؛ دو عدد پشت سر هم
 *  می‌گویند. پس با کمتر از دو دوره اصلاً نمودار نمی‌کشیم و همین را می‌نویسیم —
 *  نمودارِ تک‌نقطه‌ای یک دایرهٔ سرگردان است که چیزی به کسی نمی‌گوید.
 *
 *  دوره‌هایی که میانگینشان به‌خاطر کم‌بودنِ جمعیت پنهان شده (`null`) از نمودار
 *  کنار می‌روند ولی در متنِ زیرش شمرده می‌شوند: خطی که از رویشان بپرد، شکافِ
 *  داده را شبیهِ روندِ صاف نشان می‌دهد.
 */
export function PeriodTrendChart({ data, height = 260 }: { data: PeriodTrendPoint[]; height?: number }) {
  const plotted = data.filter((point) => point.avg_final_pct !== null);
  const hidden = data.length - plotted.length;

  if (plotted.length < 2) {
    return (
      <p className="py-12 text-center text-sm text-gray-400">
        {data.length === 0
          ? "هنوز ارزیابی نهایی‌شده‌ای ثبت نشده است."
          : "روند از دومین دورهٔ دارای ارزیابی نهایی‌شده رسم می‌شود."}
      </p>
    );
  }

  return (
    <>
      <div style={{ height }}>
        <ResponsiveContainer>
          <AreaChart data={plotted} margin={{ top: 12, right: 16, bottom: 12, left: 0 }}>
            <defs>
              <linearGradient id="period-trend-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={SERIES_COLOR} stopOpacity={0.22} />
                <stop offset="100%" stopColor={SERIES_COLOR} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={GRID_STROKE} vertical={false} />
            <XAxis dataKey="name" tick={TICK_STYLE} tickLine={false} axisLine={{ stroke: AXIS_STROKE }} />
            <YAxis domain={[0, 100]} tick={TICK_STYLE} tickLine={false} axisLine={false} width={36} />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              formatter={(value: unknown, _name: unknown, item: { payload?: PeriodTrendPoint }) => [
                `${faNum(value)}٪ (${faNum(item.payload?.count ?? 0)} ارزیابی)`,
                "میانگین نهایی",
              ]}
            />
            <Area
              type="monotone"
              dataKey="avg_final_pct"
              name="میانگین نهایی"
              stroke={SERIES_COLOR}
              strokeWidth={2}
              fill="url(#period-trend-fill)"
              dot={{ r: 3, fill: "#fff", strokeWidth: 2, stroke: SERIES_COLOR }}
              activeDot={{ r: 5, fill: SERIES_COLOR, strokeWidth: 2, stroke: "#fff" }}
              animationDuration={700}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      {hidden > 0 && (
        <p className="mt-2 text-xs text-gray-400">
          {hidden.toLocaleString("fa-IR")} دوره نمایش داده نشده است، چون تعداد ارزیابی‌هایش کمتر از
          حدِ لازم برای ناشناس‌ماندن افراد بود.
        </p>
      )}
    </>
  );
}
