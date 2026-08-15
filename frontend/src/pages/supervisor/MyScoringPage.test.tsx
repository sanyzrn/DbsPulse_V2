/** جملهٔ حکم در «آینهٔ ارزیاب».
 *
 * این تنها جای صفحه است که یک عدد به یک *قضاوت* تبدیل می‌شود، و دقیقاً همان جایی
 * است که یک اشتباه بی‌صدا می‌ماند: اگر جهت مقایسه برعکس شود، صفحه همچنان سالم
 * به‌نظر می‌رسد و فقط به ارزیاب خلافِ واقعیت را می‌گوید.
 */
import { describe, expect, it } from "vitest";
import { STYLE_THRESHOLD, verdict } from "./MyScoringPage";

describe("verdict", () => {
  it("نمرهٔ بالاتر از میانگین را «بالاتر» می‌خواند", () => {
    expect(verdict(4.2, 3.4)).toContain("بالاتر");
  });

  it("نمرهٔ پایین‌تر از میانگین را «پایین‌تر» می‌خواند", () => {
    expect(verdict(2.6, 3.4)).toContain("پایین‌تر");
  });

  it("اختلاف ناچیز را تفاوت سبک اعلام نمی‌کند", () => {
    // روی مقیاس ۱ تا ۵، اختلاف کمتر از یک‌دهم نویز است؛ اسم گذاشتن رویش به
    // ارزیاب می‌گوید مشکلی هست که نیست.
    const verdictText = verdict(3.4, 3.4 + STYLE_THRESHOLD / 2);
    expect(verdictText).toContain("هم‌تراز");
    expect(verdictText).not.toContain("بالاتر");
    expect(verdictText).not.toContain("پایین‌تر");
  });

  it("مرزِ آستانه خودش تفاوت حساب می‌شود", () => {
    expect(verdict(3.4 + STYLE_THRESHOLD, 3.4)).toContain("بالاتر");
  });

  it("وقتی میانگین سازمان سرکوب شده، ادعای مقایسه نمی‌کند", () => {
    // null یعنی جمعیتِ «بقیه» برای نمایش بی‌نام کم بوده — نه اینکه صفر است.
    // نشان‌دادن «شما بالاترید» در این حالت یک مقایسه با هیچ است.
    const verdictText = verdict(3.4, null);
    expect(verdictText).toContain("کافی");
    expect(verdictText).not.toContain("بالاتر");
  });

  it("ارزیابِ بدون کار نهایی‌شده را با جملهٔ خودش پاسخ می‌دهد", () => {
    expect(verdict(null, 3.4)).toContain("ثبت نکرده‌اید");
  });
});
