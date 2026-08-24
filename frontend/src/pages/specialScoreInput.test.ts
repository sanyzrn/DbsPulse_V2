/** ورودیِ امتیاز ویژه با صفحه‌کلید فارسی.
 *
 *  کاربر این سامانه «۲٫۵» می‌نویسد، نه «2.5». `Number("۲٫۵")` برابر NaN است،
 *  یعنی بدون تبدیل، فرم عددِ کاملاً درستِ روی صفحه را «عدد نیست» می‌خواند — و
 *  این دقیقاً همان خرابی‌ای است که سکوت می‌کند: کاربر عدد را می‌بیند و فقط
 *  می‌فهمد «ثبت نمی‌شود».
 */
import { describe, expect, it } from "vitest";
import { toMachineNumber } from "./EvaluationDetailPage";

describe("toMachineNumber", () => {
  it("ارقام فارسی را می‌خواند", () => {
    expect(Number(toMachineNumber("۳"))).toBe(3);
    expect(Number(toMachineNumber("۲٫۵"))).toBe(2.5);
  });

  it("ارقام عربی را هم می‌خواند", () => {
    expect(Number(toMachineNumber("٤"))).toBe(4);
  });

  it("ارقام لاتین دست‌نخورده می‌مانند", () => {
    expect(Number(toMachineNumber("2.5"))).toBe(2.5);
  });

  it("فاصلهٔ اضافه عدد را خراب نمی‌کند", () => {
    expect(Number(toMachineNumber("  ۴  "))).toBe(4);
  });

  it("متنِ غیرعددی همچنان غیرعددی می‌ماند — تا فرم بتواند ردش کند", () => {
    expect(Number.isNaN(Number(toMachineNumber("خیلی زیاد")))).toBe(true);
  });
});
