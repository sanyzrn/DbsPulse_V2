/** قواعد و تولید رمز عبور — یک منبع واحد برای فرم تغییر رمز و ساخت حساب.
 *
 * تفکیک «الزامی» از «پیشنهادی» عمدی است. اگر همهٔ نشانه‌ها را الزامی نشان دهیم
 * ولی سرور فقط طول را بررسی کند، رابط کاربری دربارهٔ قانون دروغ گفته است — و
 * برعکس، الزامی‌کردن «حرف بزرگ» در یک سامانهٔ فارسی یعنی عبارت‌های عبور فارسی
 * ممنوع شوند، چون حروف فارسی اصلاً بزرگ و کوچک ندارند. راهنمای امروزی هم روی
 * طول و فهرست ممنوعه تأکید دارد نه ترکیب اجباری نویسه‌ها.
 *
 * پس: طول و «نبودِ نام کاربری» الزامی‌اند و سرور هم اعمالشان می‌کند؛ ترکیب
 * نویسه‌ها به‌عنوان تقویت‌کننده نمایش داده می‌شود.
 */

export const MIN_PASSWORD_LENGTH = 10;
const STRONG_LENGTH = 14;

export interface PasswordRule {
  key: string;
  label: string;
  passed: boolean;
}

export interface PasswordCheck {
  required: PasswordRule[];
  optional: PasswordRule[];
  /** همهٔ قواعد الزامی برقرارند؟ */
  valid: boolean;
  /** ۰ تا ۴ — فقط برای نوار قدرت */
  score: number;
}

export function checkPassword(
  password: string,
  options: { username?: string | null; currentPassword?: string } = {},
): PasswordCheck {
  const { username, currentPassword } = options;
  const lower = password.toLowerCase();

  const required: PasswordRule[] = [
    {
      key: "length",
      label: `دست‌کم ${MIN_PASSWORD_LENGTH.toLocaleString("fa-IR")} نویسه`,
      passed: password.length >= MIN_PASSWORD_LENGTH,
    },
    {
      key: "not-username",
      label: "شامل نام کاربری نباشد",
      // نام کاربری‌های خیلی کوتاه را نادیده می‌گیریم، وگرنه هر رمزی رد می‌شود
      passed:
        !username || username.length < 3 || !lower.includes(username.toLowerCase()),
    },
    {
      key: "not-current",
      label: "با رمز فعلی یکی نباشد",
      passed: !currentPassword || password !== currentPassword,
    },
  ];

  const optional: PasswordRule[] = [
    { key: "upper", label: "حرف بزرگ انگلیسی", passed: /[A-Z]/.test(password) },
    { key: "lower", label: "حرف کوچک انگلیسی", passed: /[a-z]/.test(password) },
    { key: "digit", label: "رقم", passed: /\d/.test(password) },
    { key: "symbol", label: "نماد (مثل ! یا @)", passed: /[^A-Za-z0-9\s]/.test(password) },
    {
      key: "long",
      label: `${STRONG_LENGTH.toLocaleString("fa-IR")} نویسه یا بیشتر`,
      passed: password.length >= STRONG_LENGTH,
    },
  ];

  const hits = optional.filter((r) => r.passed).length;
  // امتیاز فقط وقتی معنا دارد که شرط‌های الزامی برقرار باشند
  const valid = required.every((r) => r.passed);
  const score = password.length === 0 || !valid ? 0 : Math.max(1, Math.ceil((hits / 5) * 4));

  return { required, optional, valid, score };
}

const STRENGTH_LEVELS = [
  { label: "", color: "", textColor: "" },
  { label: "ضعیف", color: "bg-amber-500", textColor: "text-amber-600" },
  { label: "متوسط", color: "bg-yellow-500", textColor: "text-yellow-600" },
  { label: "خوب", color: "bg-pulse-500", textColor: "text-pulse-600" },
  { label: "قوی", color: "bg-green-500", textColor: "text-green-600" },
];

export function strengthLevel(score: number) {
  return STRENGTH_LEVELS[Math.min(score, 4)]!;
}

// نویسه‌های مبهم (O/0، l/1/I) عمداً کنار گذاشته شده‌اند: این رمز را HR روی کاغذ
// یا در پیام به فرد می‌دهد و باید بدون اشتباه تایپ شود.
const LETTERS_LOWER = "abcdefghijkmnopqrstuvwxyz";
const LETTERS_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ";
const DIGITS = "23456789";
const SYMBOLS = "!@#$%^&*-_=+";

function pick(alphabet: string, count: number): string[] {
  const values = crypto.getRandomValues(new Uint32Array(count));
  return Array.from(values, (n) => alphabet[n % alphabet.length]!);
}

/** رمز تصادفی قوی. از crypto استفاده می‌کند نه Math.random — رمزی که با یک مولد
 *  قابل‌پیش‌بینی ساخته شود، فقط تصادفی *به‌نظر* می‌رسد. */
export function generatePassword(length = 16): string {
  // دست‌کم یکی از هر گروه، تا خروجی همیشه همهٔ نشانه‌های تقویت‌کننده را بگیرد
  const chars = [
    ...pick(LETTERS_LOWER, 1),
    ...pick(LETTERS_UPPER, 1),
    ...pick(DIGITS, 1),
    ...pick(SYMBOLS, 1),
    ...pick(LETTERS_LOWER + LETTERS_UPPER + DIGITS + SYMBOLS, Math.max(0, length - 4)),
  ];

  // بُر زدن با Fisher–Yates روی همان منبع تصادفی؛ بدون آن، همیشه نویسهٔ اول
  // کوچک و دومی بزرگ بود و الگو قابل حدس می‌شد.
  const order = crypto.getRandomValues(new Uint32Array(chars.length));
  for (let i = chars.length - 1; i > 0; i--) {
    const j = order[i]! % (i + 1);
    [chars[i], chars[j]] = [chars[j]!, chars[i]!];
  }
  return chars.join("");
}
