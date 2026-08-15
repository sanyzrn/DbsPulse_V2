/** ویرایشگر طرح نمره‌دهی (P1-04).
 *
 * تا امروز وزن بخش‌ها، قاعدهٔ شواهد و جدول نتیجه ثابت‌های پایتون بودند: سازمانی
 * که ۷۰/۳۰ می‌خواست به یک تغییر کد و استقرار نیاز داشت.
 *
 * ساختار این صفحه از خطرِ خودِ قابلیت می‌آید. عوض‌کردن وزن‌ها تصمیمی است که
 * پیامدش تا وقتی روی دادهٔ واقعی دیده نشود قابل تصور نیست — «۰٫۷ به‌جای ۰٫۶» یک
 * عدد است، «۱۴ نفر از تمدید استاندارد به تمدید مشروط منتقل می‌شوند» یک تصمیم.
 * پس پیش‌نمایش وسط صفحه است، نه پشت یک دکمهٔ فرعی، و دکمهٔ ساخت تا وقتی
 * پیش‌نمایش دیده نشده غیرفعال است.
 */
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../../api/client";
import { useConfirm } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toast";
import { Button } from "../../ui/Button";
import { Card, EmptyState, PageHeader, TableSkeleton } from "../../ui/Card";
import { Modal } from "../../ui/Modal";
import { formatDateTime } from "../../utils/dates";

interface ThresholdBand {
  upper_exclusive: number;
  label: string;
}

interface Scheme {
  id: number;
  version: number;
  name: string;
  status: "draft" | "active" | "retired";
  general_section_weight: number;
  specialized_section_weight: number;
  evidence_required_scores: number[];
  evidence_min_words: number;
  evidence_max_words: number;
  thresholds: ThresholdBand[];
  indicator_weights: Record<string, number>;
  created_at: string;
  created_by_username: string | null;
  activated_at: string | null;
  activated_by_username: string | null;
  retired_at: string | null;
}

interface ReclassifiedCase {
  evaluation_code: string;
  org_unit: string;
  current_final_pct: number;
  proposed_final_pct: number;
  current_recommendation: string;
  proposed_recommendation: string;
}

interface Preview {
  sample_size: number;
  changed_count: number;
  transitions: { from: string; to: string; count: number }[];
  cases: ReclassifiedCase[];
}

interface SchemeForm {
  name: string;
  general_section_weight: number;
  specialized_section_weight: number;
  evidence_required_scores: number[];
  evidence_min_words: number;
  evidence_max_words: number;
  thresholds: ThresholdBand[];
}

