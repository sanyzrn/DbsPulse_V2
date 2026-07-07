import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { apiClient, extractErrorMessage } from "../../api/client";
import { useAppConfig, useIndicators } from "../../api/queries";
import { useConfirm } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toast";
import { Button } from "../../ui/Button";
import { PageHeader } from "../../ui/Card";
import { Table } from "../../ui/Table";
import type { Indicator, IndicatorSection } from "../../types";

const inputClass =
  "w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white";

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
                className="absolute inset-0 rounded-xl bg-charcoal-900 shadow-sm"
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
        <Table
          bordered={false}
          headers={["ترتیب", "دسته", "شرح", "وضعیت", ""]}
          rowKeys={indicators.map((ind) => ind.id)}
          emptyMessage="شاخصی تعریف نشده است."
          rows={indicators.map((ind) => [
            <span key="order" className="text-gray-500">
              {ind.display_order}
            </span>,
            <span key="category" className="font-medium text-gray-700">
              {ind.category}
            </span>,
            <span key="desc" className="text-gray-600">
              {ind.description}
            </span>,
            ind.is_active ? (
              <span key="status" className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700">
                <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-green-500" />
                فعال
              </span>
            ) : (
              <span key="status" className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-500">
                <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-gray-400" />
                غیرفعال
              </span>
            ),
            <button key="action" onClick={() => toggleActive(ind)} className="text-sm font-medium text-pulse-600 hover:text-pulse-700">
              {ind.is_active ? "غیرفعال کردن" : "فعال کردن"}
            </button>,
          ])}
        />
      </div>
    </div>
  );
}
