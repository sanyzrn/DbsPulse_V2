/** نمودارهای کارنامهٔ فرد — رادار شایستگی و روند امتیاز.
 *
 * این دو تا عیناً در داشبورد و در مودال پروفایل تکرار شده بودند، با همان دو ایراد:
 *
 * ۱. برچسب‌های رادار روی هم می‌افتادند. ده دستهٔ فارسی دور یک دایره، با نام‌هایی تا
 *    ۲۷ نویسه، در ۳۲۰px جا نمی‌شوند — «کیفیت خروجی کار» و «رعایت الزامات واحد و
 *    سازمان» عملاً روی هم چاپ می‌شدند. حالا برچسب در حداکثر دو خط می‌شکند و شعاع
 *    نمودار کوچک‌تر شده تا جا باز شود.
 * ۲. با یک ارزیابی، نمودار روند یک نقطهٔ تنها بود. «روند» با یک نقطه معنا ندارد؛
 *    به‌جای نمودارِ توخالی، همان یک عدد را می‌نویسیم و می‌گوییم چرا روندی نیست.
 *
 * رادار عمداً به نقطه‌ای (DotPlot) تبدیل نشده: کار این نمودار «شکلِ» شایستگی در
 * چند بُعد است نه رتبه‌بندی، و همین شکل چیزی است که در کارنامه خوانده می‌شود.
 */
import {
  Area,
  AreaChart,
  CartesianGrid,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RadarPoint, TrendPoint } from "../types";

const SERIES_COLOR = "var(--chart-series)";
const GRID_STROKE = "var(--chart-grid)";
const AXIS_STROKE = "var(--chart-axis)";
const TICK_STYLE = { fontSize: 11, fill: "var(--chart-tick)", fontFamily: "Vazirmatn, Tahoma, sans-serif" };
const TOOLTIP_STYLE = {
  direction: "rtl" as const,
  fontFamily: "Vazirmatn, Tahoma, sans-serif",
  fontSize: 12,
  borderRadius: 12,
  border: "1px solid var(--chart-grid)",
  boxShadow: "0 12px 40px rgba(0,0,0,0.12)",
  background: "rgba(255,255,255,0.97)",
};

const faNum = (value: unknown) =>
  typeof value === "number" ? value.toLocaleString("fa-IR") : String(value);

const MAX_LINE = 16;
const MAX_LINES = 2;

/** برچسب را روی فاصله‌ها به حداکثر دو خط می‌شکند؛ اگر باز هم جا نشد، «…». */
export function wrapLabel(text: string, maxLine = MAX_LINE, maxLines = MAX_LINES): string[] {
  const lines: string[] = [];
  let current = "";
  for (const word of text.split(" ")) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= maxLine) {
      current = candidate;
      continue;
    }
    if (current) lines.push(current);
    current = word;
    if (lines.length === maxLines) break;
  }
  if (current && lines.length < maxLines) lines.push(current);

  if (lines.length === 0) return [text.slice(0, maxLine)];
  // هرچه از متن جا نشده در آخرین خط با … اعلام می‌شود، تا برچسب دروغ نگوید
  const shown = lines.join(" ");
  if (shown.length < text.length) {
    const last = lines[lines.length - 1]!;
    lines[lines.length - 1] = `${last.slice(0, Math.max(1, maxLine - 1))}…`;
  }
  return lines;
}

interface TickProps {
  x?: number;
  y?: number;
  /** Recharts بسته به موقعیت زاویه‌ای، لنگرِ متن را خودش تعیین می‌کند */
  textAnchor?: "inherit" | "start" | "middle" | "end";
  payload?: { value?: string };
}

function AngleTick({ x = 0, y = 0, textAnchor, payload }: TickProps) {
  const label = payload?.value ?? "";
  const lines = wrapLabel(label);
  return (
    <text
      x={x}
      y={y}
      textAnchor={textAnchor}
      fill={TICK_STYLE.fill}
      fontSize={10}
      fontFamily={TICK_STYLE.fontFamily}
    >
      <title>{label}</title>
      {lines.map((line, i) => (
        <tspan key={i} x={x} dy={i === 0 ? 0 : 11}>
          {line}
        </tspan>
      ))}
    </text>
  );
}

