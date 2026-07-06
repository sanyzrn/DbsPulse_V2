import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { apiClient, extractErrorMessage } from "../../api/client";
import { useDebouncedValue, usePersonnelList, useUsersList } from "../../api/queries";
import { useConfirm } from "../../components/ConfirmDialog";
import { PaginationControls } from "../../components/PaginationControls";
import { useToast } from "../../components/Toast";
import { Button } from "../../ui/Button";
import { PageHeader } from "../../ui/Card";
import { ROLE_LABELS, type AppUser, type UserRole } from "../../types";

const ROLES: UserRole[] = ["unit_supervisor", "hr", "deputy", "ceo", "employee"];
const PAGE_SIZE = 10;

const inputClass =
  "w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition-all duration-200 focus:border-pulse-400";

export function UsersPage() {
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ username: "", password: "", role: "unit_supervisor" as UserRole });
  const [personnelId, setPersonnelId] = useState<number | "">("");
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const debouncedSearch = useDebouncedValue(search);

  // برای نقش «کارمند» باید پرسنل متناظر انتخاب شود تا کارنامه‌اش را ببیند
  const { data: personnelData } = usePersonnelList({ limit: 1000, offset: 0 });

  const { data, error: loadError } = useUsersList({
    q: debouncedSearch,
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
          <div className="relative">
            <svg viewBox="0 0 20 20" className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <circle cx="9" cy="9" r="6" />
              <path d="M14 14l3 3" />
            </svg>
            <input
              className="w-full rounded-xl border border-gray-200 bg-white py-1.5 pr-9 pl-3 text-sm text-gray-700 outline-none transition-all duration-200 focus:border-pulse-400 sm:w-64"
              placeholder="جست‌وجو (نام کاربری)…"
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
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">نام کاربری</th>
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">نقش</th>
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">وضعیت</th>
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600"></th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((u, idx) => (
                  <motion.tr
                    key={u.id}
                    className="border-b border-gray-50 transition-colors last:border-0 hover:bg-pulse-50/30"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.2, delay: idx * 0.03 }}
                  >
                    <td className="px-3 py-2.5 font-medium text-gray-700">{u.username}</td>
                    <td className="px-3 py-2.5 text-gray-600">{ROLE_LABELS[u.role]}</td>
                    <td className="px-3 py-2.5">
                      {u.is_active ? (
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
                      <button onClick={() => toggleActive(u)} className="text-sm font-medium text-pulse-600 hover:text-pulse-700">
                        {u.is_active ? "غیرفعال کردن" : "فعال کردن"}
                      </button>
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
  );
}
