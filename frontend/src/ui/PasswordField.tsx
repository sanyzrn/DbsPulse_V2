import { useMemo, useState } from "react";
import { PasswordInput } from "./PasswordInput";

/** حداقلی که سرور هم اعمال می‌کند (`app/schemas/user.py`). اگر این دو از هم دور
 *  بیفتند، فرم رمزی را قبول می‌کند که API ردش می‌کند. */
export const PASSWORD_MIN_LENGTH = 10;

const ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%^&*-_=+";

/** رمزِ تصادفیِ قوی، از `crypto` مرورگر.
 *
 *  `Math.random` نه: قابل پیش‌بینی است و رمزی که این‌جا ساخته می‌شود رمزِ ورودِ
 *  اولِ یک حساب واقعی است. حروف و رقم‌های شبیه‌به‌هم (l/1/O/0) عمداً نیستند —
 *  این رمز قرار است روی کاغذ یا در پیام به کسی گفته شود.
 */
export function generatePassword(length = 16): string {
  const values = new Uint32Array(length);
  crypto.getRandomValues(values);
  return Array.from(values, (v) => ALPHABET[v % ALPHABET.length]).join("");
}

interface Strength {
  score: 0 | 1 | 2 | 3;
  label: string;
  bar: string;
  text: string;
}

/** سنجهٔ قدرت — عمداً ساده و قابل توضیح.
 *
 *  طول مهم‌ترین عامل است (NIST 800-63B)، و تنوعِ نویسه‌ها بعد از آن. هدف نمرهٔ
 *  دقیق نیست؛ هدف این است که کسی که «Ali1234567» می‌گذارد، *پیش از ذخیره* ببیند
 *  که این ضعیف است.
 */
function strengthOf(value: string): Strength {
  const classes =
    Number(/[a-z]/.test(value)) +
    Number(/[A-Z]/.test(value)) +
    Number(/[0-9]/.test(value)) +
    Number(/[^a-zA-Z0-9]/.test(value));
  const points = (value.length >= 16 ? 2 : value.length >= 12 ? 1 : 0) + (classes >= 3 ? 1 : 0);

  if (value.length < PASSWORD_MIN_LENGTH) {
    return { score: 0, label: "خیلی کوتاه", bar: "bg-red-500", text: "text-red-600" };
  }
  if (points >= 3) return { score: 3, label: "قوی", bar: "bg-green-500", text: "text-green-700" };
  if (points >= 2) return { score: 2, label: "خوب", bar: "bg-lime-500", text: "text-lime-700" };
  return { score: 1, label: "ضعیف", bar: "bg-amber-500", text: "text-amber-700" };
}

/** ورودی رمز با چشمِ نمایش، سنجهٔ قدرت، ساختِ رمز قوی و کپی.
 *
 *  چرا یک‌جا: تعیینِ رمز برای *کسِ دیگر* سه کارِ پشت سر هم است — یک رمز خوب
 *  انتخاب کن، ببین چه نوشته‌ای، و آن را به صاحبش برسان. تا امروز هر سه دستی
 *  بودند، و نتیجه‌اش رمزهایی بود که چون باید تایپ و گفته می‌شدند، ساده انتخاب
 *  می‌شدند.
 */
export function PasswordField({
  value,
  onChange,
  id,
  autoComplete = "new-password",
  placeholder,
  required,
  /** فرم «ویرایش» رمز را اختیاری می‌گذارد؛ سنجه تا وقتی خالی است پنهان می‌ماند. */
  optional = false,
}: {
  value: string;
  onChange: (value: string) => void;
  id?: string;
  autoComplete?: string;
  placeholder?: string;
  required?: boolean;
  optional?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const strength = useMemo(() => strengthOf(value), [value]);
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
        minLength={PASSWORD_MIN_LENGTH}
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
              {[1, 2, 3].map((step) => (
                <span
                  key={step}
                  className={`h-1.5 w-7 rounded-full ${
                    strength.score >= step ? strength.bar : "bg-gray-200"
                  }`}
                />
              ))}
            </div>
            <span className={`text-xs font-medium ${strength.text}`}>{strength.label}</span>
          </div>
        )}
      </div>

      <p className="text-[11px] text-gray-400">
        حداقل {PASSWORD_MIN_LENGTH.toLocaleString("fa-IR")} نویسه. کاربر در اولین ورود باید خودش
        آن را عوض کند.
      </p>
    </div>
  );
}
