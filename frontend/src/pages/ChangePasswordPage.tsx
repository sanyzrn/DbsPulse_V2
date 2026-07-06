import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { apiClient, authToken, extractErrorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { Button } from "../ui/Button";

const MIN_PASSWORD_LENGTH = 10;

export function ChangePasswordPage() {
  const { user, refreshUser } = useAuth();
  const { showSuccess } = useToast();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const forced = user?.must_change_password ?? false;

  // شاخص قدرت رمز ساده
  const strength = getPasswordStrength(newPassword);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      setError(`رمز عبور جدید باید حداقل ${MIN_PASSWORD_LENGTH} نویسه باشد.`);
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
    <div className="mx-auto max-w-sm py-6">
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
          <input
            id="current-password"
            type="password"
            autoComplete="current-password"
            required
            className="w-full rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm text-gray-900 outline-none transition-all duration-200 focus:border-pulse-400"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
          />
        </Field>

        <Field label={`رمز عبور جدید (حداقل ${MIN_PASSWORD_LENGTH} نویسه)`} htmlFor="new-password">
          <input
            id="new-password"
            type="password"
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD_LENGTH}
            className="w-full rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm text-gray-900 outline-none transition-all duration-200 focus:border-pulse-400"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />
          {newPassword.length > 0 && (
            <div className="mt-2">
              <div className="flex gap-1">
                {[0, 1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className={`h-1 flex-1 rounded-full transition-colors duration-200 ${
                      i < strength.score ? strength.color : "bg-gray-100"
                    }`}
                  />
                ))}
              </div>
              <p className={`mt-1 text-xs ${strength.textColor}`}>{strength.label}</p>
            </div>
          )}
        </Field>

        <Field label="تکرار رمز عبور جدید" htmlFor="confirm-password">
          <input
            id="confirm-password"
            type="password"
            autoComplete="new-password"
            required
            className="w-full rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm text-gray-900 outline-none transition-all duration-200 focus:border-pulse-400"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />
        </Field>

        {error && (
          <motion.p
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600"
          >
            {error}
          </motion.p>
        )}

        <Button type="submit" loading={submitting} className="w-full">
          {submitting ? "در حال ذخیره…" : "تغییر رمز عبور"}
        </Button>
      </motion.form>
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

/** شاخص قدرت رمز ساده بر اساس طول و تنوع نویسه‌ها. */
function getPasswordStrength(pw: string): {
  score: number;
  label: string;
  color: string;
  textColor: string;
} {
  if (pw.length === 0) return { score: 0, label: "", color: "", textColor: "" };
  let score = 0;
  if (pw.length >= 10) score++;
  if (pw.length >= 14) score++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) score++;
  const levels = [
    { label: "بسیار ضعیف", color: "bg-red-500", textColor: "text-red-600" },
    { label: "ضعیف", color: "bg-amber-500", textColor: "text-amber-600" },
    { label: "متوسط", color: "bg-yellow-500", textColor: "text-yellow-600" },
    { label: "خوب", color: "bg-pulse-500", textColor: "text-pulse-600" },
    { label: "قوی", color: "bg-green-500", textColor: "text-green-600" },
  ];
  return { score, ...levels[score]! };
}
