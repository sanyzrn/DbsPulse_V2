import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../../api/client";
import {
  useDebouncedValue,
  useOrgUnits,
  usePersonnelList,
  useUsersList,
} from "../../api/queries";
import { EmployeeProfileModal } from "../../components/EmployeeProfileModal";
import { ExcelExportButton } from "../../components/ExcelExportButton";
import { PersonnelImportDialog } from "../../components/PersonnelImportDialog";
import { PaginationControls } from "../../components/PaginationControls";
import { useToast } from "../../components/Toast";
import { generatePassword } from "../../utils/password";
import { Button } from "../../ui/Button";
import { FilterSelect, PageHeader, TableSkeleton } from "../../ui/Card";
import { Modal } from "../../ui/Modal";
import { Table } from "../../ui/Table";
import { JalaliDatePicker } from "../../ui/JalaliDatePicker";
import { SEPARATION_REASON_LABELS, type AppUser, type Personnel, type SeparationReason } from "../../types";
import { SearchInput } from "../../ui/SearchInput";

/** پیش‌فرض تعداد در هر صفحه؛ کاربر می‌تواند از نوار پایین عوضش کند. */
const DEFAULT_PAGE_SIZE = 10;

const emptyForm = {
  personnel_code: "",
  full_name: "",
  job_title: "",
  is_manager: false,
  org_unit: "",
  contract_start_date: "",
  contract_end_date: "",
};

/** حالت دسترسی زنجیره ارزیابی که همراه فرم پرسنل نگه داشته می‌شود. */
type AccessDraft = {
  unit_supervisor_user_id: number | null;
  deputy_user_id: number | null;
  ceo_user_id: number | null;
};

const emptyAccess: AccessDraft = {
  unit_supervisor_user_id: null,
  deputy_user_id: null,
  ceo_user_id: null,
};

/** حساب کاربری «کارمند» که هم‌زمان با پرسنل ساخته می‌شود.
 *
 * پیش‌فرض روشن است چون حالت رایج همین است، ولی قابل خاموش‌کردن: هر پرسنلی لازم
 * نیست حساب داشته باشد، و حسابِ خفته با رمز موقتِ تغییرنکرده خودش یک بدهی امنیتی است. */
type AccountDraft = { enabled: boolean; username: string; password: string };

const emptyAccount: AccountDraft = { enabled: true, username: "", password: "" };

/** نام کاربری پیشنهادی از روی کد پرسنلی — یکتا به‌طور طبیعی، و بدون حدس‌زدنِ
 *  آوانگاری نام فارسی که هم شکننده است و هم تکراری‌پذیر. */
function suggestUsername(personnelCode: string): string {
  return personnelCode.trim().toLowerCase().replace(/[^a-z0-9_.-]/g, "-").replace(/^-+|-+$/g, "");
}

/** رمز موقتِ قوی. HR باید آن را به فرد بدهد، پس باید بتواند ببیندش. */

/** کلاس استاندارد فیلد ورودی مدرن. */
const inputClass =
  "w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white";

/** حساب کاربری کارمند، داخل همان فرم ثبت پرسنل — تا «دسترسی دادن به فرد» یک
 * مرحلهٔ جدا و فراموش‌شدنی نباشد. */
