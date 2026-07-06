/**
 * تبدیل تاریخ میلادی ↔ شمسی (جلالی) — بدون وابستگی خارجی.
 * الگوریتم بر پایه‌ی محاسبات نجومی استاندارد جلالی (روش بیرشک) است،
 * همان الگوریتمی که در کتابخانه‌های شناخته‌شده jalaali-js استفاده می‌شود.
 *
 * تاریخ در پایگاه‌داده همچنان میلادی (ISO 8601: "YYYY-MM-DD") ذخیره می‌شود؛
 * این ماژول فقط برای نمایش/دریافت ورودی در تقویم شمسی به کار می‌رود.
 */

export interface JalaliDate {
  jy: number;
  jm: number; // 1-12
  jd: number;
}

const breaks = [
  -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394,
  2456, 3178,
];

function div(a: number, b: number) {
  return ~~(a / b);
}

function jalCal(jy: number) {
  const bl = breaks.length;
  const gy = jy + 621;
  let leapJ = -14;
  let jp = breaks[0]!;
  let jump = 0;

  if (jy < jp || jy >= breaks[bl - 1]!) {
    throw new Error("Invalid Jalaali year " + jy);
  }

  let jm = 0;
  for (let i = 1; i < bl; i += 1) {
    jm = breaks[i]!;
    jump = jm - jp;
    if (jy < jm) break;
    leapJ = leapJ + div(jump, 33) * 8 + div(jump % 33, 4);
    jp = jm;
  }
  let n = jy - jp;

  leapJ = leapJ + div(n, 33) * 8 + div((n % 33) + 3, 4);
  if (jump % 33 === 4 && jump - n === 4) {
    leapJ += 1;
  }

  const leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;
  const march = 20 + leapJ - leapG;

  if (jump - n < 6) {
    n = n - jump + div(jump + 4, 33) * 33;
  }
  let leap = ((((n + 1) % 33) - 1) % 4);
  if (leap === -1) leap = 4;

  return { leap, gy, march };
}

function g2d(gy: number, gm: number, gd: number) {
  let d =
    div((gy + div(gm - 8, 6) + 100100) * 1461, 4) +
    div(153 * ((gm + 9) % 12) + 2, 5) +
    gd -
    34840408;
  d = d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752;
  return d;
}

function d2g(jdn: number) {
  let j = 4 * jdn + 139361631;
  j = j + div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908;
  const i = div((j % 1461), 4) * 5 + 308;
  const gd = div(i % 153, 5) + 1;
  const gm = (div(i, 153) % 12) + 1;
  const gy = div(j, 1461) - 100100 + div(8 - gm, 6);
  return { gy, gm, gd };
}

function j2d(jy: number, jm: number, jd: number) {
  const r = jalCal(jy);
  return g2d(r.gy, 3, r.march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1;
}

function d2j(jdn: number): JalaliDate {
  let gy = d2g(jdn).gy;
  let jy = gy - 621;
  let r = jalCal(jy);
  let jdn1f = g2d(gy, 3, r.march);
  let k = jdn - jdn1f;

  if (k >= 0) {
    if (k <= 185) {
      const jm = 1 + div(k, 31);
      const jd = (k % 31) + 1;
      return { jy, jm, jd };
    }
    k -= 186;
  } else {
    jy -= 1;
    k += 179;
    if (r.leap === 1) k += 1;
  }
  const jm = 7 + div(k, 30);
  const jd = (k % 30) + 1;
  return { jy, jm, jd };
}

/** میلادی → شمسی */
export function gregorianToJalali(gy: number, gm: number, gd: number): JalaliDate {
  return d2j(g2d(gy, gm, gd));
}

/** شمسی → میلادی */
export function jalaliToGregorian(jy: number, jm: number, jd: number): { gy: number; gm: number; gd: number } {
  return d2g(j2d(jy, jm, jd));
}

export function isLeapJalaliYear(jy: number): boolean {
  return jalCal(jy).leap === 0;
}

export function jalaliMonthLength(jy: number, jm: number): number {
  if (jm <= 6) return 31;
  if (jm <= 11) return 30;
  return isLeapJalaliYear(jy) ? 30 : 29;
}

const pad2 = (n: number) => String(n).padStart(2, "0");

/** رشته‌ی ISO میلادی "YYYY-MM-DD" → آبجکت تاریخ شمسی */
export function isoToJalali(iso: string | null | undefined): JalaliDate | null {
  if (!iso) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return null;
  const [, y, mo, d] = m;
  return gregorianToJalali(Number(y), Number(mo), Number(d));
}

/** آبجکت تاریخ شمسی → رشته‌ی ISO میلادی "YYYY-MM-DD" (برای ذخیره در پایگاه‌داده) */
export function jalaliToIso(jy: number, jm: number, jd: number): string {
  const { gy, gm, gd } = jalaliToGregorian(jy, jm, jd);
  return `${gy}-${pad2(gm)}-${pad2(gd)}`;
}

const persianDigitsMap: Record<string, string> = {
  "0": "۰",
  "1": "۱",
  "2": "۲",
  "3": "۳",
  "4": "۴",
  "5": "۵",
  "6": "۶",
  "7": "۷",
  "8": "۸",
  "9": "۹",
};

export function toPersianDigits(value: string | number): string {
  return String(value).replace(/[0-9]/g, (d) => persianDigitsMap[d]!);
}

export const JALALI_MONTH_NAMES = [
  "فروردین",
  "اردیبهشت",
  "خرداد",
  "تیر",
  "مرداد",
  "شهریور",
  "مهر",
  "آبان",
  "آذر",
  "دی",
  "بهمن",
  "اسفند",
];

export const JALALI_WEEKDAY_LABELS = ["ش", "ی", "د", "س", "چ", "پ", "ج"];

/** شمسی → رشته‌ی نمایشی "۱۴۰۳/۰۱/۰۵" */
export function formatJalali(iso: string | null | undefined): string {
  const j = isoToJalali(iso);
  if (!j) return "";
  return toPersianDigits(`${j.jy}/${pad2(j.jm)}/${pad2(j.jd)}`);
}

/** روز هفته‌ی جلالی (۰=شنبه ... ۶=جمعه) برای یک تاریخ شمسی مشخص */
export function jalaliWeekday(jy: number, jm: number, jd: number): number {
  const { gy, gm, gd } = jalaliToGregorian(jy, jm, jd);
  const jsDay = new Date(gy, gm - 1, gd).getDay(); // 0=Sun..6=Sat
  return (jsDay + 1) % 7; // 0=Sat,1=Sun,...,6=Fri
}

export function todayJalali(): JalaliDate {
  const now = new Date();
  return gregorianToJalali(now.getFullYear(), now.getMonth() + 1, now.getDate());
}
