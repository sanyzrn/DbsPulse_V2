import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { useAuth } from "../auth/AuthContext";
import { extractErrorMessage } from "../api/client";
import { APP_NAME, APP_NAME_FA, APP_TAGLINE } from "../appInfo";
import { BrandMark } from "../components/Brand";
import { Footer } from "../components/Footer";
import { Button } from "../ui/Button";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

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
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-cream-50">
      {/* یک المان محو و خاموش، به‌جای گرادیانت متحرک رنگی قبلی — صرفاً کمی حس زندگی
          به پس‌زمینهٔ ساده می‌دهد، بدون رقابت با محتوای فرم */}
      <div
        className="pointer-events-none absolute -right-24 -top-24 -z-10 h-96 w-96 rounded-full bg-gray-200/50 blur-3xl"
        style={{ animation: "var(--animate-float)" }}
      />

      <div className="flex flex-1 items-center justify-center p-4">
        <motion.div
          className="w-full max-w-sm"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        >
          {/* لوگوی موقت + معرفی کوتاه برنامه بالای فرم ورود */}
          <div className="mb-8 flex flex-col items-center text-center">
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.6, delay: 0.1, type: "spring", stiffness: 200 }}
              className="mb-4"
            >
              <div className="rounded-3xl bg-white p-3 shadow-card">
                <BrandMark className="h-16 w-16" />
              </div>
            </motion.div>
            <h1 dir="ltr" className="text-3xl font-extrabold tracking-tight text-gray-900">
              {APP_NAME}
            </h1>
            <p className="mt-1 text-sm font-semibold text-gray-600">{APP_NAME_FA}</p>
            <p className="mt-2 max-w-xs text-xs leading-relaxed text-gray-400">{APP_TAGLINE}</p>
          </div>

          {/* کارت ورود */}
          <motion.form
            onSubmit={handleSubmit}
            className="rounded-3xl border border-gray-100 bg-white p-6 shadow-float"
            initial={{ opacity: 0, scale: 0.95, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
          >
            <p className="mb-6 text-sm text-gray-600">
              برای ورود، نام کاربری و رمز عبور خود را وارد کنید.
            </p>

            <Field label="نام کاربری" htmlFor="login-username">
              <input
                id="login-username"
                name="username"
                autoComplete="username"
                className="w-full rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm text-gray-900 outline-none transition-all duration-200 focus:border-gray-400"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
              />
            </Field>

            <Field label="رمز عبور" htmlFor="login-password">
              <input
                id="login-password"
                name="password"
                type="password"
                autoComplete="current-password"
                className="w-full rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm text-gray-900 outline-none transition-all duration-200 focus:border-gray-400"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
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
              {submitting ? "در حال ورود…" : "ورود"}
            </Button>
          </motion.form>
        </motion.div>
      </div>
      <Footer />
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
