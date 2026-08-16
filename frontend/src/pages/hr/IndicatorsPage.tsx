import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, Reorder, useDragControls } from "motion/react";
import { apiClient, extractErrorMessage } from "../../api/client";
import { useAppConfig, useIndicators } from "../../api/queries";
import { useConfirm } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toast";
import { Button } from "../../ui/Button";
import { PageHeader, TableSkeleton } from "../../ui/Card";
import { Modal } from "../../ui/Modal";
import { TAB_TRANSITION } from "../../ui/motion";
import type { FrameworkImpact, Indicator, IndicatorSection } from "../../types";

const inputClass =
  "w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white";

/** «در ۲۳ ارزیابی استفاده شده» — یا سکوت، وقتی هنوز جایی استفاده نشده. */
function useCountLabel(ind: Indicator): string {
  return ind.usage_count > 0
    ? `این شاخص در ${ind.usage_count.toLocaleString("fa-IR")} ارزیابی ثبت‌شده استفاده شده است؛ آن‌ها دست‌نخورده می‌مانند.`
    : "این شاخص هنوز در هیچ ارزیابی‌ای استفاده نشده است.";
}

export function IndicatorsPage() {
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const config = useAppConfig();
  const [section, setSection] = useState<IndicatorSection>("general");
  const [form, setForm] = useState({ category: "", description: "" });
  const [error, setError] = useState<string | null>(null);
  const [showAddIndicator, setShowAddIndicator] = useState(false);
  const [editing, setEditing] = useState<Indicator | null>(null);

  const { data, error: loadError, isPending } = useIndicators({ section, includeInactive: true });
  const { data: framework } = useQuery({
    queryKey: ["indicators", "framework"],
    queryFn: async () =>
      (await apiClient.get<FrameworkImpact>("/indicators/framework")).data,
  });

  // نسخهٔ محلی مرتب‌شده که drag روی آن اعمال می‌شود؛ با هر تغییر بخش/داده هم‌گام می‌شود.
  const [items, setItems] = useState<Indicator[]>([]);
  useEffect(() => {
    if (data) setItems([...data].sort((a, b) => a.display_order - b.display_order));
  }, [data]);

  const generalPct = Math.round(config.general_section_weight * 100);
  const specializedPct = Math.round(config.specialized_section_weight * 100);

  async function invalidate() {
    await queryClient.invalidateQueries({ queryKey: ["indicators"] });
    // پروندهٔ باز ممکن است به نسخهٔ تازه منتقل شده باشد؛ کشِ کهنه، فرمی نشان
    // می‌دهد که با آنچه سرور برای «ثبت» می‌خواهد یکی نیست.
    await queryClient.invalidateQueries({ queryKey: ["evaluation"] });
  }

  async function createIndicator() {
    setError(null);
    try {
      await apiClient.post("/indicators", { ...form, section });
      setForm({ category: "", description: "" });
      await invalidate();
      setShowAddIndicator(false);
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
        description:
          "این شاخص از فرم‌های ارزیابی جدید برداشته می‌شود. " +
          `${useCountLabel(ind)} و پرونده‌های بازی که قبلاً امتیاز خورده‌اند همچنان همین سؤال را می‌پرسند — ` +
          "پس هیچ ارزیابیِ نیمه‌کاره‌ای قفل نمی‌شود.",
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
        ind.usage_count > 0
          ? `${useCountLabel(ind)} به همین دلیل حذف مجاز نیست و درخواست رد می‌شود؛ برای کنار گذاشتنش از فرم‌های جدید، «غیرفعال»‌اش کنید.`
          : "این شاخص برای همیشه حذف می‌شود. چون هنوز جایی استفاده نشده، هیچ داده‌ای از دست نمی‌رود.",
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

      {framework && <FrameworkNote impact={framework} />}

      <div className="flex flex-wrap items-center justify-between gap-2">
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
                transition={{ type: "spring", stiffness: 300, damping: 30 }}
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
        <Button onClick={() => { setError(null); setShowAddIndicator(true); }}>
          + افزودن شاخص
        </Button>
      </div>

      {showAddIndicator && (
        <Modal
          title="افزودن شاخص"
          onClose={() => setShowAddIndicator(false)}
          footer={
            <>
              <Button variant="secondary" onClick={() => setShowAddIndicator(false)}>
                انصراف
              </Button>
              <Button type="submit" form="add-indicator-form">
                افزودن
              </Button>
            </>
          }
        >
        <form
          id="add-indicator-form"
          onSubmit={(e) => {
            e.preventDefault();
            createIndicator();
          }}
          className="flex flex-wrap items-end gap-3 py-2 text-sm"
        >
          <p className="w-full text-xs text-gray-500">
            این شاخص به بخش «{section === "general" ? "عمومی" : "تخصصی"}» افزوده می‌شود.
          </p>
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
        </form>
        {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
        </Modal>
      )}

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
          <span className="w-20 text-center">استفاده</span>
          <span className="w-16 text-center">وضعیت</span>
          <span className="w-36 text-left">عملیات</span>
        </div>

        <motion.div key={section} {...TAB_TRANSITION}>
        {isPending ? (
          <TableSkeleton rows={6} />
        ) : items.length === 0 ? (
          <p className="py-6 text-center text-sm text-gray-400">شاخصی تعریف نشده است.</p>
        ) : (
          <Reorder.Group axis="y" values={items} onReorder={setItems} className="space-y-1.5">
            {items.map((ind, index) => (
              <IndicatorRow
                key={ind.id}
                indicator={ind}
                position={index + 1}
                onDrop={() => persistOrder(items)}
                onEdit={() => setEditing(ind)}
                onToggle={() => toggleActive(ind)}
                onDelete={() => deleteIndicator(ind)}
              />
            ))}
          </Reorder.Group>
        )}
        </motion.div>
      </div>

      {editing && (
        <EditIndicatorModal
          indicator={editing}
          onClose={() => setEditing(null)}
          onSaved={async (message) => {
            setEditing(null);
            await invalidate();
            showSuccess(message);
          }}
        />
      )}
    </div>
  );
}

/** نسخهٔ چارچوب، و اینکه تغییر بعدی روی چه چیزی اثر می‌گذارد.
 *
 * این کارت جواب سؤالی است که تا امروز پرسیده نمی‌شد چون کسی نمی‌دانست باید
 * بپرسدش: «اگر الان این سؤال را عوض کنم، چه اتفاقی برای پرونده‌های در جریان
 * می‌افتد؟» جوابِ قدیمی «دوازده‌تاشان قفل می‌شوند» بود، و بی‌صدا.
 */
function FrameworkNote({ impact }: { impact: FrameworkImpact }) {
  const fa = (n: number) => n.toLocaleString("fa-IR");
  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-bold text-gray-900">
          نسخهٔ فعلی فرم: {fa(impact.version)}
        </p>
        <p className="text-xs text-gray-400">
          {fa(impact.member_count)} شاخص فعال
        </p>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-gray-500">
        هر پرونده به نسخه‌ای که زیر آن باز شده گره می‌خورد. یعنی افزودن یا برداشتن
        یک شاخص، ارزیابی‌های در جریان را نمی‌شکند — چیزی که ارزیاب جلویش دارد همان
        می‌ماند تا کارش تمام شود.
      </p>
      {(impact.frozen_open_records > 0 || impact.movable_open_records > 0) && (
        <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-2 border-t border-gray-100 pt-3 text-xs">
          <div className="flex items-baseline gap-1.5">
            <dt className="text-gray-500">با نسخهٔ فعلی خودشان بسته می‌شوند:</dt>
            <dd className="font-bold text-gray-900">
              {fa(impact.frozen_open_records)} پرونده
            </dd>
          </div>
          <div className="flex items-baseline gap-1.5">
            <dt className="text-gray-500">دست‌نخورده‌اند و به نسخهٔ تازه می‌روند:</dt>
            <dd className="font-bold text-gray-900">
              {fa(impact.movable_open_records)} پرونده
            </dd>
          </div>
        </dl>
      )}
    </div>
  );
}

/** ویرایش متن یک شاخص — با دو راهِ صریح، چون معنا و نگارش دو چیزند.
 *
 * تا امروز این صفحه اصلاً امکان ویرایش متن نداشت: یک غلط املایی فقط با حذف و
 * ساخت دوباره درست می‌شد، که تاریخِ همان شاخص را هم پاک می‌کرد. حالا هر دو راه
 * هست، ولی کاربر باید بگوید کدام یکی است — چون سامانه نمی‌تواند تشخیص بدهد و
 * حدس زدنش دقیقاً همان بازنویسی خاموشِ تاریخ است.
 */
function EditIndicatorModal({
  indicator,
  onClose,
  onSaved,
}: {
  indicator: Indicator;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const [category, setCategory] = useState(indicator.category);
  const [description, setDescription] = useState(indicator.description);
  const [mode, setMode] = useState<"wording" | "meaning">("wording");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const used = indicator.usage_count > 0;
  const changed = category !== indicator.category || description !== indicator.description;

  async function save() {
    setError(null);
    setBusy(true);
    try {
      if (used && mode === "meaning") {
        await apiClient.post(`/indicators/${indicator.id}/replace`, {
          category,
          description,
          reason,
        });
        onSaved("شاخص تازه ساخته شد و شاخص قبلی بایگانی شد");
      } else {
        await apiClient.patch(`/indicators/${indicator.id}`, {
          category,
          description,
          ...(used ? { wording_fix_reason: reason } : {}),
        });
        onSaved("شاخص به‌روزرسانی شد");
      }
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={`ویرایش «${indicator.category}»`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            انصراف
          </Button>
          <Button type="submit" form="edit-indicator-form" disabled={busy || !changed}>
            {busy ? "در حال ذخیره…" : used && mode === "meaning" ? "ساخت شاخص تازه" : "ذخیره"}
          </Button>
        </>
      }
    >
      <form
        id="edit-indicator-form"
        onSubmit={(e) => {
          e.preventDefault();
          save();
        }}
        className="space-y-4 py-2 text-sm"
      >
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          دسته
          <input
            required
            className={inputClass}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          شرح شاخص
          <input
            required
            className={inputClass}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>

        {used ? (
          <div className="space-y-3 rounded-xl bg-amber-50/60 p-4 ring-1 ring-amber-100">
            <p className="text-xs leading-relaxed text-amber-900">
              {useCountLabel(indicator)} پس این ویرایش می‌تواند معنای گذشته را عوض کند.
              کدام‌یک است؟
            </p>
            <label className="flex cursor-pointer items-start gap-2 text-xs text-amber-900">
              <input
                type="radio"
                name="edit-mode"
                className="mt-0.5"
                checked={mode === "wording"}
                onChange={() => setMode("wording")}
              />
              <span>
                <b>فقط نگارش را اصلاح می‌کنم.</b> سؤال همان سؤال است. متن درجا عوض
                می‌شود و مقایسه‌های گذشته معتبر می‌مانند.
              </span>
            </label>
            <label className="flex cursor-pointer items-start gap-2 text-xs text-amber-900">
              <input
                type="radio"
                name="edit-mode"
                className="mt-0.5"
                checked={mode === "meaning"}
                onChange={() => setMode("meaning")}
              />
              <span>
                <b>معنای سؤال عوض می‌شود.</b> شاخص تازه‌ای با همین جایگاه ساخته و
                شاخص فعلی بایگانی می‌شود، تا نمودارها دو سؤال متفاوت را یکی نبینند.
              </span>
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-amber-900">
              دلیل (در گزارش رویدادها ثبت می‌شود)
              <input
                required
                minLength={3}
                className={inputClass}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={
                  mode === "wording" ? "مثلاً: غلط املایی" : "مثلاً: سؤال دو مفهوم را با هم می‌پرسید"
                }
              />
            </label>
          </div>
        ) : (
          <p className="rounded-xl bg-gray-50 px-3 py-2 text-xs text-gray-500">
            این شاخص هنوز در هیچ ارزیابی‌ای استفاده نشده، پس ویرایشش هیچ تاریخی را
            عوض نمی‌کند.
          </p>
        )}

        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
      </form>
    </Modal>
  );
}

/** یک ردیف قابل‌کشیدن؛ drag فقط از روی دستگیره شروع می‌شود تا کلیک روی دکمه‌ها با
 * کشیدن اشتباه نگیرد. */
function IndicatorRow({
  indicator,
  position,
  onDrop,
  onEdit,
  onToggle,
  onDelete,
}: {
  indicator: Indicator;
  position: number;
  onDrop: () => void;
  onEdit: () => void;
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
      <span className="w-20 text-center text-xs tabular-nums text-gray-400">
        {indicator.usage_count > 0
          ? `${indicator.usage_count.toLocaleString("fa-IR")} ارزیابی`
          : "—"}
      </span>
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
      <span className="flex w-36 items-center justify-start gap-2">
        <button
          onClick={onEdit}
          className="cursor-pointer text-xs font-medium text-gray-500 hover:text-gray-900"
          aria-label={`ویرایش ${indicator.category}`}
        >
          ویرایش
        </button>
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
