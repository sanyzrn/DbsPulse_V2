/** ورود دسته‌ای پرسنل از Excel — سه گام: فایل، پیش‌نمایش، نتیجه.
 *
 * گامِ پیش‌نمایش حذف‌شدنی نیست. «۲۰۰ ردیف وارد شد و ۳تایش اشتباه بود» را نمی‌شود
 * به‌سادگی برگرداند، پس کاربر اول می‌بیند دقیقاً چه اتفاقی *قرار است* بیفتد —
 * کدام ردیف، کدام خطا — و بعد تصمیم می‌گیرد. سرور هنگام درج دوباره از صفر
 * اعتبارسنجی می‌کند، پس پیش‌نمایش راهنماست نه مجوز.
 */
import { useRef, useState } from "react";
import { apiClient, extractErrorMessage } from "../api/client";
import { useToast } from "./Toast";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";

interface RowIssue {
  row_number: number;
  personnel_code: string;
  full_name: string;
  username: string | null;
  errors: string[];
}

interface Preview {
  total_rows: number;
  valid_count: number;
  invalid_count: number;
  accounts_to_create: number;
  rows: RowIssue[];
  file_errors: string[];
}

interface CreatedAccount {
  personnel_code: string;
  full_name: string;
  username: string;
  temporary_password: string;
}

interface ImportResult {
  created_personnel: number;
  created_accounts: number;
  created_chains: number;
  skipped_rows: number;
  accounts: CreatedAccount[];
}

const faNum = (value: number) => value.toLocaleString("fa-IR");

/** یک سلول CSV. رمز تولیدی می‌تواند نویسه‌هایی مثل «"» داشته باشد و نام هم ممکن
 *  است ویرگول داشته باشد؛ بدون نقل‌قول‌گذاری، ستون‌ها جابه‌جا می‌شدند و رمزِ
 *  نمایش‌داده‌شده با رمزِ فایل فرق می‌کرد. */
function csvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

/** رمزهای موقت را به‌صورت CSV می‌دهد تا HR راهی برای توزیعشان داشته باشد.
 *  فقط همین یک بار در دسترس‌اند — سرور رمز را نگه نمی‌دارد، فقط هشش را. */
export function buildAccountsCsv(accounts: CreatedAccount[]): string {
  const header = ["کد پرسنلی", "نام", "نام کاربری", "رمز موقت"].map(csvCell).join(",");
  const body = accounts
    .map((a) =>
      [a.personnel_code, a.full_name, a.username, a.temporary_password].map(csvCell).join(","),
    )
    .join("\r\n");
  // BOM تا اکسل فارسی را درست باز کند
  return `﻿${header}\r\n${body}`;
}

