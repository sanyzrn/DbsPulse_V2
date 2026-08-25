import { useMemo, useState } from "react";
import {
  MIN_PASSWORD_LENGTH,
  checkPassword,
  generatePassword,
  strengthLevel,
} from "../utils/password";
import { PasswordInput } from "./PasswordInput";

/** ورودی رمز با چشمِ نمایش، سنجهٔ قدرت، ساختِ رمز قوی و کپی.
 *
 *  چرا یک‌جا: تعیینِ رمز برای *کسِ دیگر* سه کارِ پشت سر هم است — یک رمز خوب
 *  انتخاب کن، ببین چه نوشته‌ای، و آن را به صاحبش برسان. تا امروز هر سه دستی
 *  بودند، و نتیجه‌اش رمزهایی بود که چون باید تایپ و گفته می‌شدند، ساده انتخاب
 *  می‌شدند.
 *
 *  قاعده‌ها این‌جا تعریف نمی‌شوند: طول، تولید و سنجه همه از `utils/password`
 *  می‌آیند — همان جایی که صفحهٔ «تغییر رمز» هم از آن می‌خواند. پیش‌تر این فایل
 *  نسخهٔ دوم و کمی متفاوتِ همان قاعده‌ها را داشت، یعنی یک رمز می‌توانست این‌جا
 *  «قوی» و آن‌جا «متوسط» باشد.
 */
export function PasswordField({
  value,
  onChange,
  id,
  autoComplete = "new-password",
  placeholder,
  required,
  /** برای قاعدهٔ «رمز نباید شامل نام کاربری باشد». */
  username,
  /** فرم «ویرایش» رمز را اختیاری می‌گذارد؛ سنجه تا وقتی خالی است پنهان می‌ماند. */
  optional = false,
}: {
  value: string;
  onChange: (value: string) => void;
  id?: string;
  autoComplete?: string;
  placeholder?: string;
  required?: boolean;
  username?: string | null;
  optional?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const check = useMemo(() => checkPassword(value, { username }), [value, username]);
  const level = strengthLevel(check.score);
  const show = value.length > 0 || !optional;

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      /* بدون مجوز کلیپ‌بورد (یا http)، کاربر می‌تواند رمز را ببیند و دستی بردارد */
    }
  }

  return (
    <div className="space-y-2">
      <PasswordInput
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        placeholder={placeholder}
        required={required}
        minLength={MIN_PASSWORD_LENGTH}
      />

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => onChange(generatePassword())}
          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-2.5 py-1 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50 hover:text-gray-900"
        >
          <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M10 3v3M10 14v3M3 10h3M14 10h3M5.1 5.1l2.1 2.1M12.8 12.8l2.1 2.1M14.9 5.1l-2.1 2.1M7.2 12.8l-2.1 2.1" />
          </svg>
          ساخت رمز قوی
        </button>
        <button
          type="button"
          onClick={copy}
          disabled={!value}
          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-2.5 py-1 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50 hover:text-gray-900 disabled:opacity-40"
        >
          <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <rect x="7" y="7" width="9" height="10" rx="1.6" />
            <path d="M13 4.5A1.5 1.5 0 0 0 11.5 3H5.5A1.5 1.5 0 0 0 4 4.5v7A1.5 1.5 0 0 0 5.5 13" />
          </svg>
          {copied ? "کپی شد" : "کپی"}
        </button>

        {show && (
          <div className="flex min-w-0 flex-1 items-center justify-end gap-2">
            <div className="flex gap-1" aria-hidden>
              {[1, 2, 3, 4].map((step) => (
                <span
                  key={step}
                  className={`h-1.5 w-6 rounded-full ${
                    check.score >= step ? level.color : "bg-gray-200"
                  }`}
                />
              ))}
            </div>
            <span className={`text-xs font-medium ${level.textColor}`}>{level.label}</span>
          </div>
        )}
      </div>

      {/* قاعده‌های الزامیِ نقض‌شده — نه فهرست کاملِ همیشه‌روشن، که فقط نویز است.
          کسی که رمزِ درستی نوشته لازم نیست سه تیکِ سبز را بخواند. */}
      {show && !check.valid && (
        <ul className="space-y-0.5 text-[11px] text-amber-700">
          {check.required
            .filter((rule) => !rule.passed)
            .map((rule) => (
              <li key={rule.key}>• {rule.label}</li>
            ))}
        </ul>
      )}

      <p className="text-[11px] text-gray-400">
        حداقل {MIN_PASSWORD_LENGTH.toLocaleString("fa-IR")} نویسه. کاربر در اولین ورود باید خودش
        آن را عوض کند.
      </p>
    </div>
  );
}