export function CompetencyRadar({
  data,
  gradientId,
  height = 340,
}: {
  data: RadarPoint[];
  /** شناسهٔ گرادیان باید در هر صفحه یکتا باشد، وگرنه دو نمودار هم‌زمان تداخل می‌کنند */
  gradientId: string;
  height?: number;
}) {
  if (data.length === 0) {
    return (
      <p className="py-16 text-center text-sm text-gray-400">داده‌ای برای این فرد یافت نشد.</p>
    );
  }
  return (
    <div style={{ height }}>
      <ResponsiveContainer>
        <RadarChart data={data} margin={{ top: 24, right: 40, bottom: 24, left: 40 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={SERIES_COLOR} stopOpacity={0.28} />
              <stop offset="100%" stopColor={SERIES_COLOR} stopOpacity={0.06} />
            </linearGradient>
          </defs>
          <PolarGrid stroke={GRID_STROKE} />
          {/* شعاع کوچک‌تر از پیش‌فرض، تا برچسب‌های دوخطی جا شوند */}
          <PolarAngleAxis dataKey="category" tick={<AngleTick />} radius={90} />
          <PolarRadiusAxis
            domain={[0, 5]}
            tickCount={6}
            tick={TICK_STYLE}
            stroke={GRID_STROKE}
            axisLine={false}
          />
          <Radar
            dataKey="avg_score"
            name="میانگین امتیاز"
            stroke={SERIES_COLOR}
            strokeWidth={2}
            fill={`url(#${gradientId})`}
            dot={{ r: 3.5, fill: SERIES_COLOR, strokeWidth: 0 }}
          />
          <Tooltip contentStyle={TOOLTIP_STYLE} formatter={faNum} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ScoreTrend({
  data,
  gradientId,
  height = 340,
}: {
  data: TrendPoint[];
  gradientId: string;
  height?: number;
}) {
  if (data.length === 0) {
    return (
      <p className="py-16 text-center text-sm text-gray-400">روندی برای این فرد ثبت نشده است.</p>
    );
  }

  // «روند» با یک نقطه وجود ندارد. نمودارِ تک‌نقطه‌ای فقط یک دایرهٔ سرگردان است؛
  // همان عدد را مستقیم می‌نویسیم و علتش را می‌گوییم.
  if (data.length === 1) {
    const only = data[0]!;
    return (
      <div
        className="flex flex-col items-center justify-center rounded-xl bg-gray-50 py-10 text-center"
        style={{ minHeight: height / 2 }}
      >
        <p className="text-3xl font-extrabold tabular-nums text-gray-900">
          {faNum(Math.round(only.final_weighted_pct))}٪
        </p>
        <p className="mt-1 text-xs text-gray-500">{only.evaluation_code}</p>
        <p className="mt-3 max-w-xs text-xs text-gray-400">
          تنها یک ارزیابی نهایی‌شده وجود دارد؛ روند از دومین ارزیابی به بعد رسم می‌شود.
        </p>
      </div>
    );
  }

  return (
    <div style={{ height }}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 12, right: 16, bottom: 12, left: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={SERIES_COLOR} stopOpacity={0.22} />
              <stop offset="100%" stopColor={SERIES_COLOR} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={GRID_STROKE} vertical={false} />
          <XAxis
            dataKey="evaluation_code"
            tick={TICK_STYLE}
            tickLine={false}
            axisLine={{ stroke: AXIS_STROKE }}
          />
          <YAxis domain={[0, 100]} tick={TICK_STYLE} tickLine={false} axisLine={false} width={36} />
          <Tooltip contentStyle={TOOLTIP_STYLE} formatter={faNum} />
          <Area
            type="monotone"
            dataKey="final_weighted_pct"
            name="امتیاز نهایی"
            stroke={SERIES_COLOR}
            strokeWidth={2.5}
            fill={`url(#${gradientId})`}
            dot={{ r: 4, fill: "#fff", strokeWidth: 2.5, stroke: SERIES_COLOR }}
            activeDot={{ r: 6, fill: SERIES_COLOR, strokeWidth: 2, stroke: "#fff" }}
            animationDuration={1200}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
