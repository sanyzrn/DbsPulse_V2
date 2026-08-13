/** نمودار میله‌ای افقی — یک پیاده‌سازی مشترک برای همهٔ نمودارهای «بزرگی» داشبورد.
 *
 * پیش از این چهار نسخهٔ کپی‌شده وجود داشت و هر چهار تا سه ایراد یکسان داشتند:
 *
 * ۱. میله‌ها کل ارتفاع باندشان را پر می‌کردند، پس با دو-سه دسته به بلوک‌های قرمزِ
 *    غول‌پیکر تبدیل می‌شدند. سقف ضخامت (۲۲px) یعنی باقی باند «هوا» می‌شود.
 * ۲. برچسب محور روی خود میله می‌افتاد، چون عرض محور برای متن فارسی کم بود و متن
 *    هم بلند بود. حالا متن متناسب با عرض واقعی محور کوتاه می‌شود و متن کامل در
 *    tooltip می‌آید.
 * ۳. شبکه نقطه‌چین بود؛ نقطه‌چین نویز بصری اضافه می‌کند و به‌غلط معنای «آستانه» یا
 *    «پیش‌بینی» می‌دهد. خط مو، یک پله از سطح.
 *
 * نکتهٔ RTL: چون صفحه `dir="rtl"` است، `text-anchor="start"` که Recharts برای
 * position="right" تولید می‌کند به‌جای «شروع از x» به «پایان در x» تفسیر می‌شود و
 * برچسب عدد داخل خود میله گم می‌شود. `direction: ltr` فقط روی همان برچسب رفعش می‌کند.
 */
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

/** یک هیو برای یک سری — رنگ کارِ «بزرگی» را می‌کند، نه هویت را. */
export const SERIES_COLOR = "#b61615";
export const MUTED_INK = "#6b7280";
const GRID_STROKE = "#eef0f4";
const AXIS_STROKE = "#e5e7eb";

// سقف ضخامت میله. با دستهٔ کم، باقی باند هوا می‌شود به‌جای یک بلوک تو‌پر.
const MAX_BAR_SIZE = 22;
const ROW_HEIGHT = 34;

const TICK_STYLE = {
  fontSize: 11,
  fill: MUTED_INK,
  fontFamily: "Vazirmatn, Tahoma, sans-serif",
};

const TOOLTIP_STYLE = {
  direction: "rtl" as const,
  fontFamily: "Vazirmatn, Tahoma, sans-serif",
  fontSize: 12,
  borderRadius: 12,
  border: "1px solid #eef0f4",
  boxShadow: "0 12px 40px rgba(0,0,0,0.12)",
  background: "rgba(255,255,255,0.97)",
};

const faNum = (value: unknown): string =>
  typeof value === "number" ? value.toLocaleString("fa-IR") : String(value);

export interface BarDatum {
  /** برچسب محور — کوتاه می‌شود تا با میله تصادف نکند */
  name: string;
  value: number;
  /** متن کامل برای tooltip، وقتی name کوتاه شده است */
  fullName?: string;
}

export function HorizontalBarChart({
  data,
  max,
  axisWidth = 150,
  valueFormatter = faNum,
  ariaLabel,
}: {
  data: BarDatum[];
  /** سقف محور مقدار — ۱۰۰ برای درصد، ۵ برای امتیاز شاخص */
  max: number;
  axisWidth?: number;
  valueFormatter?: (value: unknown) => string;
  ariaLabel?: string;
}) {
  // حدود ۶.۵ پیکسل به‌ازای هر نویسهٔ فارسی در اندازهٔ ۱۱px؛ کمی حاشیه نگه می‌داریم
  const maxChars = Math.max(8, Math.floor((axisWidth - 12) / 6.5));
  const rows = data.map((d) => ({
    ...d,
    fullName: d.fullName ?? d.name,
    name: d.name.length > maxChars ? `${d.name.slice(0, maxChars - 1).trimEnd()}…` : d.name,
  }));

  return (
    <div
      role="img"
      aria-label={ariaLabel}
      style={{ height: Math.max(120, rows.length * ROW_HEIGHT + 24) }}
    >
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ top: 8, right: 44, bottom: 8, left: 8 }}>
          {/* خط مو و توپر — نقطه‌چین نویز می‌سازد و معنای «آستانه» می‌دهد */}
          <CartesianGrid stroke={GRID_STROKE} horizontal={false} />
          <XAxis
            type="number"
            domain={[0, max]}
            tick={TICK_STYLE}
            tickLine={false}
            axisLine={{ stroke: AXIS_STROKE }}
            tickFormatter={faNum}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={TICK_STYLE}
            tickLine={false}
            axisLine={false}
            width={axisWidth}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={valueFormatter}
            labelFormatter={(_, payload) => payload?.[0]?.payload?.fullName ?? ""}
            cursor={{ fill: "rgba(107,114,128,0.06)" }}
          />
          <Bar
            dataKey="value"
            name="مقدار"
            fill={SERIES_COLOR}
            maxBarSize={MAX_BAR_SIZE}
            radius={[0, 4, 4, 0]}
            animationDuration={700}
          >
            {/* عدد در نوکِ میله، با رنگ متن نه رنگ سری */}
            <LabelList
              dataKey="value"
              position="right"
              formatter={(v: unknown) => (v == null ? "" : valueFormatter(v))}
              style={{
                fontSize: 11,
                fill: MUTED_INK,
                fontFamily: "Vazirmatn, Tahoma, sans-serif",
                direction: "ltr",
              }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
