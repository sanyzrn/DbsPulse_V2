import { useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { useAuth } from "../auth/AuthContext";
import { extractErrorMessage } from "../api/client";
import { APP_NAME, APP_NAME_FA, APP_TAGLINE } from "../appInfo";
import { AnimatedGridBackground } from "../components/AnimatedGridBackground";
import { BrandMark } from "../components/Brand";
import { Footer } from "../components/Footer";
import { PasswordInput } from "../ui/PasswordInput";
import { Button } from "../ui/Button";
import { ThemeToggle } from "../ui/ThemeToggle";

const PRODUCT_POINTS = [
  "ثبت ساختاریافتهٔ ارزیابی و شواهد عملکرد",
  "گردش‌کار شفاف تأیید از مسئول واحد تا تصمیم نهایی",
  "کارنامهٔ رسمیِ قابل استعلام و قابل پیگیری",
];

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden">
      <AnimatedGridBackground />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(183,25,34,0.14),transparent_38%),radial-gradient(circle_at_bottom_right,rgba(75,85,99,0.12),transparent_26%)]" />
      <div className="relative mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-5 lg:px-6">
        <div className="grid flex-1 items-center gap-6 lg:grid-cols-[1.05fr_0.95fr] xl:gap-12">
          <motion.section
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            className="hidden lg:block"
          >
            <div className="rounded-[28px] border border-white/80 bg-white/80 p-10 shadow-float backdrop-blur">
              <img
                src="/brand/nafas-pharmed-logo.png"
                alt="نفس زیست فارمد"
                className="mb-10 h-auto w-full max-w-md object-contain"
              />
              <p className="text-sm font-semibold text-pulse-700">{APP_NAME}</p>
              <h1 className="mt-2 text-2xl font-extrabold tracking-tight text-gray-900">{APP_NAME_FA}</h1>
              <p className="mt-3 max-w-xl text-sm leading-7 text-gray-600">{APP_TAGLINE}</p>
              <div className="mt-8 border-t border-gray-100 pt-6">
                <p className="text-sm font-bold text-gray-800">در این سامانه</p>
                <ul className="mt-4 space-y-3">
                  {PRODUCT_POINTS.map((point) => (
                    <li key={point} className="flex items-start gap-3 text-sm leading-6 text-gray-600">
                      <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-pulse-600" />
                      {point}
                    </li>
                  ))}
                </ul>
              </div>
              <p className="mt-8 text-xs text-gray-400">ویژهٔ همکاران نفس زیست فارمد</p>
            </div>
          </motion.section>

          <motion.section
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, ease: "easeOut", delay: 0.05 }}
            className="flex items-center justify-center"
          >
            <div className="w-full max-w-md rounded-[28px] border border-white/80 bg-white/90 p-6 shadow-float backdrop-blur md:p-8">
              <div className="mb-8 flex items-center gap-3">
                <div className="rounded-2xl bg-pulse-50 p-3">
                  <BrandMark className="h-8 w-8" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-gray-900">{APP_NAME}</div>
                  <div className="text-xs font-medium text-gray-500">{APP_NAME_FA}</div>
                </div>
              </div>

              <motion.form
                onSubmit={handleSubmit}
                className="space-y-4"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.35, delay: 0.1 }}
              >
                <Field label="نام کاربری" htmlFor="login-username">
                  <input
                    id="login-username"
                    name="username"
                    required
                    autoComplete="username"
                    className="w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-gray-900 focus:bg-white"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    autoFocus
                  />
                </Field>

                <Field label="رمز عبور" htmlFor="login-password">
                  <PasswordInput
                    id="login-password"
                    name="password"
                    required
                    autoComplete="current-password"
                    baseClassName="w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 pl-11 text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-gray-900 focus:bg-white"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    visible={showPassword}
                    onVisibleChange={setShowPassword}
                  />
                </Field>

                {error && (
                  <motion.p
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    className="rounded-2xl bg-red-50 px-3 py-2 text-sm text-red-600"
                  >
                    {error}
                  </motion.p>
                )}

                <Button type="submit" loading={submitting} className="w-full rounded-2xl">
                  {submitting ? "در حال ورود…" : "ورود"}
                </Button>
              </motion.form>
            </div>
          </motion.section>
        </div>

        <div className="mt-4 space-y-3">
          <div className="flex justify-center">
            <ThemeToggle />
          </div>
          <Footer />
        </div>
      </div>
    </div>
  );
}

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-gray-700">
        {label}
      </label>
      {children}
    </div>
  );
}
