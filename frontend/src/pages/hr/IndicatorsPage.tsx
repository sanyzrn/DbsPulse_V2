import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { apiClient, extractErrorMessage } from "../../api/client";
import { useAppConfig, useIndicators } from "../../api/queries";
import { useConfirm } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toast";
import { Button } from "../../ui/Button";
import { PageHeader } from "../../ui/Card";
import type { Indicator, IndicatorSection } from "../../types";

const inputClass =
  "w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition-all duration-200 focus:border-gray-400";

export function IndicatorsPage() {
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const config = useAppConfig();
  const [section, setSection] = useState<IndicatorSection>("general");
  const [form, setForm] = useState({ category: "", description: "", display_order: 1 });
  const [error, setError] = useState<string | null>(null);

  const { data, error: loadError } = useIndicators({ section, includeInactive: true });
  const indicators = [...(data ?? [])].sort((a, b) => a.display_order - b.display_order);

  const generalPct = Math.round(config.general_section_weight * 100);
  const specializedPct = Math.round(config.specialized_section_weight * 100);

  async function invalidate() {
    await queryClient.invalidateQueries({ queryKey: ["indicators"] });
  }

  async function createIndicator() {
    setError(null);
    try {
      await apiClient.post("/indicators", { ...form, section });
      setForm({ category: "", description: "", display_order: 1 });
      await invalidate();
      showSuccess("شاخص با موفقیت افزوده شد");
    } catch (err) {
      const message = extractErrorMessage(err);
      setError(message);
      showError(message);
    }
  }

  async function toggleActive(ind: Indicator) {
    if (ind.is_active) {
      const ok = await confirm({
        title: `غیرفعال کردن «${ind.category}»؟`,
        description: "این شاخص دیگر در فرم‌های ارزیابی جدید نمایش داده نمی‌شود، اما داده‌های تاریخی حفظ می‌شوند.",
        confirmLabel: "غیرفعال کن",
      });
      if (!ok) return;
    }
    try {
      await apiClient.patch(`/indicators/${ind.id}`, { is_active: !ind.is_active });
      await invalidate();
      showSuccess(ind.is_active ? "شاخص غیرفعال شد" : "شاخص فعال شد");
    } catch (err) {
      showError(extractErrorMessage(err));
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="شاخص‌های ارزیابی" subtitle="تعریف و مدیریت شاخص‌های عمومی و تخصصی فرم ارزیابی" />

      {/* تب‌های مدرن با نشانگر گرادیانت متحرک */}
      <div
        role="tablist"
        aria-label="بخش شاخص‌ها"
        className="inline-flex rounded-2xl border border-gray-100 bg-white p-1 shadow-sm"
      >
        {(["general", "specialized"] as const).map((s) => (
          <button
            key={s}
            role="tab"
            aria-selected={section === s}
            onClick={() => setSection(s)}
            className={`relative rounded-xl px-4 py-1.5 text-sm font-medium transition-colors ${
              section === s ? "text-white" : "text-gray-600 hover:text-gray-900"
            }`}
          >
            {section === s && (
              <motion.span
                layoutId="indicator-tab"
                className="absolute inset-0 rounded-xl bg-gradient-to-bl from-pulse-500 to-pulse-violet-600 shadow-sm"
                transition={{ type: "spring", stiffness: 400, damping: 32 }}
              />
            )}
            <span className="relative">
              {s === "general"
                ? `شاخص‌های عمومی (${generalPct.toLocaleString("fa-IR")}٪)`
                : `شاخص‌های تخصصی (${specializedPct.toLocaleString("fa-IR")}٪)`}
            </span>
          </button>
        ))}
      </div>

      <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
        <h2 className="mb-4 text-base font-bold text-gray-900">افزودن شاخص</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createIndicator();
          }}
          className="flex flex-wrap items-end gap-3 text-sm"
        >
          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            دسته (مثلاً «تعهد سازمانی»)
            <input
              required
              className={`${inputClass} sm:w-48`}
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            />
          </label>
          <label className="flex flex-1 flex-col gap-1 text-xs font-medium text-gray-600">
            شرح شاخص
            <input
              required
              className={inputClass}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            ترتیب
            <input
              type="number"
              min={0}
              className={`${inputClass} w-20`}
              value={form.display_order}
              onChange={(e) => setForm({ ...form, display_order: Number(e.target.value) })}
            />
          </label>
          <Button type="submit">افزودن</Button>
        </form>
        {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
      </div>

      <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
        {loadError != null && (
          <p className="mb-2 text-sm text-red-600">{extractErrorMessage(loadError)}</p>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gradient-to-l from-pulse-50/50 to-pulse-violet-50/50">
                <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">ترتیب</th>
                <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">دسته</th>
                <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">شرح</th>
                <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">وضعیت</th>
                <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600"></th>
              </tr>
            </thead>
            <tbody>
              {indicators.map((ind, idx) => (
                <motion.tr
                  key={ind.id}
                  className="border-b border-gray-50 transition-colors last:border-0 hover:bg-pulse-50/30"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.2, delay: idx * 0.03 }}
                >
                  <td className="px-3 py-2.5 text-gray-500">{ind.display_order}</td>
                  <td className="px-3 py-2.5 font-medium text-gray-700">{ind.category}</td>
                  <td className="px-3 py-2.5 text-gray-600">{ind.description}</td>
                  <td className="px-3 py-2.5">
                    {ind.is_active ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700">
                        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-green-500" />
                        فعال
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-500">
                        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-gray-400" />
                        غیرفعال
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <button onClick={() => toggleActive(ind)} className="text-sm font-medium text-pulse-600 hover:text-pulse-700">
                      {ind.is_active ? "غیرفعال کردن" : "فعال کردن"}
                    </button>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
        {indicators.length === 0 && (
          <p className="mt-3 text-center text-sm text-gray-400">شاخصی تعریف نشده است.</p>
        )}
      </div>
    </div>
  );
}