function AccountFields({
  personnelCode,
  account,
  setAccount,
}: {
  personnelCode: string;
  account: AccountDraft;
  setAccount: (a: AccountDraft) => void;
}) {
  // تا وقتی HR دستی چیزی ننوشته، نام کاربری از کد پرسنلی پیروی می‌کند
  const [usernameTouched, setUsernameTouched] = useState(false);
  const username = usernameTouched ? account.username : suggestUsername(personnelCode);

  return (
    <>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={account.enabled}
          onChange={(e) => setAccount({ ...account, enabled: e.target.checked })}
          className="h-4 w-4 cursor-pointer rounded border-gray-300 text-pulse-500 focus:ring-gray-400"
        />
        <span className="font-semibold text-gray-800">ساخت حساب کاربری برای این فرد</span>
      </label>
      <p className="mt-1 text-xs text-gray-500">
        تا وقتی حساب نداشته باشد، نمی‌تواند کارنامهٔ خودش را ببیند. اگر این فرد اصلاً با
        سامانه کار نمی‌کند، تیک را بردارید.
      </p>

      {account.enabled && (
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium text-gray-700">نام کاربری</span>
            <input
              className={inputClass}
              value={username}
              onChange={(e) => {
                setUsernameTouched(true);
                setAccount({ ...account, username: e.target.value });
              }}
              placeholder="مثلاً p-1004"
              dir="ltr"
            />
            <span className="mt-1 block text-xs text-gray-400">
              حروف انگلیسی، عدد، نقطه، خط تیره و زیرخط
            </span>
          </label>

          <label className="block text-sm">
            <span className="mb-1.5 block font-medium text-gray-700">رمز عبور موقت</span>
            <div className="flex gap-2">
              <input
                className={inputClass}
                value={account.password}
                onChange={(e) => setAccount({ ...account, username: username, password: e.target.value })}
                placeholder="حداقل ۱۰ نویسه"
                dir="ltr"
              />
              <button
                type="button"
                onClick={() =>
                  setAccount({ ...account, username, password: generatePassword() })
                }
                className="whitespace-nowrap rounded-xl border border-gray-300 bg-white px-3 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100"
              >
                تولید
              </button>
            </div>
            <span className="mt-1 block text-xs text-gray-400">
              همین رمز را به فرد بدهید؛ در اولین ورود مجبور به تغییرش می‌شود.
            </span>
          </label>
        </div>
      )}
    </>
  );
}

/** فیلدهای دسترسی زنجیره ارزیابی (مسئول واحد/معاونت/مدیرعامل) که هم در فرم افزودن
 * و هم در مودال ویرایش پرسنل استفاده می‌شوند؛ دسترسی جزئی از ثبت پرسنل است نه یک
 * مرحلهٔ جدا. برای فرد «مدیر»، مسئول واحد غیرفعال می‌شود (ارزیابی مستقیم توسط معاونت). */
