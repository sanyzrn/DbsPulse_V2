import { useEffect, useState, type ReactNode } from "react";
import { useParams } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import axios from "axios";
import { APP_NAME } from "../appInfo";
import { BrandMark } from "../components/Brand";
import { Footer } from "../components/Footer";
import { PctBadge } from "../ui/Meters";
import { formatDateTime } from "../utils/dates";

interface VerificationResult {
  valid: boolean;
  evaluation_code: string;
  subject_full_name: string;
  org_unit: string;
  final_weighted_pct: number | null;
  recommendation: string | null;
  finalized_at: string | null;
  sha256: string;
  /** سند هنوز در حال ساخت است (رندر PDF پس از نهایی‌سازی انجام می‌شود) */
  document_ready: boolean;
}

// صفحه عمومی (بدون احراز هویت) برای تأیید اصالت سند از روی QR نسخه چاپی
export function VerifyPage() {
  const { token } = useParams();
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [status, setStatus] = useState<"loading" | "valid" | "invalid">("loading");

  useEffect(() => {
    let active = true;
    axios
      .get<VerificationResult>(`/api/verify/${token}`)
      .then(({ data }) => {
        if (!active) return;
        setResult(data);
        // به فیلد valid پاسخ احترام می‌گذاریم؛ اگر سرور به هر دلیلی 200 با valid=false
        // برگرداند (سند نامعتبر/نهایی‌نشده)، همان حالت «نامعتبر» نمایش داده می‌شود.
        setStatus(data.valid ? "valid" : "invalid");
      })
      .catch(() => {
        if (active) setStatus("invalid");
      });
    return () => {
      active = false;
    };
  }, [token]);

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-cream-50">
      <div
        className="pointer-events-none absolute -right-24 -top-24 -z-10 h-96 w-96 rounded-full bg-gray-200/50 blur-3xl"
        style={{ animation: "var(--animate-float)" }}
      />

      <div className="flex flex-1 items-center justify-center p-4">
        <motion.div
          className="w-full max-w-md rounded-3xl border border-gray-200 bg-white p-6 shadow-float"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        >
          <div className="mb-5 flex flex-col items-center text-center">
            <div className="mb-2 rounded-2xl bg-pulse-50 p-2">
              <BrandMark className="h-10 w-10" />
            </div>
            <p dir="ltr" className="text-xs font-bold text-gray-400">{APP_NAME}</p>
            <h1 className="mt-1 text-lg font-bold text-gray-900">تأیید اصالت سند ارزیابی</h1>
          </div>

          <AnimatePresence mode="wait">
            {status === "loading" && (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center py-8"
              >
                <div className="mb-3 h-10 w-10 rounded-full border-[3px] border-pulse-100 border-t-pulse-500 animate-spin" />
                <p className="text-sm text-gray-500">در حال بررسی…</p>
              </motion.div>
            )}

            {status === "invalid" && (
              <motion.div
                key="invalid"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="rounded-2xl bg-red-50 p-5 text-center"
              >
                <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
                  <svg viewBox="0 0 24 24" className="h-6 w-6 text-red-600" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <path d="M12 9v4m0 4h.01M10.3 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.7 3.86a2 2 0 0 0-3.42 0z" />
                  </svg>
                </div>
                <p className="text-sm font-medium text-red-700">
                  سند معتبری با این نشانی یافت نشد.
                </p>
                <p className="mt-1 text-xs text-red-600">
                  ممکن است این سند نهایی نشده باشد یا نشانی اشتباه وارد شده باشد.
                </p>
              </motion.div>
            )}

            {status === "valid" && result && (
              <motion.div
                key="valid"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <div className="mb-4 flex flex-col items-center rounded-2xl bg-green-50 p-4 text-center">
                  <div className="mb-1 flex h-12 w-12 items-center justify-center rounded-full bg-green-500 shadow-md shadow-green-500/20">
                    <svg viewBox="0 0 24 24" className="h-6 w-6 text-white" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <p className="mt-1 text-sm font-medium text-green-700">این سند معتبر و نهایی‌شده است.</p>
                </div>
                <dl className="space-y-2 text-sm">
                  <Row label="کد ارزیابی" value={result.evaluation_code} />
                  <Row label="نام و نام خانوادگی" value={result.subject_full_name} />
                  <Row label="واحد سازمانی" value={result.org_unit} />
                  <Row label="امتیاز نهایی وزنی" value={<PctBadge value={result.final_weighted_pct} />} />
                  {result.recommendation && <Row label="نتیجه پیشنهادی" value={result.recommendation} />}
                  <Row label="تاریخ نهایی‌شدن" value={formatDateTime(result.finalized_at)} />
                </dl>
                {/* «هشِ خالی» روی یک صفحهٔ تأیید اصالت، از «سند دستکاری‌شده» قابل
                    تشخیص نیست — پس نبودنش صریحاً توضیح داده می‌شود. */}
                <div className="mt-4 border-t border-gray-100 pt-3">
                  <p className="text-xs text-gray-400">اثر انگشت دیجیتال سند (SHA-256):</p>
                  {result.sha256 ? (
                    <p dir="ltr" className="mt-1 break-all text-left font-mono text-[10px] text-gray-500">
                      {result.sha256}
                    </p>
                  ) : (
                    <p className="mt-1 text-xs text-amber-700">
                      سند رسمی این ارزیابی هنوز در حال آماده‌سازی است؛ چند لحظهٔ دیگر
                      دوباره این صفحه را باز کنید. اصالت خودِ ارزیابی — که در بالا آمده —
                      تأیید شده است.
                    </p>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
      {/* پاصفحه حالا یک قابِ گردِ شناور است، پس مثل بقیهٔ پوسته باید از
          لبه‌های پنجره فاصله بگیرد. */}
      <div className="px-3 pb-3 lg:px-4 lg:pb-4">
        <Footer />
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-gray-50 py-1.5">
      <dt className="text-gray-500">{label}</dt>
      <dd className="font-medium text-gray-800">{value}</dd>
    </div>
  );
}
