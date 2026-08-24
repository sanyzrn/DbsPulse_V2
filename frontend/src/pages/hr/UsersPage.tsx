import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../../api/client";
import { useDebouncedValue, usePersonnelList, useUsersList } from "../../api/queries";
import { useAuth } from "../../auth/AuthContext";
import { useConfirm } from "../../components/ConfirmDialog";
import { ExcelExportButton } from "../../components/ExcelExportButton";
import { PaginationControls } from "../../components/PaginationControls";
import { useToast } from "../../components/Toast";
import { Button } from "../../ui/Button";
import { FilterSelect, PageHeader, TableSkeleton } from "../../ui/Card";
import { Modal } from "../../ui/Modal";
import { Table } from "../../ui/Table";
import { ROLE_LABELS, type AppUser, type Personnel, type UserRole } from "../../types";
import { SearchInput } from "../../ui/SearchInput";

const ROLES: UserRole[] = ["unit_supervisor", "hr", "deputy", "ceo", "employee"];
/** پیش‌فرض تعداد در هر صفحه؛ کاربر می‌تواند از نوار پایین عوضش کند. */
const DEFAULT_PAGE_SIZE = 10;

const inputClass =
  "w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white";

export function UsersPage() {
  const { showSuccess, showError } = useToast();
  const { user: currentUser } = useAuth();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    username: "",
    fullName: "",
    password: "",
    role: "unit_supervisor" as UserRole,
  });
  const [personnelId, setPersonnelId] = useState<number | "">("");
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<UserRole | "">("");
  const [activeFilter, setActiveFilter] = useState<"" | "true" | "false">("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [showAddUser, setShowAddUser] = useState(false);
  const [editingUser, setEditingUser] = useState<AppUser | null>(null);
  const debouncedSearch = useDebouncedValue(search);

  // برای نقش «کارمند» باید پرسنل متناظر انتخاب شود تا کارنامه‌اش را ببیند
  const { data: personnelData } = usePersonnelList({ limit: 1000, offset: 0 });

  const listParams = {
    q: debouncedSearch,
    role: roleFilter || undefined,
    is_active: activeFilter === "" ? undefined : activeFilter === "true",
  } as const;

  const { data, error: loadError, isPending } = useUsersList({
    ...listParams,
    limit: pageSize,
    offset: page * pageSize,
  });
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const hasActiveFilter = Boolean(search || roleFilter || activeFilter);

  function resetFilters() {
    setSearch("");
    setRoleFilter("");
    setActiveFilter("");
    setPage(0);
  }

  async function createUser() {
    setError(null);
    if (form.role === "employee" && personnelId === "") {
      const message = "برای نقش «کارمند» باید پرسنل متناظر انتخاب شود";
      setError(message);
      showError(message);
      return;
    }
    try {
      const { fullName, ...rest } = form;
      await apiClient.post("/users", {
        ...rest,
        // برای حساب «کارمند» نام از پروندهٔ پرسنلی می‌آید؛ فرستادن دوبارهٔ آن فقط
        // یک نسخهٔ دوم می‌سازد که با اصلاح پرونده هماهنگ نمی‌ماند.
        full_name: form.role === "employee" ? undefined : fullName.trim() || undefined,
        personnel_id: form.role === "employee" ? personnelId : undefined,
      });
      setForm({ username: "", fullName: "", password: "", role: "unit_supervisor" });
      setPersonnelId("");
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      setShowAddUser(false);
      showSuccess("کاربر با موفقیت ساخته شد");
    } catch (err) {
      const message = extractErrorMessage(err);
      setError(message);
      showError(message);
    }
  }

  async function toggleActive(u: AppUser) {
    if (u.is_active) {
      const ok = await confirm({
        title: `غیرفعال کردن «${u.username}»؟`,
        description: "این کاربر دیگر نمی‌تواند وارد سامانه شود، اما داده‌های قبلی‌اش حفظ می‌شود.",
        confirmLabel: "غیرفعال کن",
      });
      if (!ok) return;
    }
    try {
      await apiClient.patch(`/users/${u.id}`, { is_active: !u.is_active });
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      showSuccess(u.is_active ? "کاربر غیرفعال شد" : "کاربر فعال شد");
    } catch (err) {
      showError(extractErrorMessage(err));
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="کاربران" subtitle="ساخت و مدیریت حساب‌های کاربری نقش‌های مختلف سامانه" />
      {showAddUser && (
        <Modal
          title="ساخت حساب کاربری"
          onClose={() => setShowAddUser(false)}
          footer={
            <>
              <Button variant="secondary" onClick={() => setShowAddUser(false)}>
                انصراف
              </Button>
              <Button type="submit" form="add-user-form">
                ساخت کاربر
              </Button>
            </>
          }
        >
        <form
          id="add-user-form"
          onSubmit={(e) => {
            e.preventDefault();
            createUser();
          }}
          className="flex flex-wrap items-end gap-3 py-2 text-sm"
        >
          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            نام کاربری
            <input
              required
              autoComplete="off"
              className={`${inputClass} sm:w-40`}
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
            />
          </label>
          {form.role !== "employee" && (
            <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
              نام و سِمَت
              <input
                autoComplete="off"
                placeholder="مثلاً: معاونت اداری، آقای رضایی"
                className={`${inputClass} sm:w-56`}
                value={form.fullName}
                onChange={(e) => setForm({ ...form, fullName: e.target.value })}
              />
            </label>
          )}
          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            رمز عبور (حداقل ۱۰ نویسه)
            <input
              type="password"
              required
              minLength={10}
              autoComplete="new-password"
              className={`${inputClass} sm:w-44`}
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            نقش
            <select
              className={`${inputClass} sm:w-36`}
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </select>
          </label>
          {form.role === "employee" && (
            <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
              پرسنل متناظر
              <select
                required
                className={`${inputClass} sm:w-52`}
                value={personnelId}
                onChange={(e) => setPersonnelId(e.target.value === "" ? "" : Number(e.target.value))}
              >
                <option value="">انتخاب کنید…</option>
                {personnelData?.items.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name} ({p.personnel_code})
                  </option>
                ))}
              </select>
            </label>
          )}
        </form>
        {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
        </Modal>
      )}

      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-card">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-3">
            <h2 className="text-base font-bold text-gray-900">فهرست کاربران</h2>
            <Button onClick={() => { setError(null); setShowAddUser(true); }}>
              + ساخت کاربر
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ExcelExportButton url="/users/export.xlsx" filename="users.xlsx" params={listParams} />
            {/* فیلتر نقش — ترکیب‌پذیر با جست‌وجو و وضعیت */}
            <FilterSelect
              aria-label="فیلتر نقش"
              value={roleFilter}
              onChange={(v) => {
                setRoleFilter(v as UserRole | "");
                setPage(0);
              }}
            >
              <option value="">همهٔ نقش‌ها</option>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </FilterSelect>
            <FilterSelect
              aria-label="فیلتر وضعیت"
              value={activeFilter}
              onChange={(v) => {
                setActiveFilter(v as "" | "true" | "false");
                setPage(0);
              }}
            >
              <option value="">همهٔ وضعیت‌ها</option>
              <option value="true">فعال</option>
              <option value="false">غیرفعال</option>
            </FilterSelect>
            <SearchInput
              widthClass="sm:w-56"
              placeholder="جست‌وجو (نام یا نام کاربری)…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(0);
              }}
            />
            {hasActiveFilter && (
              <button
                onClick={resetFilters}
                className="rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-500 transition-colors hover:bg-gray-50 hover:text-gray-700"
              >
                حذف فیلترها
              </button>
            )}
          </div>
        </div>
        {loadError != null && (
          <p className="mb-2 text-sm text-red-600">{extractErrorMessage(loadError)}</p>
        )}
        {isPending && <TableSkeleton rows={6} />}
        {data && (
          <Table
            bordered={false}
            headers={["نام کاربری", "نام", "نقش", "وضعیت", ""]}
            rowKeys={data.items.map((u) => u.id)}
            rows={data.items.map((u) => [
              <span key="username" className="font-medium text-gray-700">
                {u.username}
              </span>,
              // بک‌اند وقتی نامی نداشته باشد خودِ نام کاربری را برمی‌گرداند، پس
              // نابرابری یعنی «نام واقعی دارد». تکرار نام کاربری در دو ستون
              // چیزی اضافه نمی‌کند؛ خط تیره صریح‌تر می‌گوید هنوز اسمی ثبت نشده.
              u.display_name !== u.username ? (
                <span key="name" className="text-gray-700">
                  {u.display_name}
                </span>
              ) : (
                <span key="name" className="text-gray-400">
                  —
                </span>
              ),
              <span key="role" className="text-gray-600">
                {ROLE_LABELS[u.role]}
              </span>,
              u.is_active ? (
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
                  onClick={() => setEditingUser(u)}
                  className="text-sm font-medium text-gray-600 hover:text-gray-800"
                >
                  ویرایش
                </button>
                {/* حساب خودِ HR قابل غیرفعال‌شدن نیست (محافظ قفل‌نشدن سامانه) */}
                {u.id !== currentUser?.id && (
                  <button onClick={() => toggleActive(u)} className="text-sm font-medium text-pulse-600 hover:text-pulse-700">
                    {u.is_active ? "غیرفعال کردن" : "فعال کردن"}
                  </button>
                )}
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

      {editingUser && (
        <EditUserModal
          user={editingUser}
          personnel={personnelData?.items ?? []}
          onClose={() => setEditingUser(null)}
        />
      )}
    </div>
  );
}

function EditUserModal({
  user,
  personnel,
  onClose,
}: {
  user: AppUser;
  personnel: Personnel[];
  onClose: () => void;
}) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [role, setRole] = useState<UserRole>(user.role);
  const [fullName, setFullName] = useState(user.full_name ?? "");
  const [personnelId, setPersonnelId] = useState<number | "">(user.personnel_id ?? "");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function save() {
    setError(null);
    if (role === "employee" && personnelId === "") {
      const message = "برای نقش «کارمند» باید پرسنل متناظر انتخاب شود";
      setError(message);
      showError(message);
      return;
    }
    if (newPassword && newPassword.length < 10) {
      const message = "رمز جدید باید حداقل ۱۰ نویسه باشد";
      setError(message);
      showError(message);
      return;
    }
    setSaving(true);
    try {
      await apiClient.patch(`/users/${user.id}`, {
        role,
        full_name: fullName.trim() || null,
        personnel_id: role === "employee" ? personnelId : null,
        ...(newPassword ? { password: newPassword } : {}),
      });
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      showSuccess("کاربر به‌روزرسانی شد");
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
      title={`ویرایش کاربر: ${user.username}`}
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
      <div className="space-y-4 py-2">
        <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700">
          نام و سِمَت
          <input
            autoComplete="off"
            placeholder="مثلاً: معاونت اداری، آقای رضایی"
            className={inputClass}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
          {role === "employee" && (
            <span className="text-xs font-normal text-gray-500">
              برای حساب کارمند، نامِ نمایش‌داده‌شده از پروندهٔ پرسنلی خوانده می‌شود.
            </span>
          )}
        </label>

        <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700">
          نقش
          <select className={inputClass} value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
        </label>

        {role === "employee" && (
          <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700">
            پرسنل متناظر
            <select
              className={inputClass}
              value={personnelId}
              onChange={(e) => setPersonnelId(e.target.value === "" ? "" : Number(e.target.value))}
            >
              <option value="">انتخاب کنید…</option>
              {personnel.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.full_name} ({p.personnel_code})
                </option>
              ))}
            </select>
          </label>
        )}

        <div className="border-t border-gray-100 pt-4">
          <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700">
            تعیین رمز جدید (اختیاری)
            <input
              type="password"
              minLength={10}
              autoComplete="new-password"
              placeholder="خالی بگذارید تا رمز فعلی تغییر نکند"
              className={inputClass}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </label>
          {newPassword && (
            <p className="mt-1.5 text-xs text-amber-600">
              با تنظیم رمز جدید، تمام نشست‌های فعال این کاربر باطل می‌شود و باید در ورود بعدی رمز را
              دوباره تغییر دهد.
            </p>
          )}
        </div>

        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
      </div>
    </Modal>
  );
}