function AccessFields({
  users,
  isManager,
  access,
  setAccess,
}: {
  users: AppUser[];
  isManager: boolean;
  access: AccessDraft;
  setAccess: (next: AccessDraft) => void;
}) {
  const supervisors = users.filter((u) => u.role === "unit_supervisor");
  const deputies = users.filter((u) => u.role === "deputy");
  const ceos = users.filter((u) => u.role === "ceo");

  return (
    <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
      <label className="flex flex-col gap-1 text-xs font-medium text-gray-600 sm:col-span-2">
        دسترسی ارزیابی — مسئول واحد
        <select
          disabled={isManager}
          className={`${inputClass} disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400`}
          value={access.unit_supervisor_user_id ?? ""}
          onChange={(e) =>
            setAccess({
              ...access,
              unit_supervisor_user_id: e.target.value ? Number(e.target.value) : null,
            })
          }
        >
          <option value="">— انتخاب کنید —</option>
          {supervisors.map((u) => (
            <option key={u.id} value={u.id}>
              {u.username}
            </option>
          ))}
        </select>
      </label>
      {isManager && (
        <p className="-mt-1 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700 sm:col-span-2">
          چون این فرد به‌عنوان «مدیر» علامت خورده است، دسترسی مسئول واحد غیرفعال است؛ این فرد مستقیماً
          توسط معاونت ارزیابی می‌شود.
        </p>
      )}
      <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
        معاونت
        <select
          required
          className={inputClass}
          value={access.deputy_user_id ?? ""}
          onChange={(e) =>
            setAccess({ ...access, deputy_user_id: e.target.value ? Number(e.target.value) : null })
          }
        >
          <option value="">— انتخاب کنید —</option>
          {deputies.map((u) => (
            <option key={u.id} value={u.id}>
              {u.username}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
        مدیرعامل
        <select
          required
          className={inputClass}
          value={access.ceo_user_id ?? ""}
          onChange={(e) =>
            setAccess({ ...access, ceo_user_id: e.target.value ? Number(e.target.value) : null })
          }
        >
          <option value="">— انتخاب کنید —</option>
          {ceos.map((u) => (
            <option key={u.id} value={u.id}>
              {u.username}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

/** payload دسترسی را از draft می‌سازد؛ برای فرد «مدیر» مسئول واحد همیشه null است. */
function accessPayload(access: AccessDraft, isManager: boolean) {
  return {
    unit_supervisor_user_id: isManager ? null : access.unit_supervisor_user_id,
    deputy_user_id: access.deputy_user_id,
    ceo_user_id: access.ceo_user_id,
  };
}

export function PersonnelPage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState(emptyForm);
  const [access, setAccess] = useState<AccessDraft>(emptyAccess);
  const [account, setAccount] = useState<AccountDraft>(emptyAccount);
  const [error, setError] = useState<string | null>(null);
  const [showAddPersonnel, setShowAddPersonnel] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [profilePerson, setProfilePerson] = useState<Personnel | null>(null);
  const [editingPersonnel, setEditingPersonnel] = useState<Personnel | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"" | "active" | "inactive">("");
  const [orgUnitFilter, setOrgUnitFilter] = useState("");
  const [managerFilter, setManagerFilter] = useState<"" | "true" | "false">("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const debouncedSearch = useDebouncedValue(search);

  const listParams = {
    q: debouncedSearch,
    status: statusFilter || undefined,
    org_unit: orgUnitFilter || undefined,
    is_manager: managerFilter === "" ? undefined : managerFilter === "true",
  } as const;

  const { data, error: loadError, isPending } = usePersonnelList({
    ...listParams,
    limit: pageSize,
    offset: page * pageSize,
  });
  const { data: usersPage } = useUsersList({ limit: 1000 });
  const users = usersPage?.items ?? [];
  const { data: orgUnits = [] } = useOrgUnits(true);
  const hasActiveFilter = Boolean(search || statusFilter || orgUnitFilter || managerFilter);

  function resetFilters() {
    setSearch("");
    setStatusFilter("");
    setOrgUnitFilter("");
    setManagerFilter("");
    setPage(0);
  }

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  async function createPersonnel() {
    setError(null);
    if (access.deputy_user_id == null || access.ceo_user_id == null) {
      const message = "برای ثبت پرسنل، معاونت و مدیرعامل زنجیره ارزیابی را انتخاب کنید";
      setError(message);
      showError(message);
      return;
    }
    try {
      // ثبت پرسنل و سپس تنظیم دسترسی در همان جریان؛ دسترسی بخشی از ایجاد پرسنل است.
      // حساب کاربری در همان درخواستِ ساخت پرسنل می‌رود تا اگر نام کاربری تکراری بود،
      // هیچ‌کدام ساخته نشوند — نه پرسنلی که حسابش نیمه‌کاره مانده.
      const username = account.username.trim() || suggestUsername(form.personnel_code);
      const body = account.enabled
        ? { ...form, account: { username, password: account.password } }
        : form;
      const { data: created } = await apiClient.post<Personnel & { account_username: string | null }>(
        "/personnel",
        body,
      );
      await apiClient.put(`/personnel/${created.id}/access`, accessPayload(access, form.is_manager));
      setForm(emptyForm);
      setAccess(emptyAccess);
      setAccount(emptyAccount);
      await queryClient.invalidateQueries({ queryKey: ["personnel"] });
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      setShowAddPersonnel(false);
      showSuccess(
        created.account_username
          ? `پرسنل افزوده شد و حساب کاربری «${created.account_username}» برایش ساخته شد`
          : "پرسنل با موفقیت افزوده شد",
      );
    } catch (err) {
      const message = extractErrorMessage(err);
      setError(message);
      showError(message);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="پرسنل" subtitle="ثبت پرسنل جدید و مدیریت دسترسی زنجیره ارزیابی هر فرد" />
      <div className="space-y-4">
        {showImport && (
          <PersonnelImportDialog
            onClose={() => setShowImport(false)}
            onImported={() => queryClient.invalidateQueries({ queryKey: ["personnel"] })}
          />
        )}

        {showAddPersonnel && (
          <Modal
            title="افزودن پرسنل"
            size="lg"
            onClose={() => setShowAddPersonnel(false)}
            footer={
              <>
                <Button variant="secondary" onClick={() => setShowAddPersonnel(false)}>
                  انصراف
                </Button>
                <Button type="submit" form="add-personnel-form">
                  افزودن
                </Button>
              </>
            }
          >
          <form
            id="add-personnel-form"
            className="py-2"
            onSubmit={(e) => {
              e.preventDefault();
              createPersonnel();
            }}
          >
            <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                کد پرسنلی
                <input
                  required
                  className={inputClass}
                  value={form.personnel_code}
                  onChange={(e) => setForm({ ...form, personnel_code: e.target.value })}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                نام و نام خانوادگی
                <input
                  required
                  className={inputClass}
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                عنوان شغلی
                <input
                  required
                  className={inputClass}
                  value={form.job_title}
                  onChange={(e) => setForm({ ...form, job_title: e.target.value })}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                واحد سازمانی
                <input
                  required
                  className={inputClass}
                  value={form.org_unit}
                  onChange={(e) => setForm({ ...form, org_unit: e.target.value })}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                تاریخ شروع قرارداد
                <JalaliDatePicker
                  required
                  className={inputClass}
                  value={form.contract_start_date}
                  onChange={(iso) => setForm({ ...form, contract_start_date: iso })}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                تاریخ پایان قرارداد
                <JalaliDatePicker
                  required
                  className={inputClass}
                  value={form.contract_end_date}
                  onChange={(iso) => setForm({ ...form, contract_end_date: iso })}
                />
              </label>
              <label className="flex items-center gap-2 text-sm sm:col-span-2">
                <input
                  type="checkbox"
                  checked={form.is_manager}
                  onChange={(e) => setForm({ ...form, is_manager: e.target.checked })}
                  className="h-4 w-4 cursor-pointer rounded border-gray-300 text-pulse-500 focus:ring-gray-400"
                />
                پرسنل مدیریتی (ارزیابی مستقیم توسط معاونت، بدون مسئول واحد)
              </label>
            </div>

            {/* حساب کاربری کارمند — همان‌جا، تا مرحلهٔ جدا و فراموش‌شدنی نباشد */}
            <div className="mt-4 border-t border-gray-100 pt-4">
              <AccountFields
                personnelCode={form.personnel_code}
                account={account}
                setAccount={setAccount}
              />
            </div>

            {/* دسترسی زنجیره ارزیابی — بخشی از همان فرم ثبت پرسنل */}
            <div className="mt-4 border-t border-gray-100 pt-4">
              <h3 className="mb-3 text-sm font-semibold text-gray-800">دسترسی زنجیره ارزیابی</h3>
              <AccessFields
                users={users}
                isManager={form.is_manager}
                access={access}
                setAccess={setAccess}
              />
            </div>

            {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
          </form>
          </Modal>
        )}

        <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-3">
              <h2 className="text-base font-bold text-gray-900">فهرست پرسنل</h2>
              <Button onClick={() => { setError(null); setShowAddPersonnel(true); }}>
                + افزودن پرسنل
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <ExcelExportButton
                url="/personnel/export.xlsx"
                filename="personnel.xlsx"
                params={listParams}
              />
              <button
                type="button"
                onClick={() => setShowImport(true)}
                className="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-600 shadow-sm transition-colors hover:bg-gray-50"
              >
                <svg viewBox="0 0 20 20" className="h-4 w-4 text-pulse-600" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M10 14V4m0 0L6.5 7.5M10 4l3.5 3.5M4 15v1a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-1" />
                </svg>
                ورودی Excel
              </button>
              <SearchInput
                widthClass="sm:w-72"
                placeholder="جست‌وجو (نام، کد پرسنلی، عنوان شغلی، واحد)…"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(0);
                }}
              />
            </div>
          </div>

          {/* فیلترهای ترکیب‌پذیر فهرست پرسنل */}
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <FilterSelect
              aria-label="فیلتر واحد سازمانی"
              value={orgUnitFilter}
              onChange={(v) => {
                setOrgUnitFilter(v);
                setPage(0);
              }}
            >
              <option value="">همهٔ واحدها</option>
              {orgUnits.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </FilterSelect>
            <FilterSelect
              aria-label="فیلتر وضعیت"
              value={statusFilter}
              onChange={(v) => {
                setStatusFilter(v as "" | "active" | "inactive");
                setPage(0);
              }}
            >
              <option value="">همهٔ وضعیت‌ها</option>
              <option value="active">فعال</option>
              <option value="inactive">غیرفعال</option>
            </FilterSelect>
            <FilterSelect
              aria-label="فیلتر نوع پرسنل"
              value={managerFilter}
              onChange={(v) => {
                setManagerFilter(v as "" | "true" | "false");
                setPage(0);
              }}
            >
              <option value="">همه (مدیر و غیرمدیر)</option>
              <option value="true">فقط مدیران</option>
              <option value="false">فقط غیرمدیران</option>
            </FilterSelect>
            {hasActiveFilter && (
              <button
                onClick={resetFilters}
                className="rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-500 transition-colors hover:bg-gray-50 hover:text-gray-700"
              >
                حذف فیلترها
              </button>
            )}
          </div>

          {loadError != null && (
            <p className="mb-2 text-sm text-red-600">{extractErrorMessage(loadError)}</p>
          )}
          {isPending && <TableSkeleton rows={6} />}
          {data && (
            <Table
              bordered={false}
              headers={["نام", "عنوان شغلی", "واحد", "وضعیت", ""]}
              rowKeys={data.items.map((p) => p.id)}
              rows={data.items.map((p) => [
                <button
                  key="name"
                  onClick={() => setProfilePerson(p)}
                  className="rounded-md text-right font-medium text-pulse-700 underline decoration-pulse-200 decoration-dotted underline-offset-4 transition-colors hover:text-pulse-800"
                  title="مشاهده پروفایل"
                >
                  {p.full_name}
                </button>,
                // نشان «مدیر» با فاصلهٔ flex از عنوان جدا می‌شود، نه با حاشیهٔ
                // ۶ پیکسلی. «مدیر» عنوان شغلی نیست — یک نشانهٔ ساختاری است که
                // مسیر ارزیابی را عوض می‌کند — و چسبیده به عنوان، «کارشناس فروش
                // مدیر» خوانده می‌شد، انگار بخشی از خودِ عنوان باشد.
                <span key="job" className="flex flex-wrap items-center gap-x-2 gap-y-1 text-gray-600">
                  <span>{p.job_title}</span>
                  {p.is_manager && (
                    <span
                      className="shrink-0 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700 ring-1 ring-amber-100"
                      title="ارزیابی این فرد مستقیماً توسط معاونت انجام می‌شود"
                    >
                      مدیر
                    </span>
                  )}
                </span>,
                <span key="unit" className="text-gray-500">
                  {p.org_unit}
                </span>,
                p.status === "active" ? (
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
                <div key="actions" className="flex items-center gap-3">
                  <button
                    onClick={() => setEditingPersonnel(p)}
                    className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-sm font-medium text-pulse-600 transition-colors hover:bg-pulse-50"
                  >
                    <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M4 13.5V16h2.5l7.4-7.4-2.5-2.5L4 13.5z" />
                      <path d="M12.5 5.5l2 2" />
                    </svg>
                    ویرایش و دسترسی
                  </button>
                </div>,
              ])}
            />
          )}
          <PaginationControls
            page={page}
            totalPages={totalPages}
            totalCount={total}
            pageSize={pageSize}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setPage(0);
            }}
            onPageChange={setPage}
          />
        </div>
      </div>

      {/* پروفایل پرسنل با کلیک روی نام از همین فهرست همیشه در دسترس است؛ به هیچ
          مرحله‌ای از گردش‌کار ارزیابی (مثل بازکردن یک پرونده خاص) گره نخورده است. */}
      {profilePerson && (
        <EmployeeProfileModal
          personnelId={profilePerson.id}
          personName={profilePerson.full_name}
          onClose={() => setProfilePerson(null)}
        />
      )}

      {editingPersonnel && (
        <EditPersonnelModal
          personnel={editingPersonnel}
          users={users}
          onClose={() => setEditingPersonnel(null)}
        />
      )}
    </div>
  );
}

function EditPersonnelModal({
  personnel,
  users,
  onClose,
}: {
  personnel: Personnel;
  users: AppUser[];
  onClose: () => void;
}) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    personnel_code: personnel.personnel_code,
    full_name: personnel.full_name,
    job_title: personnel.job_title,
    is_manager: personnel.is_manager,
    org_unit: personnel.org_unit,
    contract_start_date: personnel.contract_start_date,
    contract_end_date: personnel.contract_end_date,
    status: personnel.status,
    separation_reason: personnel.separation_reason ?? ("resignation" as SeparationReason),
  });
  const [access, setAccess] = useState<AccessDraft>(emptyAccess);
  const [accessLoaded, setAccessLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setAccessLoaded(false);
    apiClient
      .get(`/personnel/${personnel.id}/access`)
      .then(({ data }) => {
        if (data) {
          setAccess({
            unit_supervisor_user_id: data.unit_supervisor_user_id ?? null,
            deputy_user_id: data.deputy_user_id ?? null,
            ceo_user_id: data.ceo_user_id ?? null,
          });
        }
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setAccessLoaded(true));
  }, [personnel.id]);

  async function save() {
    setError(null);
    if (access.deputy_user_id == null || access.ceo_user_id == null) {
      const message = "معاونت و مدیرعامل زنجیره ارزیابی الزامی هستند";
      setError(message);
      showError(message);
      return;
    }
    setSaving(true);
    try {
      // علت خروج فقط وقتی فرستاده می‌شود که واقعاً دارد خارج می‌شود. فرستادنش
      // همراه یک ویرایش معمولی، روی پروندهٔ یک نفرِ شاغل علتِ بی‌ربط می‌نشاند.
      const { separation_reason, ...rest } = form;
      await apiClient.patch(`/personnel/${personnel.id}`, {
        ...rest,
        ...(form.status === "inactive" ? { separation_reason } : {}),
      });
      await apiClient.put(
        `/personnel/${personnel.id}/access`,
        accessPayload(access, form.is_manager)
      );
      await queryClient.invalidateQueries({ queryKey: ["personnel"] });
      showSuccess("پرسنل و دسترسی به‌روزرسانی شد");
      onClose();
    } catch (err) {
      const message = extractErrorMessage(err);
      setError(message);
      showError(message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      title={`ویرایش پرسنل: ${personnel.full_name}`}
      size="lg"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            انصراف
          </Button>
          <Button onClick={save} disabled={saving || !accessLoaded}>
            ذخیره
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-3 py-2 text-sm sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          کد پرسنلی
          <input
            required
            className={inputClass}
            value={form.personnel_code}
            onChange={(e) => setForm({ ...form, personnel_code: e.target.value })}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          نام و نام خانوادگی
          <input
            required
            className={inputClass}
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          عنوان شغلی
          <input
            required
            className={inputClass}
            value={form.job_title}
            onChange={(e) => setForm({ ...form, job_title: e.target.value })}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          واحد سازمانی
          <input
            required
            className={inputClass}
            value={form.org_unit}
            onChange={(e) => setForm({ ...form, org_unit: e.target.value })}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          تاریخ شروع قرارداد
          <JalaliDatePicker
            required
            className={inputClass}
            value={form.contract_start_date}
            onChange={(iso) => setForm({ ...form, contract_start_date: iso })}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          تاریخ پایان قرارداد
          <JalaliDatePicker
            required
            className={inputClass}
            value={form.contract_end_date}
            onChange={(iso) => setForm({ ...form, contract_end_date: iso })}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          وضعیت
          <select
            className={inputClass}
            value={form.status}
            onChange={(e) => setForm({ ...form, status: e.target.value as Personnel["status"] })}
          >
            <option value="active">فعال</option>
            <option value="inactive">غیرفعال</option>
          </select>
        </label>
        {/* فقط وقتی دیده می‌شود که واقعاً خروجی در کار است. سرور هم همین را
            الزام می‌کند: غیرفعال‌کردن بدون علت رد می‌شود، چون «رفت» بدون
            «چرا رفت» در هیچ گزارشی قابل استفاده نیست. */}
        {form.status === "inactive" && (
          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            علت خروج
            <select
              className={inputClass}
              value={form.separation_reason}
              onChange={(e) =>
                setForm({ ...form, separation_reason: e.target.value as SeparationReason })
              }
            >
              {Object.entries(SEPARATION_REASON_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="flex items-center gap-2 self-end pb-2 text-sm">
          <input
            type="checkbox"
            checked={form.is_manager}
            onChange={(e) => setForm({ ...form, is_manager: e.target.checked })}
            className="h-4 w-4 cursor-pointer rounded border-gray-300 text-pulse-500 focus:ring-gray-400"
          />
          پرسنل مدیریتی
        </label>
      </div>

      {/* دسترسی زنجیره ارزیابی — در همان مودال ویرایش پرسنل */}
      <div className="mt-3 border-t border-gray-100 pt-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-800">دسترسی زنجیره ارزیابی</h3>
        {!accessLoaded ? (
          <div className="space-y-3">
            <div className="skeleton h-10" />
            <div className="skeleton h-10" />
          </div>
        ) : (
          <AccessFields
            users={users}
            isManager={form.is_manager}
            access={access}
            setAccess={setAccess}
          />
        )}
      </div>

      {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
    </Modal>
  );
}
