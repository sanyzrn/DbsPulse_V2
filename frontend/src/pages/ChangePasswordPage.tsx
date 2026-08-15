import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { apiClient, authToken, extractErrorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { Button } from "../ui/Button";
import { PasswordInput } from "../ui/PasswordInput";
import {
  MIN_PASSWORD_LENGTH,
  checkPassword,
  generatePassword,
  strengthLevel,
} from "../utils/password";

export function ChangePasswordPage() {
  const { user, refreshUser } = useAuth();
  const { showSuccess } = useToast();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [generated, setGenerated] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const forced = user?.must_change_password ?? false;
  const check = checkPassword(newPassword, {
    username: user?.username,
    currentPassword,
  });
  const strength = strengthLevel(check.score);
  const mismatch = confirmPassword.length > 0 && newPassword !== confirmPassword;

  function useGenerated() {
    const password = generatePassword();
    setGenerated(password);
    setNewPassword(password);
    setConfirmPassword(password);
    setCopied(false);
  }

  async function copyGenerated() {
    if (!generated) return;
    try {
      await navigator.clipboard.writeText(generated);
      setCopied(true);
    } catch {
      // کلیپ‌بورد در بستر ناامن یا بدون اجازه کار نمی‌کند؛ رمز روی صفحه دیده
      // می‌شود، پس کاربر همچنان راهی برای برداشتنش دارد.
      setCopied(false);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!check.valid) {
      const failed = check.required.find((r) => !r.passed);
      setError(failed ? `رمز عبور جدید: ${failed.label}` : "رمز عبور جدید معتبر نیست.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("تکرار رمز عبور جدید مطابقت ندارد.");
      return;
    }
    setSubmitting(true);
    try {
      const { data } = await apiClient.post("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      authToken.set(data.access_token);
      await refreshUser();
      showSuccess("رمز عبور با موفقیت تغییر کرد");
      navigate("/");
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-md py-6">
      <motion.form
        onSubmit={handleSubmit}
        className="rounded-3xl border border-gray-100 bg-white p-6 shadow-card"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
      >
        <h1 className="mb-1 text-lg font-bold text-gray-900">تغییر رمز عبور</h1>
        {forced ? (
          <p className="mb-5 text-sm text-amber-700">
            رمز فعلی شما موقتی است و توسط منابع انسانی تعیین شده؛ برای ادامه کار باید رمز جدیدی
            برای خودتان انتخاب کنید.
          </p>
        ) : (
          <p className="mb-5 text-sm text-gray-500">
            پس از تغییر رمز، نشست‌های فعال شما روی سایر دستگاه‌ها خارج می‌شوند.
          </p>
        )}

        <Field label="رمز عبور فعلی" htmlFor="current-password">
          <PasswordInput
            id="current-password"
            autoComplete="current-password"
            required
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
          />
        </Field>

        <div className="mb-1.5 flex items-baseline justify-between gap-2">
          <label htmlFor="new-password" className="text-sm font-medium text-gray-700">
            رمز عبور جدید
          </label>
          <button
            type="button"
            onClick={useGenerated}
            className="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50"
          >
            <svg viewBox="0 0 20 20" className="h-3.5 w-3.5 text-pulse-600" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M10 3v3M10 14v3M3 10h3M14 10h3M5.4 5.4l2.1 2.1M12.5 12.5l2.1 2.1M14.6 5.4l-2.1 2.1M7.5 12.5l-2.1 2.1" />
            </svg>
            ساخت رمز قوی
          </button>
        </div>
        <PasswordInput
          id="new-password"
          autoComplete="new-password"
          required
          minLength={MIN_PASSWORD_LENGTH}
          value={newPassword}
          onChange={(e) => {
            setNewPassword(e.target.value);
            setGenerated(null);
          }}
        />

        {generated && (
          <div className="mt-2 flex items-center justify-between gap-2 rounded-xl border border-pulse-100 bg-pulse-50/60 px-3 py-2">
            <code className="min-w-0 select-all break-all font-mono text-xs text-gray-800" dir="ltr">
              {generated}
            </code>
            <button
              type="button"
              onClick={copyGenerated}
              className="shrink-0 rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50"
            >
              {copied ? "کپی شد ✓" : "کپی"}
            </button>
          </div>
        )}

        {newPassword.length > 0 && (
          <div className="mt-3 space-y-3">
            <div>
              <div className="flex gap-1" aria-hidden>
                {[0, 1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className={`h-1 flex-1 rounded-full transition-colors duration-200 ${
                      i < check.score ? strength.color : "bg-gray-100"
                    }`}
                  />
                ))}
              </div>
              {strength.label && (
                <p className={`mt-1 text-xs ${strength.textColor}`}>قدرت رمز: {strength.label}</p>
              )}
            </div>

            <RuleList title="الزامی" rules={check.required} strict />
            <RuleList title="برای قوی‌تر شدن" rules={check.optional} />
          </div>
        )}

        <div className="mt-4">
          <Field label="تکرار رمز عبور جدید" htmlFor="confirm-password">
            <PasswordInput
              id="confirm-password"
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              aria-invalid={mismatch}
            />
            {mismatch && (
              <p className="mt-1 text-xs text-red-600">تکرار رمز با رمز جدید یکی نیست.</p>
            )}
          </Field>
        </div>

        {error && (
          <motion.p
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600"
          >
            {error}
          </motion.p>
        )}

        <Button
          type="submit"
          loading={submitting}
          disabled={!check.valid || mismatch || confirmPassword.length === 0}
          className="w-full"
        >
          {submitting ? "در حال ذخیره…" : "تغییر رمز عبور"}
        </Button>
      </motion.form>
    </div>
  );
}

/** فهرست نشانه‌دار قواعد.
 *
 * «الزامی» و «برای قوی‌تر شدن» عمداً از هم جدا شده‌اند: سرور فقط قواعد الزامی را
 * اعمال می‌کند و اگر همه را یک‌کاسه نشان دهیم، رابط کاربری دربارهٔ قانون دروغ گفته
 * است. ضمناً اجباری‌کردن «حرف بزرگ» در سامانه‌ای فارسی، عبارت عبور فارسی را
 * ناممکن می‌کرد — حروف فارسی بزرگ و کوچک ندارند. */
function RuleList({
  title,
  rules,
  strict = false,
}: {
  title: string;
  rules: { key: string; label: string; passed: boolean }[];
  strict?: boolean;
}) {
  return (
    <div>
      <p className="mb-1 text-[11px] font-medium text-gray-400">{title}</p>
      <ul className="space-y-0.5">
        {rules.map((rule) => (
          <li key={rule.key} className="flex items-center gap-1.5 text-xs">
            <span
              aria-hidden
              className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full ${
                rule.passed
                  ? "bg-green-100 text-green-700"
                  : strict
                    ? "bg-red-50 text-red-500"
                    : "bg-gray-100 text-gray-400"
              }`}
            >
              <svg viewBox="0 0 12 12" className="h-2.5 w-2.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                {rule.passed ? <path d="M2.5 6.2l2.4 2.4L9.5 4" /> : <path d="M3.5 3.5l5 5M8.5 3.5l-5 5" />}
              </svg>
            </span>
            <span className={rule.passed ? "text-gray-600" : strict ? "text-red-600" : "text-gray-400"}>
              {rule.label}
            </span>
            {/* حالت هر قاعده باید بدون تکیه بر رنگ هم خوانده شود */}
            <span className="sr-only">{rule.passed ? "برقرار است" : "برقرار نیست"}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-4">
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-gray-700">
        {label}
      </label>
      {children}
    </div>
  );
}
