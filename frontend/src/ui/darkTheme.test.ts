/** سوراخ‌های تم تیره، قبل از اینکه کسی ببیندشان.
 *
 * تم تیره با *بازتعریف متغیرهای رنگ* کار می‌کند، نه با پیشوند `dark:` روی تک‌تک
 * کلاس‌ها. این تصمیم آگاهانه است (توضیحش در `index.css`) ولی یک نقطهٔ کور دارد:
 * هر کلاسی که به رنگِ *ثابت* ختم شود از این سازوکار جا می‌ماند، چون متغیری در
 * کار نیست که عوض شود.
 *
 * دقیقاً همین اتفاق افتاد. Tailwind برای هر واریانت یک انتخابگر جدا می‌سازد:
 *
 *     .bg-white              → var(--color-white)   ← قاعدهٔ تم تیره داشت
 *     .focus\:bg-white:focus → var(--color-white)   ← نداشت
 *     .bg-white\/90          → #ffffffe6            ← نداشت
 *
 * نتیجه: تقریباً هر ورودی سامانه در لحظهٔ فوکوس سفیدِ خالص می‌شد و متنش —که در
 * تم تیره روشن است— ناپدید می‌شد؛ و کارت ورود اصلاً تیره نمی‌شد.
 *
 * این تست کدِ اجراشونده را نمی‌سنجد، سازگاریِ دو فایل را می‌سنجد: هر کلاسِ
 * سفیدِ ثابتی که در کامپوننت‌ها به کار می‌رود باید در `index.css` قاعدهٔ تیره‌اش
 * را داشته باشد. اضافه‌کردن `bg-white/60` فردا، همین‌جا می‌شکند نه روی صفحهٔ
 * یک کاربر.
 */
/// <reference types="node" />
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/** ارجاع محلی به تایپ‌های Node بالای همین فایل، به‌جای افزودنشان به
 *  `tsconfig.app.json`: آن‌جا گذاشتنشان یعنی `process` و `Buffer` در کل کد
 *  برنامه هم شناخته می‌شوند و اشتباهِ استفاده از آن‌ها در مرورگر دیگر خطا
 *  نمی‌دهد.
 *
 *  `import … from "…?raw"` این‌جا کار نمی‌کند: vitest به‌صورت پیش‌فرض فایل‌های
 *  CSS را stub می‌کند و رشتهٔ خالی برمی‌گرداند — یعنی تست بی‌صدا سبز می‌ماند. */
const SRC = join(__dirname, "..");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry) ? [path] : [];
  });
}

const ALL_SOURCE = sourceFiles(SRC)
  .map((path) => readFileSync(path, "utf8"))
  .join("\n");

/** توضیحات CSS حذف می‌شوند، و این نکتهٔ ظریفِ همین تست است: بلوکِ توضیح بالای
 *  همان قاعده، *مثال‌های* `.focus\:bg-white:focus` را نقل می‌کند. بدون این پاک‌سازی،
 *  تست خودِ توضیح را پیدا می‌کرد و همیشه سبز می‌ماند — یعنی هیچ‌چیز را نمی‌سنجید. */
const CSS = readFileSync(join(SRC, "index.css"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");

/** شفافیت‌های کم عمداً بیرون‌اند: پوششِ روشن روی سطحِ از قبل تیره (نشانِ نقش روی
 *  هدر قرمز، دکمهٔ بستن توست). آن‌ها باید سفید بمانند. */
const OVERLAY_MAX_OPACITY = 20;

function usedWhiteSurfaces(): string[] {
  const found = new Set<string>();
  for (const match of ALL_SOURCE.matchAll(/\bbg-white\/(\d+)\b/g)) {
    if (Number(match[1]) > OVERLAY_MAX_OPACITY) found.add(match[0]);
  }
  for (const match of ALL_SOURCE.matchAll(/\b(focus|hover|active|group-hover|focus-within):bg-white\b/g)) {
    found.add(match[0]);
  }
  return [...found];
}

/** `.focus\:bg-white:focus` — همان شکلی که Tailwind در CSS می‌نویسد. */
function escapedSelector(className: string): string {
  const [variant, base] = className.includes(":")
    ? [className.split(":")[0], className.split(":").slice(1).join(":")]
    : [null, className];
  const escaped = base.replace("/", "\\/");
  return variant ? `.${variant}\\:${escaped}:${variant}` : `.${escaped}`;
}

describe("dark theme coverage", () => {
  it("covers every fixed-white surface class the app actually uses", () => {
    const used = usedWhiteSurfaces();
    // اگر روزی الگوی جست‌وجو با کد از هم بیفتد، این تست بی‌صدا سبز می‌ماند چون
    // فهرستِ خالی هم «همه پوشش دارند» است. پس خودِ پیداکردن هم ادعا می‌شود.
    expect(used.length).toBeGreaterThan(0);
    const uncovered = used.filter((className) => !CSS.includes(escapedSelector(className)));
    expect(uncovered).toEqual([]);
  });

  it("still leaves the low-opacity overlays alone", () => {
    // اگر روزی کسی `bg-white/10` را هم تیره کند، دکمهٔ بستنِ توست روی زمینهٔ
    // تیرهٔ خودش ناپدید می‌شود. این تست آن جهت را هم می‌بندد.
    expect(CSS).not.toContain(".bg-white\\/10");
    expect(CSS).not.toContain(".bg-white\\/15");
    expect(CSS).not.toContain(".bg-white\\/20");
  });

  it("keeps the modal scrim dark in both themes", () => {
    // `--color-gray-900` در تم تیره تقریباً سفید است (رنگ عنوان‌ها)، پس پرده‌ای
    // که از آن ساخته شده بدون قاعدهٔ صریح، سفید روی صفحهٔ تیره می‌افتد.
    expect(ALL_SOURCE).toContain("bg-gray-900/40");
    expect(CSS).toContain('[data-theme="dark"] .bg-gray-900\\/40');
  });

  it("darkens native select popups", () => {
    // فهرست بازشو را سیستم‌عامل می‌کشد؛ `color-scheme: dark` لازم است ولی وقتی
    // خودِ select پس‌زمینهٔ صریح دارد کافی نیست.
    expect(CSS).toContain('[data-theme="dark"] select option');
  });
});
