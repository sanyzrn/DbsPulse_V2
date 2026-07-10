import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../../api/client";
import {
  useDebouncedValue,
  usePersonnelList,
  useUsersList,
} from "../../api/queries";
import { EmployeeProfileModal } from "../../components/EmployeeProfileModal";
import { ExcelExportButton } from "../../components/ExcelExportButton";
import { PaginationControls } from "../../components/PaginationControls";
import { useToast } from "../../components/Toast";
import { Button } from "../../ui/Button";
import { PageHeader } from "../../ui/Card";
import { Modal } from "../../ui/Modal";
import { Table } from "../../ui/Table";
import { JalaliDatePicker } from "../../ui/JalaliDatePicker";
import type { AppUser, Personnel } from "../../types";

const PAGE_SIZE = 10;

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

/** کلاس استاندارد فیلد ورودی مدرن. */
const inputClass =
  "w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white";

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
  const [error, setError] = useState<string | null>(null);
  const [profilePerson, setProfilePerson] = useState<Personnel | null>(null);
  const [editingPersonnel, setEditingPersonnel] = useState<Personnel | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const debouncedSearch = useDebouncedValue(search);

  const { data, error: loadError } = usePersonnelList({
    q: debouncedSearch,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });
  const { data: usersPage } = useUsersList({ limit: 1000 });
  const users = usersPage?.items ?? [];

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

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
      const { data: created } = await apiClient.post<Personnel>("/personnel", form);
      await apiClient.put(`/personnel/${created.id}/access`, accessPayload(access, form.is_manager));
      setForm(emptyForm);
      setAccess(emptyAccess);
      await queryClient.invalidateQueries({ queryKey: ["personnel"] });
      showSuccess("پرسنل با موفقیت افزوده شد");
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
        <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
          <h2 className="mb-4 text-base font-bold text-gray-900">افزودن پرسنل</h2>
          <form
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
            <Button type="submit" className="mt-4">
              افزودن
            </Button>
          </form>
        </div>

        <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-bold text-gray-900">فهرست پرسنل</h2>
            <div className="flex flex-wrap items-center gap-2">
              <ExcelExportButton
                url="/personnel/export.xlsx"
                filename="personnel.xlsx"
                params={{ q: debouncedSearch || undefined }}
              />
              <div className="relative">
                <svg viewBox="0 0 20 20" className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                  <circle cx="9" cy="9" r="6" />
                  <path d="M14 14l3 3" />
                </svg>
                <input
                  className="w-full rounded-xl border border-gray-200 bg-gray-100 py-1.5 pr-9 pl-3 text-sm text-gray-700 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white sm:w-80"
                  placeholder="جست‌وجو (نام، کد پرسنلی، عنوان شغلی، واحد)…"
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setPage(0);
                  }}
                />
              </div>
            </div>
          </div>
          {loadError != null && (
            <p className="mb-2 text-sm text-red-600">{extractErrorMessage(loadError)}</p>
          )}
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
                <span key="job" className="text-gray-600">
                  {p.job_title}
                  {p.is_manager && (
                    <span className="mr-1.5 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700">
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
            pageSize={PAGE_SIZE}
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
      await apiClient.patch(`/personnel/${personnel.id}`, form);
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
