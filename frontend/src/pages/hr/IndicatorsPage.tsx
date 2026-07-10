import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { motion, Reorder, useDragControls } from "motion/react";
import { apiClient, extractErrorMessage } from "../../api/client";
import { useAppConfig, useIndicators } from "../../api/queries";
import { useConfirm } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toast";
import { Button } from "../../ui/Button";
import { PageHeader } from "../../ui/Card";
import type { Indicator, IndicatorSection } from "../../types";

const inputClass =
  "w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white";

export function IndicatorsPage() {
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const config = useAppConfig();
  const [section, setSection] = useState<IndicatorSection>("general");
  const [form, setForm] = useState({ category: "", description: "" });
  const [error, setError] = useState<string | null>(null);

  const { data, error: loadError } = useIndicators({ section, includeInactive: true });

  // نسخهٔ محلی مرتب‌شده که drag روی آن اعمال می‌شود؛ با هر تغییر بخش/داده هم‌گام می‌شود.
  const [items, setItems] = useState<Indicator[]>([]);
  useEffect(() => {
    if (data) setItems([...data].sort((a, b) => a.display_order - b.display_order));
  }, [data]);

  const generalPct = Math.round(config.general_section_weight * 100);
  const specializedPct = Math.round(config.specialized_section_weight * 100);

  async function invalidate() {
    await queryClient.invalidateQueries({ queryKey: ["indicators"] });
  }

  async function createIndicator() {
    setError(null);
    try {
      await apiClient.post("/indicators", { ...form, section });
      setForm({ category: "", description: "" });
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

  async function deleteIndicator(ind: Indicator) {
    const ok = await confirm({
      title: `حذف «${ind.category}»؟`,
      description:
        "این شاخص برای همیشه حذف می‌شود. اگر در ارزیابی‌های ثبت‌شده استفاده شده باشد، حذف مجاز نیست و باید به‌جای آن «غیرفعال» شود.",
      confirmLabel: "حذف کن",
    });
    if (!ok) return;
    try {
      await apiClient.delete(`/indicators/${ind.id}`);
      await invalidate();
      showSuccess("شاخص حذف شد");
    } catch (err) {
      showError(extractErrorMessage(err));
    }
  }

  /** ترتیب جدید را پس از رها شدن drag ذخیره می‌کند. */
  async function persistOrder(ordered: Indicator[]) {
    try {
      await apiClient.patch("/indicators/reorder", {
        section,
        ordered_ids: ordered.map((i) => i.id),
      });
      await invalidate();
    } catch (err) {
      showError(extractErrorMessage(err));
      // در صورت خطا، به ترتیب سرور بازمی‌گردیم
      if (data) setItems([...data].sort((a, b) => a.display_order - b.display_order));
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
            className={`relative cursor-pointer rounded-xl px-4 py-1.5 text-sm font-medium transition-colors ${
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
          <Button type="submit">افزودن</Button>
        </form>
        {/* شاخص جدید خودکار به انتهای فهرست همین بخش اضافه می‌شود؛ ترتیب را با کشیدن تغییر دهید. */}
        <p className="mt-3 text-xs text-gray-400">
          شاخص جدید به انتهای فهرست افزوده می‌شود. برای تغییر ترتیب، ردیف‌ها را با دستگیرهٔ کنارشان بکشید.
        </p>
        {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
      </div>

      <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
        {loadError != null && (
          <p className="mb-2 text-sm text-red-600">{extractErrorMessage(loadError)}</p>
        )}

        {/* سرستون‌ها */}
        <div className="flex items-center gap-3 px-3 pb-2 text-xs font-medium text-gray-400">
          <span className="w-5" aria-hidden />
          <span className="w-6 text-center">#</span>
          <span className="w-40">دسته</span>
          <span className="flex-1">شرح</span>
          <span className="w-16 text-center">وضعیت</span>
          <span className="w-28 text-left">عملیات</span>
        </div>

        {items.length === 0 ? (
          <p className="py-6 text-center text-sm text-gray-400">شاخصی تعریف نشده است.</p>
        ) : (
          <Reorder.Group axis="y" values={items} onReorder={setItems} className="space-y-1.5">
            {items.map((ind, index) => (
              <IndicatorRow
                key={ind.id}
                indicator={ind}
                position={index + 1}
                onDrop={() => persistOrder(items)}
                onToggle={() => toggleActive(ind)}
                onDelete={() => deleteIndicator(ind)}
              />
            ))}
          </Reorder.Group>
        )}
      </div>
    </div>
  );
}

/** یک ردیف قابل‌کشیدن؛ drag فقط از روی دستگیره شروع می‌شود تا کلیک روی دکمه‌ها با
 * کشیدن اشتباه نگیرد. */
function IndicatorRow({
  indicator,
  position,
  onDrop,
  onToggle,
  onDelete,
}: {
  indicator: Indicator;
  position: number;
  onDrop: () => void;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const controls = useDragControls();
  return (
    <Reorder.Item
      value={indicator}
      dragListener={false}
      dragControls={controls}
      onDragEnd={onDrop}
      className="flex items-center gap-3 rounded-xl border border-gray-100 bg-white px-3 py-2.5 text-sm"
      whileDrag={{ scale: 1.01, boxShadow: "0 12px 32px rgba(0,0,0,0.10)" }}
    >
      <button
        type="button"
        onPointerDown={(e) => controls.start(e)}
        aria-label="کشیدن برای تغییر ترتیب"
        className="w-5 cursor-grab touch-none text-gray-300 transition-colors hover:text-gray-500 active:cursor-grabbing"
      >
        <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
          <circle cx="7" cy="5" r="1.4" />
          <circle cx="13" cy="5" r="1.4" />
          <circle cx="7" cy="10" r="1.4" />
          <circle cx="13" cy="10" r="1.4" />
          <circle cx="7" cy="15" r="1.4" />
          <circle cx="13" cy="15" r="1.4" />
        </svg>
      </button>
      <span className="w-6 text-center text-gray-400">{position.toLocaleString("fa-IR")}</span>
      <span className="w-40 truncate font-medium text-gray-700">{indicator.category}</span>
      <span className="flex-1 truncate text-gray-600">{indicator.description}</span>
      <span className="w-16 text-center">
        {indicator.is_active ? (
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
      </span>
      <span className="flex w-28 items-center justify-start gap-2">
        <button
          onClick={onToggle}
          className="cursor-pointer text-xs font-medium text-pulse-600 hover:text-pulse-700"
        >
          {indicator.is_active ? "غیرفعال" : "فعال"}
        </button>
        <button
          onClick={onDelete}
          className="cursor-pointer text-xs font-medium text-gray-400 hover:text-red-600"
          aria-label={`حذف ${indicator.category}`}
        >
          حذف
        </button>
      </span>
    </Reorder.Item>
  );
}
