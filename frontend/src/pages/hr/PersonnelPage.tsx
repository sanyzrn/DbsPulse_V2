import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { apiClient, extractErrorMessage } from "../../api/client";
import {
  useDebouncedValue,
  usePersonnelList,
  useUsersList,
} from "../../api/queries";
import { EmployeeProfileModal } from "../../components/EmployeeProfileModal";
import { PaginationControls } from "../../components/PaginationControls";
import { useToast } from "../../components/Toast";
import { Button } from "../../ui/Button";
import { PageHeader } from "../../ui/Card";
import { Modal } from "../../ui/Modal";
import { JalaliDatePicker } from "../../ui/JalaliDatePicker";
import type { AppUser, EvaluationAccess, Personnel } from "../../types";

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

/** کلاس استاندارد فیلد ورودی مدرن. */
const inputClass =
  "w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition-all duration-200 focus:border-pulse-400";

export function PersonnelPage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Personnel | null>(null);
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
    try {
      await apiClient.post("/personnel", form);
      setForm(emptyForm);
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
                  className="h-4 w-4 rounded border-gray-300 text-pulse-500 focus:ring-pulse-400"
                />
                پرسنل مدیریتی (ارزیابی مستقیم توسط معاونت، بدون مسئول واحد)
              </label>
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
            <div className="relative">
              <svg viewBox="0 0 20 20" className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <circle cx="9" cy="9" r="6" />
                <path d="M14 14l3 3" />
              </svg>
              <input
                className="w-full rounded-xl border border-gray-200 bg-white py-1.5 pr-9 pl-3 text-sm text-gray-700 outline-none transition-all duration-200 focus:border-pulse-400 sm:w-80"
                placeholder="جست‌وجو (نام، کد پرسنلی، عنوان شغلی، واحد)…"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(0);
                }}
              />
            </div>
          </div>
          {loadError != null && (
            <p className="mb-2 text-sm text-red-600">{extractErrorMessage(loadError)}</p>
          )}
          {data && data.items.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gradient-to-l from-pulse-50/50 to-pulse-violet-50/50">
                    <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">نام</th>
                    <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">عنوان شغلی</th>
                    <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">واحد</th>
                    <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">وضعیت</th>
                    <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600"></th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((p, idx) => (
                    <motion.tr
                      key={p.id}
                      className="border-b border-gray-50 transition-colors last:border-0 hover:bg-pulse-50/30"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.2, delay: idx * 0.03 }}
                    >
                      <td className="px-3 py-2.5 font-medium text-gray-700">
                        <button
                          onClick={() => setProfilePerson(p)}
                          className="rounded-md text-right text-pulse-700 underline decoration-pulse-200 decoration-dotted underline-offset-4 transition-colors hover:text-pulse-800"
                          title="مشاهده پروفایل"
                        >
                          {p.full_name}
                        </button>
                      </td>
                      <td className="px-3 py-2.5 text-gray-600">
                        {p.job_title}
                        {p.is_manager && (
                          <span className="mr-1.5 rounded-full bg-gradient-to-bl from-amber-50 to-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-700">
                            مدیر
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-gray-500">{p.org_unit}</td>
                      <td className="px-3 py-2.5">
                        {p.status === "active" ? (
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
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => setEditingPersonnel(p)}
                            className="text-sm font-medium text-gray-600 hover:text-gray-800"
                          >
                            ویرایش
                          </button>
                          <button
                            onClick={() => setSelected(p)}
                            className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-sm font-medium text-pulse-600 transition-colors hover:bg-pulse-50"
                          >
                            <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M10 12a2 2 0 1 0 0-4 2 2 0 0 0 0 4z" />
                              <path d="M2 10s3-5 8-5 8 5 8 5-3 5-8 5-8-5-8-5z" />
                            </svg>
                            تنظیم دسترسی
                          </button>
                        </div>
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {data && data.items.length === 0 && (
            <p className="mt-3 text-center text-sm text-gray-400">موردی یافت نشد.</p>
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

      {/* ویرایش دسترسی داخل مودال مرکزی باز می‌شود، نه ستون کناری صفحه */}
      {selected && (
        <AccessEditor
          personnel={selected}
          users={users}
          onClose={() => setSelected(null)}
        />
      )}

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
        <EditPersonnelModal personnel={editingPersonnel} onClose={() => setEditingPersonnel(null)} />
      )}
    </div>
  );
}

function EditPersonnelModal({ personnel, onClose }: { personnel: Personnel; onClose: () => void }) {
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
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function save() {
    setError(null);
    setSaving(true);
    try {
      await apiClient.patch(`/personnel/${personnel.id}`, form);
      await queryClient.invalidateQueries({ queryKey: ["personnel"] });
      showSuccess("پرسنل به‌روزرسانی شد");
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
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            انصراف
          </Button>
          <Button onClick={save} disabled={saving}>
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
            className="h-4 w-4 rounded border-gray-300 text-pulse-500 focus:ring-pulse-400"
          />
          پرسنل مدیریتی
        </label>
      </div>
      {error && <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
    </Modal>
  );
}

function AccessEditor({
  personnel,
  users,
  onClose,
}: {
  personnel: Personnel;
  users: AppUser[];
  onClose: () => void;
}) {
  const { showSuccess, showError } = useToast();
  const isManager = personnel.is_manager;
  const [access, setAccess] = useState<Partial<EvaluationAccess>>({});
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setLoaded(false);
    setError(null);
    apiClient
      .get(`/personnel/${personnel.id}/access`)
      .then(({ data }) => {
        setAccess(data ?? {});
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoaded(true));
  }, [personnel.id]);

  const supervisors = users.filter((u) => u.role === "unit_supervisor");
  const deputies = users.filter((u) => u.role === "deputy");
  const ceos = users.filter((u) => u.role === "ceo");

  async function save() {
    setError(null);
    try {
      await apiClient.put(`/personnel/${personnel.id}/access`, {
        unit_supervisor_user_id: isManager ? null : access.unit_supervisor_user_id || null,
        deputy_user_id: access.deputy_user_id,
        ceo_user_id: access.ceo_user_id,
      });
      showSuccess("دسترسی ارزیابی ذخیره شد");
      onClose();
    } catch (err) {
      const message = extractErrorMessage(err);
      setError(message);
      showError(message);
    }
  }

  return (
    <Modal
      title={`دسترسی ارزیابی: ${personnel.full_name}`}
      onClose={onClose}
      footer={
        loaded && (
          <>
            <Button variant="secondary" onClick={onClose}>
              انصراف
            </Button>
            <Button onClick={save}>ذخیره</Button>
          </>
        )
      }
    >
      {!loaded ? (
        <div className="space-y-3 py-4">
          <div className="skeleton h-10" />
          <div className="skeleton h-10" />
          <div className="skeleton h-10" />
        </div>
      ) : (
        <div className="space-y-4 py-2">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">مسئول واحد</label>
            <select
              disabled={isManager}
              className={`${inputClass} disabled:bg-gray-50 disabled:text-gray-400`}
              value={access.unit_supervisor_user_id ?? ""}
              onChange={(e) =>
                setAccess({ ...access, unit_supervisor_user_id: e.target.value ? Number(e.target.value) : null })
              }
            >
              <option value="">— انتخاب کنید —</option>
              {supervisors.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.username}
                </option>
              ))}
            </select>
            {isManager && (
              <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
                چون این فرد به‌عنوان «مدیر» علامت خورده است، دسترسی مسئول واحد غیرفعال است؛ این فرد مستقیماً
                توسط معاونت ارزیابی می‌شود.
              </p>
            )}
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">معاونت</label>
            <select
              className={inputClass}
              value={access.deputy_user_id ?? ""}
              onChange={(e) => setAccess({ ...access, deputy_user_id: Number(e.target.value) })}
            >
              <option value="">— انتخاب کنید —</option>
              {deputies.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.username}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">مدیرعامل</label>
            <select
              className={inputClass}
              value={access.ceo_user_id ?? ""}
              onChange={(e) => setAccess({ ...access, ceo_user_id: Number(e.target.value) })}
            >
              <option value="">— انتخاب کنید —</option>
              {ceos.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.username}
                </option>
              ))}
            </select>
          </div>

          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
        </div>
      )}
    </Modal>
  );
}