function downloadAccounts(accounts: CreatedAccount[]) {
  const blob = new Blob([buildAccountsCsv(accounts)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "new-accounts.csv";
  link.click();
  URL.revokeObjectURL(url);
}

export function PersonnelImportDialog({
  onClose,
  onImported,
}: {
  onClose: () => void;
  onImported: () => void;
}) {
  const { showError, showSuccess } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function send<T>(path: string, chosen: File): Promise<T> {
    const form = new FormData();
    form.append("file", chosen);
    const { data } = await apiClient.post<T>(path, form);
    return data;
  }

  async function choose(chosen: File | null) {
    setFile(chosen);
    setPreview(null);
    setResult(null);
    if (!chosen) return;
    setBusy(true);
    try {
      setPreview(await send<Preview>("/personnel/import/preview", chosen));
    } catch (err) {
      showError(extractErrorMessage(err));
      setFile(null);
    } finally {
      setBusy(false);
    }
  }

  async function commit() {
    if (!file) return;
    setBusy(true);
    try {
      const data = await send<ImportResult>("/personnel/import", file);
      setResult(data);
      showSuccess(
        `${faNum(data.created_personnel)} پرسنل ثبت شد` +
          (data.created_chains < data.created_personnel
            ? ` — ${faNum(data.created_personnel - data.created_chains)} نفر هنوز زنجیرهٔ ارزیابی ندارند`
            : "")
      );
      onImported();
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function downloadTemplate() {
    try {
      const { data } = await apiClient.get("/personnel/import-template.xlsx", {
        responseType: "blob",
      });
      const url = URL.createObjectURL(data as Blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "personnel-import-template.xlsx";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      showError(extractErrorMessage(err));
    }
  }

  const invalidRows = preview?.rows.filter((r) => r.errors.length > 0) ?? [];

  return (
    <Modal
      title="ورود دسته‌ای پرسنل از Excel"
      onClose={onClose}
      size="lg"
      footer={
        result ? (
          <Button onClick={onClose}>بستن</Button>
        ) : (
          <div className="flex gap-2">
            <Button
              onClick={commit}
              loading={busy}
              disabled={!preview || preview.valid_count === 0 || busy}
            >
              {preview
                ? `ثبت ${faNum(preview.valid_count)} ردیف معتبر`
                : "ثبت"}
            </Button>
            <Button variant="secondary" onClick={onClose}>
              انصراف
            </Button>
          </div>
        )
      }
    >
      <div className="space-y-4 py-2">
        {result ? (
          <ResultView result={result} />
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-gray-100 bg-gray-50 px-4 py-3">
              <p className="text-xs text-gray-600">
                ستون‌های فایل باید دقیقاً مثل خروجی Excel پرسنل باشد. ستون «محل» یکی از
                «دفتر مرکزی»، «کارخانه» یا «مدرپ‌ها» را می‌گیرد و خالی‌گذاشتنش هم درست است. ستون «نام کاربری»
                اختیاری است؛ هر ردیفی که پرش شود، حساب کاربری هم برایش ساخته می‌شود.
              </p>
              <button
                type="button"
                onClick={downloadTemplate}
                className="shrink-0 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50"
              >
                دریافت فایل نمونه
              </button>
            </div>

            <input
              ref={inputRef}
              type="file"
              accept=".xlsx,.xlsm"
              aria-label="انتخاب فایل Excel"
              onChange={(e) => choose(e.target.files?.[0] ?? null)}
              className="w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-700 file:me-3 file:rounded-lg file:border-0 file:bg-white file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-gray-700"
            />

            {busy && !preview && <p className="text-sm text-gray-500">در حال بررسی فایل…</p>}

            {preview?.file_errors.length ? (
              <ul className="space-y-1 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
                {preview.file_errors.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            ) : null}

            {preview && !preview.file_errors.length && (
              <>
                <div className="grid grid-cols-3 gap-3 text-center">
                  <Stat label="آمادهٔ ثبت" value={preview.valid_count} tone="green" />
                  <Stat label="دارای خطا" value={preview.invalid_count} tone="red" />
                  <Stat label="حساب کاربری" value={preview.accounts_to_create} tone="gray" />
                </div>

                {invalidRows.length > 0 && (
                  <div>
                    <p className="mb-2 text-xs font-medium text-gray-500">
                      این ردیف‌ها ثبت نمی‌شوند:
                    </p>
                    <ul className="max-h-56 space-y-1.5 overflow-y-auto">
                      {invalidRows.map((row) => (
                        <li
                          key={row.row_number}
                          className="rounded-lg border border-red-100 bg-red-50/50 px-3 py-2 text-xs"
                        >
                          <span className="font-medium text-gray-700">
                            ردیف {faNum(row.row_number)}
                            {row.full_name ? ` — ${row.full_name}` : ""}
                          </span>
                          <ul className="mt-0.5 space-y-0.5 text-red-700">
                            {row.errors.map((e) => (
                              <li key={e}>• {e}</li>
                            ))}
                          </ul>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {preview.valid_count === 0 && (
                  <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    هیچ ردیف معتبری در فایل نیست؛ خطاهای بالا را اصلاح کنید و دوباره
                    بارگذاری کنید.
                  </p>
                )}
              </>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "green" | "red" | "gray";
}) {
  const tones = {
    green: "bg-green-50 text-green-700",
    red: "bg-red-50 text-red-700",
    gray: "bg-gray-100 text-gray-600",
  };
  return (
    <div className={`rounded-xl px-3 py-2 ${tones[tone]}`}>
      <p className="text-lg font-extrabold tabular-nums">{faNum(value)}</p>
      <p className="text-[11px]">{label}</p>
    </div>
  );
}

function ResultView({ result }: { result: ImportResult }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3 text-center">
        <Stat label="پرسنل ثبت‌شده" value={result.created_personnel} tone="green" />
        {/* اگر از تعداد پرسنل کمتر باشد، بقیه هنوز قابل ارزیابی نیستند — و این
            باید همان‌جا دیده شود، نه اینکه بعداً کشف شود. */}
        <Stat
          label="زنجیرهٔ ارزیابی"
          value={result.created_chains}
          tone={result.created_chains < result.created_personnel ? "red" : "green"}
        />
        <Stat label="حساب ساخته‌شده" value={result.created_accounts} tone="gray" />
        <Stat label="ردیف ردشده" value={result.skipped_rows} tone="red" />
      </div>

      {result.accounts.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4">
          <p className="text-sm font-medium text-amber-900">
            رمزهای موقت فقط همین یک بار نمایش داده می‌شوند
          </p>
          <p className="mt-1 text-xs text-amber-800">
            سامانه رمز را نگه نمی‌دارد (فقط هشِ آن را). همین حالا فایل را بگیرید؛ هر
            کاربر در نخستین ورود مجبور به تغییر رمزش می‌شود.
          </p>
          <Button className="mt-3" onClick={() => downloadAccounts(result.accounts)}>
            دریافت فایل نام کاربری و رمز
          </Button>

          <ul className="mt-3 max-h-48 space-y-1 overflow-y-auto text-xs">
            {result.accounts.map((a) => (
              <li
                key={a.username}
                className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg bg-white/70 px-3 py-1.5"
              >
                <span className="text-gray-700">{a.full_name}</span>
                <code className="font-mono text-gray-800" dir="ltr">
                  {a.username}
                </code>
                <code className="select-all font-mono text-gray-900" dir="ltr">
                  {a.temporary_password}
                </code>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
