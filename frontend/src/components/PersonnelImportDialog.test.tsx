import { describe, expect, it } from "vitest";
import { buildAccountsCsv } from "./PersonnelImportDialog";

const account = (over: Partial<Parameters<typeof buildAccountsCsv>[0][0]> = {}) => ({
  personnel_code: "P-1",
  full_name: "سارا احمدی",
  username: "s.ahmadi",
  temporary_password: "Abcd1234!x",
  ...over,
});

describe("buildAccountsCsv", () => {
  it("با BOM شروع می‌شود تا اکسل فارسی را درست باز کند", () => {
    expect(buildAccountsCsv([account()]).startsWith("﻿")).toBe(true);
  });

  it("ویرگول داخل نام، ستون‌ها را جابه‌جا نمی‌کند", () => {
    const csv = buildAccountsCsv([account({ full_name: "احمدی, سارا" })]);
    const dataLine = csv.split("\r\n")[1]!;
    // چهار سلول، نه پنج
    expect(dataLine.match(/(?:^|,)"/g)).toHaveLength(4);
    expect(dataLine).toContain('"احمدی, سارا"');
  });

  it("نقل‌قول داخل رمز دو برابر می‌شود، وگرنه فایل از همان‌جا خراب می‌شد", () => {
    const csv = buildAccountsCsv([account({ temporary_password: 'a"b' })]);
    expect(csv).toContain('"a""b"');
  });

  it("هر حساب یک ردیف می‌شود", () => {
    const csv = buildAccountsCsv([
      account({ username: "one" }),
      account({ username: "two" }),
    ]);
    expect(csv.split("\r\n")).toHaveLength(3); // سرستون + دو ردیف
  });
});
