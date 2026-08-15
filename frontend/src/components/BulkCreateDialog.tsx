/** ساخت دسته‌ای ارزیابی برای یک کوهورت (P2-03).
 *
 * دو مرحله، و مرحلهٔ اول اختیاری نیست: اول پیش‌نمایش که دقیقاً می‌گوید برای چه
 * کسانی ساخته می‌شود و چه کسانی رد می‌شوند و چرا، بعد اجرا. باز کردن یک چرخه
 * برای دویست نفر کاری است که برگرداندنش دستی و پرزحمت است، پس باید بشود پیش از
 * انجامش دیدش — نه بعدش.
 *
 * ترتیب نمایش نتایج هم تصمیم است: ردیف‌های «مسدود» بالا می‌آیند، چون فقط آن‌ها
 * کاری از HR می‌خواهند. اگر همه با هم مرتب می‌شدند، در فهرست دویست‌نفره سه ردیفی
 * که واقعاً مهم‌اند گم می‌شدند.
 */
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../api/client";
import { useOrgUnits } from "../api/queries";
import { Button } from "../ui/Button";
import { FilterSelect } from "../ui/Card";
import { Modal } from "../ui/Modal";
import { JalaliDatePicker } from "../ui/JalaliDatePicker";
import { useToast } from "./Toast";

interface BulkPersonResult {
  personnel_id: number;
  full_name: string;
  org_unit: string;
  outcome: string;
  reason: string;
  evaluation_id: number | null;
  evaluation_code: string | null;
}

interface BulkCreateResult {
  dry_run: boolean;
  total: number;
  counts: Record<string, number>;
  results: BulkPersonResult[];
}

interface CohortForm {
  org_unit: string;
  only_managers: "" | "true" | "false";
  contract_ends_before: string;
}

const emptyCohort: CohortForm = { org_unit: "", only_managers: "", contract_ends_before: "" };

const inputClass =
  "w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white";

const faInt = (value: number) => value.toLocaleString("fa-IR");

/** «مسدود» یعنی کاری لازم بود و نشد — کسی باید کاری بکند. «رد شد» یعنی کاری
 *  لازم نبود. این دو نباید یک‌شکل دیده شوند، وگرنه HR یا نگران چیزی می‌شود که
 *  مشکل نیست، یا از کنار چیزی که هست رد می‌شود. */
export function isBlocked(outcome: string): boolean {
  return outcome.startsWith("blocked_");
}

/** مسدودها اول، بعد ساخته‌شده‌ها، بعد رد‌شده‌ها. */
export function sortResults(results: BulkPersonResult[]): BulkPersonResult[] {
  const rank = (outcome: string) => (isBlocked(outcome) ? 0 : outcome === "created" ? 1 : 2);
  return [...results].sort(
    (a, b) => rank(a.outcome) - rank(b.outcome) || a.full_name.localeCompare(b.full_name, "fa"),
  );
}

function toPayload(cohort: CohortForm) {
  return {
    org_unit: cohort.org_unit || undefined,
    only_managers: cohort.only_managers === "" ? undefined : cohort.only_managers === "true",
    contract_ends_before: cohort.contract_ends_before || undefined,
  };
}