const faInt = (n: number) => n.toLocaleString("fa-IR");
const fa1 = (n: number) =>
  n.toLocaleString("fa-IR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

const STATUS_LABEL: Record<Scheme["status"], string> = {
  draft: "پیش‌نویس",
  active: "فعال",
  retired: "بازنشسته",
};

const STATUS_TONE: Record<Scheme["status"], string> = {
  draft: "bg-amber-50 text-amber-800",
  active: "bg-green-50 text-green-700",
  retired: "bg-gray-100 text-gray-500",
};

// عمداً بدون عرض. ترکیب‌کردن `${inputClass} w-20` کار نمی‌کند: ترتیب کلاس‌ها در
// رشته تعیین‌کنندهٔ اولویت CSS نیست، پس `w-full` می‌توانست روی `w-20` غالب شود و
// ورودی کوچک را تمام‌عرض کند — دقیقاً همان چیزی که ردیف‌های جدول را از مودال
// بیرون می‌زد. عرض هر جا صریح داده می‌شود.
const fieldClass =
  "rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-900 outline-none transition-colors focus:border-pulse-500 focus:bg-white";
const inputClass = `${fieldClass} w-full`;

function formFrom(scheme: Scheme): SchemeForm {
  return {
    name: `برگرفته از نسخهٔ ${faInt(scheme.version)}`,
    general_section_weight: scheme.general_section_weight,
    specialized_section_weight: scheme.specialized_section_weight,
    evidence_required_scores: [...scheme.evidence_required_scores],
    evidence_min_words: scheme.evidence_min_words,
    evidence_max_words: scheme.evidence_max_words,
    thresholds: scheme.thresholds.map((b) => ({ ...b })),
  };
}

export function ScoringSchemesPage() {
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<SchemeForm | null>(null);

  const { data: schemes = [], isPending, error } = useQuery({
    queryKey: ["scoring-schemes"],
    queryFn: async () => (await apiClient.get<Scheme[]>("/scoring-schemes")).data,
  });

  const active = schemes.find((s) => s.status === "active");

  async function activate(scheme: Scheme) {
    const ok = await confirm({
      title: `فعال‌سازی نسخهٔ ${faInt(scheme.version)}؟`,
      description:
        "از این پس ارزیابی‌های جدید با این قواعد ساخته می‌شوند. پرونده‌های موجود دست‌نخورده می‌مانند — هرکدام با همان نسخه‌ای که زیرش باز شده حساب می‌شود.",
      confirmLabel: "فعال کن",
    });
    if (!ok) return;
    try {
      await apiClient.post(`/scoring-schemes/${scheme.id}/activate`);
      await queryClient.invalidateQueries({ queryKey: ["scoring-schemes"] });
      await queryClient.invalidateQueries({ queryKey: ["config"] });
      showSuccess(`نسخهٔ ${faInt(scheme.version)} فعال شد`);
    } catch (err) {
      showError(extractErrorMessage(err));
    }
  }

  async function remove(scheme: Scheme) {
    const ok = await confirm({
      title: "حذف این پیش‌نویس؟",
      description: "پیش‌نویس هیچ اثری روی پرونده‌ها ندارد و حذفش بی‌خطر است.",
      confirmLabel: "حذف",
    });
    if (!ok) return;
    try {
      await apiClient.delete(`/scoring-schemes/${scheme.id}`);
      await queryClient.invalidateQueries({ queryKey: ["scoring-schemes"] });
      showSuccess("پیش‌نویس حذف شد");
    } catch (err) {
      showError(extractErrorMessage(err));
    }
  }

  if (error != null)
    return <p className="p-6 text-center text-sm text-red-600">{extractErrorMessage(error)}</p>;

  return (
    <div className="space-y-5">
      <PageHeader
        title="طرح نمره‌دهی"
        subtitle="وزن بخش‌ها، قاعدهٔ شواهد و جدول نتیجه — نسخه‌دار، تا تغییرشان معنای پرونده‌های گذشته را عوض نکند"
      />

      <div className="flex justify-end">
        <Button onClick={() => setEditing(active ? formFrom(active) : null)} disabled={!active}>
          + ساخت نسخهٔ جدید
        </Button>
      </div>

      {editing && (
        <SchemeEditor
          initial={editing}
          onClose={() => setEditing(null)}
          onCreated={async () => {
            setEditing(null);
            await queryClient.invalidateQueries({ queryKey: ["scoring-schemes"] });
          }}
        />
      )}

      {isPending ? (
        <Card>
          <TableSkeleton rows={3} />
        </Card>
      ) : (
        <div className="space-y-3">
          {schemes.map((scheme) => (
            <Card key={scheme.id}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-bold text-gray-900">
                      نسخهٔ {faInt(scheme.version)} — {scheme.name}
                    </span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${STATUS_TONE[scheme.status]}`}
                    >
                      {STATUS_LABEL[scheme.status]}
                    </span>
                  </p>
                  <p className="mt-1 text-[11px] text-gray-400">
                    ساخته‌شده {formatDateTime(scheme.created_at)}
                    {scheme.created_by_username && ` توسط ${scheme.created_by_username}`}
                    {scheme.activated_at &&
                      ` · فعال‌شده ${formatDateTime(scheme.activated_at)}${
                        scheme.activated_by_username ? ` توسط ${scheme.activated_by_username}` : ""
                      }`}
                  </p>
                </div>
                {scheme.status === "draft" && (
                  <div className="flex shrink-0 gap-2">
                    <Button variant="secondary" onClick={() => remove(scheme)}>
                      حذف
                    </Button>
                    <Button onClick={() => activate(scheme)}>فعال‌سازی</Button>
                  </div>
                )}
              </div>

              <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 border-t border-gray-50 pt-3 text-xs sm:grid-cols-4">
                <Fact label="وزن عمومی" value={`${fa1(scheme.general_section_weight * 100)}٪`} />
                <Fact
                  label="وزن تخصصی"
                  value={`${fa1(scheme.specialized_section_weight * 100)}٪`}
                />
                <Fact
                  label="شواهد اجباری برای"
                  value={
                    scheme.evidence_required_scores.length
                      ? scheme.evidence_required_scores.map(faInt).join("، ")
                      : "هیچ امتیازی"
                  }
                />
                <Fact
                  label="طول شواهد"
                  value={`${faInt(scheme.evidence_min_words)} تا ${faInt(scheme.evidence_max_words)} کلمه`}
                />
              </dl>

              <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-gray-500">
                {scheme.thresholds.map((band, i) => {
                  const from = i === 0 ? 0 : scheme.thresholds[i - 1]!.upper_exclusive;
                  return (
                    <li key={band.label}>
                      <span className="tabular-nums">
                        {faInt(from)}–{faInt(Math.min(100, band.upper_exclusive))}
                      </span>{" "}
                      ⇐ {band.label}
                    </li>
                  );
                })}
              </ul>
            </Card>
          ))}
          {schemes.length === 0 && (
            <Card>
              <EmptyState>هنوز طرحی ثبت نشده است.</EmptyState>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-gray-400">{label}</dt>
      <dd className="mt-0.5 font-medium tabular-nums text-gray-800">{value}</dd>
    </div>
  );
}

function SchemeEditor({
  initial,
  onClose,
  onCreated,
}: {
  initial: SchemeForm;
  onClose: () => void;
  onCreated: () => void;
}) {
  const { showError, showSuccess } = useToast();
  const [form, setForm] = useState<SchemeForm>(initial);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);

  function patch(next: Partial<SchemeForm>) {
    setForm((prev) => ({ ...prev, ...next }));
    // هر تغییر، پیش‌نمایش را باطل می‌کند — وگرنه HR ممکن است نتیجهٔ یک تنظیم را
    // ببیند و تنظیم دیگری را بسازد.
    setPreview(null);
  }

  /** وزن دو بخش همیشه باید ۱ شود؛ حرکت‌دادن یکی، دیگری را می‌برد. */
  function setGeneralWeight(value: number) {
    const general = Math.min(1, Math.max(0, Math.round(value * 100) / 100));
    patch({
      general_section_weight: general,
      specialized_section_weight: Math.round((1 - general) * 100) / 100,
    });
  }

  function toggleRequiredScore(score: number) {
    const current = new Set(form.evidence_required_scores);
    if (current.has(score)) current.delete(score);
    else current.add(score);
    patch({ evidence_required_scores: [...current].sort((a, b) => a - b) });
  }

  function patchBand(index: number, next: Partial<ThresholdBand>) {
    patch({
      thresholds: form.thresholds.map((band, i) => (i === index ? { ...band, ...next } : band)),
    });
  }

  async function runPreview() {
    setBusy(true);
    try {
      const { data } = await apiClient.post<Preview>("/scoring-schemes/preview", form);
      setPreview(data);
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function create() {
    setBusy(true);
    try {
      await apiClient.post("/scoring-schemes", form);
      showSuccess("پیش‌نویس ساخته شد — برای فعال‌سازی، کاربر دیگری از منابع انسانی باید تأییدش کند");
      onCreated();
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="ساخت نسخهٔ جدید طرح نمره‌دهی"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            انصراف
          </Button>
          {preview === null ? (
            <Button onClick={runPreview} disabled={busy}>
              {busy ? "در حال محاسبه…" : "بررسی اثر روی پرونده‌های گذشته"}
            </Button>
          ) : (
            <Button onClick={create} disabled={busy}>
              {busy ? "در حال ساخت…" : "ساخت پیش‌نویس"}
            </Button>
          )}
        </>
      }
    >
      <div className="space-y-5 py-1">
        <label className="block text-xs font-medium text-gray-600">
          نام نسخه
          <input
            className={`${inputClass} mt-1`}
            value={form.name}
            onChange={(e) => patch({ name: e.target.value })}
          />
        </label>

        {/* ── وزن بخش‌ها ── */}
        <div>
          <p className="mb-2 text-xs font-medium text-gray-600">وزن بخش‌ها</p>
          <div className="rounded-2xl border border-gray-100 p-4">
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={Math.round(form.general_section_weight * 100)}
              onChange={(e) => setGeneralWeight(Number(e.target.value) / 100)}
              className="w-full accent-pulse-600"
              aria-label="وزن بخش عمومی"
            />
            <div className="mt-2 flex justify-between text-xs">
              <span className="text-gray-700">
                عمومی{" "}
                <span className="font-bold tabular-nums">
                  {faInt(Math.round(form.general_section_weight * 100))}٪
                </span>
              </span>
              <span className="text-gray-700">
                تخصصی{" "}
                <span className="font-bold tabular-nums">
                  {faInt(Math.round(form.specialized_section_weight * 100))}٪
                </span>
              </span>
            </div>
            {/* یک اسلایدر به‌جای دو عدد: مجموع باید دقیقاً ۱ باشد، و دو ورودی
                جدا یعنی کاربر می‌تواند حالتی بسازد که سرور ردش کند. */}
            <p className="mt-2 text-[11px] text-gray-400">
              مجموع همیشه ۱۰۰٪ است؛ جابه‌جا کردن یکی، دیگری را تنظیم می‌کند.
            </p>
          </div>
        </div>

        {/* ── قاعدهٔ شواهد ── */}
        <div>
          <p className="mb-2 text-xs font-medium text-gray-600">شواهد عینی اجباری برای امتیاز</p>
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map((score) => {
              const on = form.evidence_required_scores.includes(score);
              return (
                <button
                  key={score}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggleRequiredScore(score)}
                  className={`h-10 flex-1 rounded-xl border-2 text-sm font-bold tabular-nums transition-colors ${
                    on
                      ? "border-pulse-600 bg-pulse-600 text-white"
                      : "border-gray-200 bg-white text-gray-500"
                  }`}
                >
                  {faInt(score)}
                </button>
              );
            })}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <label className="text-xs font-medium text-gray-600">
              حداقل کلمه
              <input
                type="number"
                min={0}
                className={`${inputClass} mt-1`}
                value={form.evidence_min_words}
                onChange={(e) => patch({ evidence_min_words: Number(e.target.value) })}
              />
            </label>
            <label className="text-xs font-medium text-gray-600">
              حداکثر کلمه
              <input
                type="number"
                min={1}
                className={`${inputClass} mt-1`}
                value={form.evidence_max_words}
                onChange={(e) => patch({ evidence_max_words: Number(e.target.value) })}
              />
            </label>
          </div>
        </div>

        {/* ── جدول نتیجه ── */}
        <div>
          <p className="mb-2 text-xs font-medium text-gray-600">
            جدول نتیجه — «تا این درصد ⇐ این نتیجه»
          </p>
          <ul className="space-y-2">
            {form.thresholds.map((band, index) => (
              <li key={index} className="flex min-w-0 items-center gap-2">
                <span className="w-8 shrink-0 text-[11px] tabular-nums text-gray-400">
                  {faInt(index === 0 ? 0 : form.thresholds[index - 1]!.upper_exclusive)}–
                </span>
                <input
                  type="number"
                  className={`${fieldClass} w-20 shrink-0`}
                  value={band.upper_exclusive}
                  onChange={(e) =>
                    patchBand(index, { upper_exclusive: Number(e.target.value) })
                  }
                  aria-label={`سقف پلهٔ ${faInt(index + 1)}`}
                />
                <input
                  className={`${fieldClass} min-w-0 flex-1`}
                  value={band.label}
                  onChange={(e) => patchBand(index, { label: e.target.value })}
                  aria-label={`نتیجهٔ پلهٔ ${faInt(index + 1)}`}
                />
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-gray-400">
            سقف آخرین پله باید بالای ۱۰۰ باشد تا امتیاز کامل هم نتیجه بگیرد.
          </p>
        </div>

        {/* ── پیش‌نمایش: دلیل وجود این صفحه ── */}
        {preview !== null && <PreviewPanel preview={preview} />}
      </div>
    </Modal>
  );
}

function PreviewPanel({ preview }: { preview: Preview }) {
  return (
    <div className="rounded-2xl border border-gray-100">
      <div className="border-b border-gray-100 px-4 py-3">
        <p className="text-sm font-bold text-gray-900">
          {preview.changed_count === 0 ? (
            <span className="text-green-700">
              هیچ پروندهٔ گذشته‌ای نتیجه‌اش عوض نمی‌شود
            </span>
          ) : (
            <span className="text-amber-800">
              {faInt(preview.changed_count)} پرونده از {faInt(preview.sample_size)} پروندهٔ اخیر
              نتیجه‌شان عوض می‌شود
            </span>
          )}
        </p>
        <p className="mt-1 text-[11px] text-gray-500">
          این محاسبه‌ای فرضی است؛ هیچ پرونده‌ای تغییر نمی‌کند. پرونده‌های موجود همیشه با
          همان نسخه‌ای که زیرش باز شده‌اند حساب می‌شوند.
        </p>
      </div>

      {preview.transitions.length > 0 && (
        <ul className="divide-y divide-gray-50">
          {preview.transitions.map((t) => (
            <li key={`${t.from}→${t.to}`} className="flex items-center gap-2 px-4 py-2 text-xs">
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-gray-600">{t.from}</span>
              <span aria-hidden className="text-gray-300">
                ←
              </span>
              <span className="rounded-full bg-amber-50 px-2 py-0.5 text-amber-800">{t.to}</span>
              <span className="ms-auto shrink-0 font-bold tabular-nums text-gray-700">
                {faInt(t.count)} نفر
              </span>
            </li>
          ))}
        </ul>
      )}

      {preview.cases.length > 0 && (
        <div className="max-h-48 overflow-y-auto border-t border-gray-100">
          <table className="w-full text-[11px]">
            <thead className="sticky top-0 bg-white text-gray-400">
              <tr>
                <th className="px-4 py-2 text-right font-medium">پرونده</th>
                <th className="px-2 py-2 text-right font-medium">واحد</th>
                <th className="px-2 py-2 text-right font-medium">امتیاز فعلی</th>
                <th className="px-4 py-2 text-right font-medium">امتیاز پیشنهادی</th>
              </tr>
            </thead>
            <tbody>
              {preview.cases.map((c) => (
                <tr key={c.evaluation_code} className="border-t border-gray-50">
                  <td className="px-4 py-1.5 text-gray-700">{c.evaluation_code}</td>
                  <td className="px-2 py-1.5 text-gray-500">{c.org_unit}</td>
                  <td className="px-2 py-1.5 tabular-nums text-gray-500">
                    {fa1(c.current_final_pct)}
                  </td>
                  <td className="px-4 py-1.5 font-medium tabular-nums text-gray-900">
                    {fa1(c.proposed_final_pct)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
