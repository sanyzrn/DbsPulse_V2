import { describe, expect, it } from "vitest";
import { MIN_PASSWORD_LENGTH, checkPassword, generatePassword } from "./password";

function rule(check: ReturnType<typeof checkPassword>, key: string) {
  return [...check.required, ...check.optional].find((r) => r.key === key);
}

describe("checkPassword — قواعد الزامی", () => {
  it("طول کوتاه رد می‌شود", () => {
    const check = checkPassword("Ab1!");
    expect(rule(check, "length")?.passed).toBe(false);
    expect(check.valid).toBe(false);
  });

  it("رمزی که نام کاربری را در خود دارد رد می‌شود", () => {
    // اولین چیزی که هر فهرست حملهٔ آماده امتحان می‌کند
    const check = checkPassword("hr1-Password!", { username: "hr1" });
    expect(rule(check, "not-username")?.passed).toBe(false);
    expect(check.valid).toBe(false);
  });

  it("بررسی نام کاربری به بزرگی/کوچکی حروف حساس نیست", () => {
    expect(checkPassword("HR1-Password!", { username: "hr1" }).valid).toBe(false);
  });

  it("نام کاربری خیلی کوتاه نادیده گرفته می‌شود، وگرنه هر رمزی رد می‌شد", () => {
    // با نام کاربری «ab»، تقریباً هر عبارتی جایی این دو حرف را دارد
    expect(checkPassword("Fabulous-Thing-9!", { username: "ab" }).valid).toBe(true);
  });

  it("یکی‌بودن با رمز فعلی رد می‌شود", () => {
    const same = "Correct-Horse-9!";
    const check = checkPassword(same, { currentPassword: same });
    expect(rule(check, "not-current")?.passed).toBe(false);
    expect(check.valid).toBe(false);
  });

  it("رمز معتبر همهٔ شرط‌های الزامی را می‌گذراند", () => {
    expect(checkPassword("Correct-Horse-9!", { username: "hr1" }).valid).toBe(true);
  });
});

describe("checkPassword — پیشنهادها", () => {
  it("عبارت عبور فارسیِ بلند معتبر است، هرچند حرف بزرگ ندارد", () => {
    // حروف فارسی بزرگ و کوچک ندارند؛ اگر «حرف بزرگ» الزامی بود، این ممنوع می‌شد.
    const check = checkPassword("اسب-درست-باتری-منگنه", { username: "hr1" });
    expect(check.valid).toBe(true);
    expect(rule(check, "upper")?.passed).toBe(false);
  });

  it("امتیاز با تنوع نویسه‌ها بالا می‌رود", () => {
    const weak = checkPassword("aaaaaaaaaaaa").score;
    const strong = checkPassword("Tr0ub4dour&3xyz").score;
    expect(strong).toBeGreaterThan(weak);
  });

  it("رمزِ نامعتبر امتیاز صفر می‌گیرد — نوار قدرت نباید امنیت کاذب بدهد", () => {
    expect(checkPassword("Ab1!").score).toBe(0);
  });
});

describe("generatePassword", () => {
  it("طول خواسته‌شده را می‌دهد و همهٔ شرط‌ها را می‌گذراند", () => {
    for (let i = 0; i < 50; i++) {
      const password = generatePassword();
      expect(password.length).toBe(16);
      const check = checkPassword(password, { username: "hr1" });
      expect(check.valid).toBe(true);
      expect(check.optional.every((r) => r.passed)).toBe(true);
    }
  });

  it("از هر گروه نویسه دست‌کم یکی دارد", () => {
    for (let i = 0; i < 50; i++) {
      const password = generatePassword();
      expect(password).toMatch(/[a-z]/);
      expect(password).toMatch(/[A-Z]/);
      expect(password).toMatch(/\d/);
      expect(password).toMatch(/[^A-Za-z0-9]/);
    }
  });

  it("نویسه‌های مبهم (O/0/l/1/I) ندارد — این رمز باید دستی تایپ شود", () => {
    for (let i = 0; i < 50; i++) {
      expect(generatePassword()).not.toMatch(/[Ol1I0]/);
    }
  });

  it("موقعیت گروه‌ها ثابت نیست (بُر واقعاً انجام می‌شود)", () => {
    // بدون بُر، نویسهٔ اول همیشه کوچک و دومی همیشه بزرگ بود
    const firsts = new Set(Array.from({ length: 40 }, () => generatePassword()[0]!));
    const anyUpper = [...firsts].some((c) => /[A-Z]/.test(c));
    const anyLower = [...firsts].some((c) => /[a-z]/.test(c));
    expect(anyUpper && anyLower).toBe(true);
  });

  it("تکراری تولید نمی‌کند", () => {
    const seen = new Set(Array.from({ length: 200 }, () => generatePassword()));
    expect(seen.size).toBe(200);
  });

  it("طول دلخواه هم پشتیبانی می‌شود و کوتاه‌تر از حداقل نمی‌رود", () => {
    expect(generatePassword(24)).toHaveLength(24);
    expect(generatePassword().length).toBeGreaterThanOrEqual(MIN_PASSWORD_LENGTH);
  });
});