export function BulkCreateDialog({ onClose }: { onClose: () => void }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const { data: orgUnits = [] } = useOrgUnits(true);

  const [cohort, setCohort] = useState<CohortForm>(emptyCohort);
  const [preview, setPreview] = useState<BulkCreateResult | null>(null);
  const [busy, setBusy] = useState(false);

  function patch(next: Partial<CohortForm>) {
    setCohort((prev) => ({ ...prev, ...next }));
    // هر تغییر فیلتر، پیش‌نمایش را باطل می‌کند. نگه‌داشتنش یعنی HR ممکن است
    // نتیجهٔ یک کوهورت را ببیند و کوهورت دیگری را اجرا کند.
    setPreview(null);
  }

  async function runPreview() {
    setBusy(true);
    try {
      const { data } = await apiClient.post<BulkCreateResult>(
        "/periods/bulk-create/preview",
        toPayload(cohort),
      );
      setPreview(data);
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function runExecute() {
    setBusy(true);
    try {
      const { data } = await apiClient.post<BulkCreateResult>(
        "/periods/bulk-create",
        toPayload(cohort),
      );
      const created = data.counts.created ?? 0;
      await queryClient.invalidateQueries({ queryKey: ["periods"] });
      await queryClient.invalidateQueries({ queryKey: ["evaluations"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      showSuccess(
        created > 0
          ? `${faInt(created)} ارزیابی جدید ساخته شد`
          : "چیزی برای ساختن نبود؛ جزئیات در فهرست زیر است",
      );
      setPreview(data);
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const created = preview?.counts.created ?? 0;
  const blockedCount = preview
    ? Object.entries(preview.counts)
        .filter(([key]) => isBlocked(key))
        .reduce((sum, [, value]) => sum + value, 0)
    : 0;
  const alreadyDone = preview !== null && !preview.dry_run;

  return (
    <Modal
      title="ساخت دسته‌ای ارزیابی"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {alreadyDone ? "بستن" : "انصراف"}
          </Button>
          {!alreadyDone &&
            (preview === null ? (
              <Button onClick={runPreview} disabled={busy}>
                {busy ? "در حال بررسی…" : "بررسی پیش از ساخت"}
              </Button>
            ) : (
              <Button onClick={runExecute} disabled={busy || created === 0}>
                {busy
                  ? "در حال ساخت…"
                  : created === 0
                    ? "چیزی برای ساختن نیست"
                    : `ساخت ${faInt(created)} ارزیابی`}
              </Button>
            ))}
        </>
      }
    >
      <div className="space-y-4 py-1">
        <p className="text-sm text-gray-600">
          کوهورت را مشخص کنید. هر فیلتر خالی یعنی «همه». پیش از ساخت، فهرست کاملِ
          «چه کسی و چرا» را می‌بینید.
        </p>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            واحد سازمانی
            <FilterSelect
              aria-label="واحد سازمانی کوهورت"
              value={cohort.org_unit}
              onChange={(v) => patch({ org_unit: v })}
            >
              <option value="">همهٔ واحدها</option>
              {orgUnits.map((unit) => (
                <option key={unit} value={unit}>
                  {unit}
                </option>
              ))}
            </FilterSelect>
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            نوع پرسنل
            <FilterSelect
              aria-label="نوع پرسنل کوهورت"
              value={cohort.only_managers}
              onChange={(v) => patch({ only_managers: v as CohortForm["only_managers"] })}
            >
              <option value="">مدیران و غیرمدیران</option>
              <option value="false">فقط غیرمدیران</option>
              <option value="true">فقط مدیران</option>
            </FilterSelect>
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            پایان قرارداد تا
            <JalaliDatePicker
              className={inputClass}
              value={cohort.contract_ends_before}
              onChange={(iso) => patch({ contract_ends_before: iso })}
            />
          </label>
        </div>

        {preview !== null && (
          <div className="rounded-2xl border border-gray-100">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-b border-gray-100 px-4 py-3 text-sm">
              <span className="font-semibold text-gray-900">
                {faInt(preview.total)} نفر در این کوهورت
              </span>
              <span className="text-green-700">
                {faInt(created)} {preview.dry_run ? "ساخته می‌شود" : "ساخته شد"}
              </span>
              {(preview.counts.skipped_already_open ?? 0) > 0 && (
                <span className="text-gray-500">
                  {faInt(preview.counts.skipped_already_open ?? 0)} پروندهٔ باز دارد
                </span>
              )}
              {blockedCount > 0 && (
                <span className="font-medium text-amber-700">
                  {faInt(blockedCount)} نیازمند اقدام شما
                </span>
              )}
            </div>

            {preview.results.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-gray-400">
                هیچ پرسنلی با این فیلترها پیدا نشد.
              </p>
            ) : (
              <ul className="max-h-72 divide-y divide-gray-50 overflow-y-auto">
                {sortResults(preview.results).map((row) => (
                  <li
                    key={row.personnel_id}
                    className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-sm"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-gray-800">{row.full_name}</span>
                      <span className="text-[11px] text-gray-400">{row.org_unit}</span>
                    </span>
                    <span
                      className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        isBlocked(row.outcome)
                          ? "bg-amber-50 text-amber-800"
                          : row.outcome === "created"
                            ? "bg-green-50 text-green-700"
                            : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {row.reason}
                      {row.evaluation_code && ` · ${row.evaluation_code}`}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {preview !== null && preview.dry_run && blockedCount > 0 && (
          <p className="rounded-xl bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800">
            {faInt(blockedCount)} نفر ارزیابی نمی‌گیرند. می‌توانید همین حالا ادامه دهید و
            بعد از رفع مشکلشان دوباره اجرا کنید — اجرای دوباره برای کسانی که پرونده
            گرفته‌اند پروندهٔ دوم نمی‌سازد.
          </p>
        )}
      </div>
    </Modal>
  );
}
