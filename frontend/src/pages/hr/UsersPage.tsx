import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../../api/client";
import { useDebouncedValue, usePersonnelList, useUsersList } from "../../api/queries";
import { useAuth } from "../../auth/AuthContext";
import { useConfirm } from "../../components/ConfirmDialog";
import { PaginationControls } from "../../components/PaginationControls";
import { useToast } from "../../components/Toast";
import { Button } from "../../ui/Button";
import { PageHeader } from "../../ui/Card";
import { Modal } from "../../ui/Modal";
import { Table } from "../../ui/Table";
import { ROLE_LABELS, type AppUser, type Personnel, type UserRole } from "../../types";

const ROLES: UserRole[] = ["unit_supervisor", "hr", "deputy", "ceo", "employee"];
const PAGE_SIZE = 10;

const inputClass =
  "w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white";

export function UsersPage() {
  const { showSuccess, showError } = useToast();
  const { user: currentUser } = useAuth();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ username: "", password: "", role: "unit_supervisor" as UserRole });
  const [personnelId, setPersonnelId] = useState<number | "">("");
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<UserRole | "">("");
  const [page, setPage] = useState(0);
  const [editingUser, setEditingUser] = useState<AppUser | null>(null);
  const debouncedSearch = useDebouncedValue(search);

  // برای نقش «کارمند» باید پرسنل متناظر انتخاب شود تا کارنامه‌اش را ببیند
  const { data: personnelData } = usePersonnelList({ limit: 1000, offset: 0 });

  const { data, error: loadError } = useUsersList({
    q: debouncedSearch,
    role: roleFilter || undefined,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  async function createUser() {
    setError(null);
    if (form.role === "employee" && personnelId === "") {
      const message = "برای نقش «کارمند» باید پرسنل متناظر انتخاب شود";
      setError(message);
      showError(message);
      return;
    }
    try {
      await apiClient.post("/users", {
        ...form,
        personnel_id: form.role === "employee" ? personnelId : undefined,
      });
      setForm({ username: "", password: "", role: "unit_supervisor" });
      setPersonnelId("");
      await queryClient.invalidateQueries({ queryKey: ["users"] });
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
      <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
        <h2 className="mb-4 text-base font-bold text-gray-900">ساخت حساب کاربری</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createUser();
          }}
          className="flex flex-wrap items-end gap-3 text-sm"
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
          <Button type="submit">ساخت کاربر</Button>
        </form>
        {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
      </div>

      <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-bold text-gray-900">فهرست کاربران</h2>
          <div className="flex flex-wrap items-center gap-2">
            {/* فیلتر نقش — ترکیب‌پذیر با جست‌وجو */}
            <select
              aria-label="فیلتر نقش"
              className="rounded-xl border border-gray-200 bg-gray-100 py-1.5 pr-3 pl-8 text-sm text-gray-700 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white"
              value={roleFilter}
              onChange={(e) => {
                setRoleFilter(e.target.value as UserRole | "");
                setPage(0);
              }}
            >
              <option value="">همهٔ نقش‌ها</option>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </select>
            <div className="relative">
              <svg viewBox="0 0 20 20" className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <circle cx="9" cy="9" r="6" />
                <path d="M14 14l3 3" />
              </svg>
              <input
                className="w-full rounded-xl border border-gray-200 bg-gray-100 py-1.5 pr-9 pl-3 text-sm text-gray-700 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white sm:w-64"
                placeholder="جست‌وجو (نام کاربری)…"
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
            headers={["نام کاربری", "نقش", "وضعیت", ""]}
            rowKeys={data.items.map((u) => u.id)}
            rows={data.items.map((u) => [
              <span key="username" className="font-medium text-gray-700">
                {u.username}
              </span>,
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
          pageSize={PAGE_SIZE}
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
