import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { apiClient, extractErrorMessage } from "../../api/client";
import { usePeriodProgress, usePeriods } from "../../api/queries";
import { BulkCreateDialog } from "../../components/BulkCreateDialog";
import { useConfirm } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toast";
import { Button } from "../../ui/Button";
import { PageHeader } from "../../ui/Card";
import { Modal } from "../../ui/Modal";
import { CountUp, PctBar } from "../../ui/Meters";
import { Table } from "../../ui/Table";
import { JalaliDatePicker } from "../../ui/JalaliDatePicker";
import { formatDate } from "../../utils/dates";
import type { EvaluationPeriod } from "../../types";

const emptyForm = { name: "", starts_on: "", ends_on: "" };

const inputClass =
  "w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white";

export function PeriodsPage() {
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState<string | null>(null);
  const [showAddPeriod, setShowAddPeriod] = useState(false);
  const [showBulkCreate, setShowBulkCreate] = useState(false);

  const { data: periods = [], error: loadError } = usePeriods();
  const openPeriod = periods.find((p) => p.status === "open") ?? null;
  // برای پیام تأیید بستن: چند پرونده هنوز وسط گردش‌کار است
  const { data: openProgress } = usePeriodProgress(openPeriod?.id ?? null);

  async function invalidate() {
    await queryClient.invalidateQueries({ queryKey: ["periods"] });
  }

  async function createPeriod() {
    setError(null);
    try {
      await apiClient.post("/periods", form);
      setForm(emptyForm);
      await invalidate();
      setShowAddPeriod(false);
      showSuccess("دوره ارزیابی آغاز شد و به ارزیاب‌ها اطلاع داده شد");
    } catch (err) {
      const message = extractErrorMessage(err);
      setError(message);
      showError(message);
    }
  }

  async function closePeriod(period: EvaluationPeriod) {
    // بستن دوره‌ای که ده پرونده وسط گردش‌کار دارد، اشتباهی است که باید *پیش* از
    // انجامش دیده شود. پرونده‌های باز از بین نمی‌روند و برچسب همین دوره را نگه
    // می‌دارند، ولی HR باید بداند دارد روی چه چیزی خط می‌کشد.
    const stillOpen = openProgress?.in_progress ?? 0;
    const notStarted = openProgress?.not_started_total ?? 0;
    const warnings = [
      stillOpen > 0
        ? `${stillOpen.toLocaleString("fa-IR")} پرونده هنوز وسط گردش‌کار است (باز می‌مانند و برچسب همین دوره را نگه می‌دارند).`
        : null,
      notStarted > 0
        ? `برای ${notStarted.toLocaleString("fa-IR")} نفر هیچ ارزیابی‌ای شروع نشده است.`
        : null,
    ].filter(Boolean);

    const ok = await confirm({
      title: `بستن دوره «${period.name}»؟`,
      danger: true,
      description: [
        "پس از بستن، ارزیابی‌های جدید دیگر به این دوره برچسب نمی‌خورند.",
        ...warnings,
      ].join(" "),
      confirmLabel: "بستن دوره",
    });
    if (!ok) return;
    try {
      // سرور بستنِ دوره‌ای که پروندهٔ باز دارد را رد می‌کند مگر با `force` —
      // یعنی تأییدِ آگاهانه لازم است. همان تأیید بالا این نقش را دارد، پس فقط
      // وقتی `force` می‌فرستیم که واقعاً پروندهٔ بازی به کاربر نشان داده شده
      // باشد. اگر شمارشِ فرانت کهنه بوده باشد، سرور جلویش را می‌گیرد و پیامش
      // را نشان می‌دهیم — که دقیقاً همان چیزی است که باید بشود.
      await apiClient.post(`/periods/${period.id}/close`, null, {
        params: stillOpen > 0 ? { force: true } : undefined,
      });
      await invalidate();
      showSuccess("دوره بسته شد");
    } catch (err) {
      showError(extractErrorMessage(err));
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="دوره‌های ارزیابی" subtitle="آغاز، پایش پیشرفت و بستن دوره‌های ارزیابی سازمان" />
      {/* ساخت دسته‌ای این‌جاست چون «باز کردن چرخه» همین صفحه است؛ پروندهٔ ساخته‌شده
          به همان دورهٔ باز برچسب می‌خورد و پیشرفتش در همین صفحه دیده می‌شود. */}
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="secondary" onClick={() => setShowBulkCreate(true)}>
          ساخت دسته‌ای ارزیابی
        </Button>
        {!openPeriod && (
          <Button onClick={() => { setError(null); setShowAddPeriod(true); }}>
            + آغاز دوره ارزیابی جدید
          </Button>
        )}
      </div>
      {showBulkCreate && <BulkCreateDialog onClose={() => setShowBulkCreate(false)} />}
      {showAddPeriod && !openPeriod && (
        <Modal
          title="آغاز دوره ارزیابی جدید"
          onClose={() => setShowAddPeriod(false)}
          footer={
            <>
              <Button variant="secondary" onClick={() => setShowAddPeriod(false)}>
                انصراف
              </Button>
              <Button type="submit" form="add-period-form">
                آغاز دوره
              </Button>
            </>
          }
        >
          <form
            id="add-period-form"
            onSubmit={(e) => {
              e.preventDefault();
              createPeriod();
            }}
            className="flex flex-wrap items-end gap-3 py-2 text-sm"
          >
            <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
              نام دوره (مثلاً «دوره پاییز ۱۴۰۵»)
              <input required className={`${inputClass} sm:w-56`} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
              تاریخ شروع
              <JalaliDatePicker required className={inputClass} value={form.starts_on} onChange={(iso) => setForm({ ...form, starts_on: iso })} />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
              تاریخ پایان
              <JalaliDatePicker required className={inputClass} value={form.ends_on} onChange={(iso) => setForm({ ...form, ends_on: iso })} />
            </label>
          </form>
          {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
        </Modal>
      )}

      {openPeriod && <OpenPeriodCard period={openPeriod} onClose={() => closePeriod(openPeriod)} />}

      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-card">
        <h2 className="mb-4 text-base font-bold text-gray-900">تاریخچه دوره‌ها</h2>
        {loadError != null && (
          <p className="mb-2 text-sm text-red-600">{extractErrorMessage(loadError)}</p>
        )}
        <Table
          bordered={false}
          headers={["نام", "بازه", "وضعیت"]}
          rowKeys={periods.map((p) => p.id)}
          emptyMessage="هنوز دوره‌ای تعریف نشده است."
          rows={periods.map((p) => [
            <span key="name" className="font-medium text-gray-700">
              {p.name}
            </span>,
            <span key="range" className="text-gray-500">
              {formatDate(p.starts_on)} تا {formatDate(p.ends_on)}
            </span>,
            p.status === "open" ? (
              <span key="status" className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700">
                <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-green-500" />
                باز
              </span>
            ) : (
              <span key="status" className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-500">
                <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-gray-400" />
                بسته
              </span>
            ),
          ])}
        />
      </div>
    </div>
  );
}

function OpenPeriodCard({ period, onClose }: { period: EvaluationPeriod; onClose: () => void }) {
  const { data: progress } = usePeriodProgress(period.id);

  const eligible = progress?.eligible ?? 0;
  const started = progress?.started ?? 0;
  const finalized = progress?.finalized ?? 0;
  const inProgress = progress?.in_progress ?? 0;
  const notStartedTotal = progress?.not_started_total ?? 0;
  const pct = (value: number) => (eligible ? Math.round((value / eligible) * 100) : 0);

  return (
    <motion.div
      className="rounded-2xl border-2 border-pulse-100 bg-white p-5 shadow-card"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-base font-bold text-gray-900">
            دوره باز: {period.name}
            <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700">
              <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-green-500" style={{ animation: "var(--animate-pulse-slow)" }} />
              در جریان
            </span>
          </h2>
          <p className="mt-1 text-xs text-gray-400">
            {formatDate(period.starts_on)} تا {formatDate(period.ends_on)}
          </p>
        </div>
        <button
          onClick={onClose}
          className="rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm transition-all duration-200 hover:bg-gray-50 hover:shadow-md"
        >
          بستن دوره
        </button>
      </div>

      {progress && (
        <>
          <div className="mb-4 grid grid-cols-1 gap-3 text-center text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl bg-gray-50 p-4">
              <p className="text-xs text-gray-500">واجدان ارزیابی</p>
              <p className="mt-1 text-2xl font-extrabold tabular-nums text-gray-900">
                <CountUp value={eligible} format="plain" />
              </p>
            </div>
            <div className="rounded-2xl bg-pulse-50/50 p-4">
              <p className="text-xs text-gray-500">آغاز شده</p>
              <p className="mt-1 text-2xl font-extrabold tabular-nums text-gray-900">
                <CountUp value={started} format="plain" />
                <span className="mr-1 text-sm font-semibold">
                  ({pct(started).toLocaleString("fa-IR")}٪)
                </span>
              </p>
              <PctBar value={pct(started)} tone="green" className="mt-2" />
            </div>
            <div className="rounded-2xl bg-amber-50 p-4">
              <p className="text-xs text-amber-700">در جریان</p>
              <p className="mt-1 text-2xl font-extrabold tabular-nums text-amber-800">
                <CountUp value={inProgress} format="plain" />
              </p>
              <p className="mt-2 text-[11px] text-amber-700">
                {inProgress > 0 ? "پیش از بستن دوره تعیین تکلیف شوند" : "پرونده‌ای باز نمانده"}
              </p>
            </div>
            <div className="rounded-2xl bg-green-50 p-4">
              <p className="text-xs text-green-600">نهایی شده</p>
              <p className="mt-1 text-2xl font-extrabold tabular-nums text-green-700">
                <CountUp value={finalized} format="plain" />
                <span className="mr-1 text-sm font-semibold">
                  ({pct(finalized).toLocaleString("fa-IR")}٪)
                </span>
              </p>
              <PctBar value={pct(finalized)} tone="green" className="mt-2" />
            </div>
          </div>

          {/* پرسنلی که زنجیرهٔ ارزیابی ندارند: تا امروز از *مخرج* حذف می‌شدند، پس
              پوشش می‌توانست ۱۰۰٪ نشان بدهد در حالی که این‌ها ارزیابی نشده بودند.
              حالا یک شکافِ دیده‌شدنی‌اند، با راه‌حلش. */}
          {(progress.without_chain_total ?? 0) > 0 && (
            <div className="mb-4 rounded-2xl border border-red-200 bg-red-50/60 p-4">
              <h3 className="flex items-center gap-2 text-sm font-bold text-red-800">
                <span className="flex h-5 min-w-5 items-center justify-center rounded-md bg-red-100 px-1 text-[10px]">
                  {(progress.without_chain_total ?? 0).toLocaleString("fa-IR")}
                </span>
                زنجیرهٔ ارزیابی ندارند
              </h3>
              <p className="mt-1 text-xs leading-relaxed text-red-700">
                تا زنجیره‌شان در «دسترسی ارزیابی» تعیین نشود، هیچ‌کس نمی‌تواند ارزیابی‌شان
                کند — و در آمار پوشش هم به‌عنوان شروع‌نشده شمرده می‌شوند.
              </p>
              <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-red-900">
                {progress.without_chain.map((p) => (
                  <li key={p.personnel_id}>
                    {p.full_name} <span className="text-red-400">· {p.org_unit}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {progress.not_started.length > 0 && (
            <div>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-bold text-amber-700">
                <span className="flex h-5 min-w-5 items-center justify-center rounded-md bg-amber-100 px-1 text-[10px]">
                  {notStartedTotal.toLocaleString("fa-IR")}
                </span>
                هنوز آغاز نشده
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <tbody>
                    {progress.not_started.map((p, idx) => (
                      <motion.tr
                        key={p.personnel_id}
                        className="border-b border-gray-50 transition-colors last:border-0 hover:bg-amber-50/30"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.2, delay: idx * 0.02 }}
                      >
                        <td className="px-3 py-2 text-gray-700">{p.full_name}</td>
                        <td className="px-3 py-2 text-gray-400">{p.org_unit}</td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {notStartedTotal > progress.not_started.length && (
                <p className="mt-2 text-xs text-gray-400">
                  {progress.not_started.length.toLocaleString("fa-IR")} نفر نخست نمایش داده
                  شده‌اند؛ مجموع {notStartedTotal.toLocaleString("fa-IR")} نفر است.
                </p>
              )}
            </div>
          )}
          {progress.not_started.length === 0 && (
            <p className="flex items-center justify-center gap-2 rounded-xl bg-green-50 py-3 text-sm font-medium text-green-700">
              <span className="text-lg">🎉</span>
              ارزیابی همه واجدان این دوره آغاز شده است.
            </p>
          )}
        </>
      )}
    </motion.div>
  );
}
