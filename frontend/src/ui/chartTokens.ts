/** نشانه‌های مشترکِ نمودارها.
 *
 *  همه از متغیرهای CSS می‌خوانند تا تمِ تیره با تعویضِ همان متغیرها درست شود، نه
 *  با یک شاخهٔ `if (dark)` در هر نمودار.
 *
 *  این‌ها یک بار در `PersonCharts` تعریف شده بودند؛ با اضافه‌شدنِ دومین خانوادهٔ
 *  نمودار (روند سازمان) جای درستشان یک ماژول مشترک است، وگرنه دو نمودار کنار هم
 *  می‌نشینند و رنگ محورشان یکی نیست.
 */
export const SERIES_COLOR = "var(--chart-series)";
export const GRID_STROKE = "var(--chart-grid)";
export const AXIS_STROKE = "var(--chart-axis)";
export const TICK_STYLE = {
  fontSize: 11,
  fill: "var(--chart-tick)",
  fontFamily: "Vazirmatn, Tahoma, sans-serif",
};
export const TOOLTIP_STYLE = {
  direction: "rtl" as const,
  fontFamily: "Vazirmatn, Tahoma, sans-serif",
  fontSize: 12,
  borderRadius: 12,
  border: "1px solid var(--chart-grid)",
  boxShadow: "0 12px 40px rgba(0,0,0,0.12)",
  background: "rgba(255,255,255,0.97)",
};

export const faNum = (value: unknown) =>
  typeof value === "number" ? value.toLocaleString("fa-IR") : String(value);
