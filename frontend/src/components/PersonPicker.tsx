/** انتخابگر پرسنل با جست‌وجو — یک کامپوننت برای همهٔ جاهایی که باید یک نفر انتخاب شود.
 *
 * پیش از این دو راه‌حل جدا وجود داشت و هر دو با بلندشدن فهرست خراب می‌شدند:
 *
 *  • «کارنامهٔ فرد» یک <select> ساده بود روی `limit: 1000`. یعنی کل پرسنل در یک
 *    درخواست می‌آمد و کاربر باید بینشان اسکرول می‌کرد؛ با چند صد نفر بی‌استفاده
 *    می‌شد، و بالای هزار نفر حتی کاملش را هم نمی‌گرفت.
 *  • فیلتر «پرسنل مشخص» یک input جست‌وجو *به‌علاوهٔ* یک <select> بود — دو کنترل
 *    برای یک کار، که کاربر باید ترتیبشان را حدس می‌زد.
 *
 * این‌جا جست‌وجو سمت سرور است (`q`) و فقط چند نتیجهٔ اول می‌آید، پس طول فهرست
 * پرسنل دیگر مهم نیست. علاوه بر نام، واحد و کد پرسنلی هم نشان داده می‌شود چون
 * هم‌نامی در سازمان عادی است و نام تنها برای تشخیص کافی نیست.
 */
import { useEffect, useId, useRef, useState } from "react";
import { useDebouncedValue, usePersonnelDetail, usePersonnelList } from "../api/queries";
import type { Personnel } from "../types";

const RESULT_LIMIT = 12;

function personLabel(person: Personnel): string {
  return `${person.full_name} — ${person.org_unit}`;
}

export function PersonPicker({
  value,
  onChange,
  placeholder = "جست‌وجو و انتخاب فرد…",
  accessibleToMe = false,
  className = "",
  "aria-label": ariaLabel = "انتخاب فرد",
}: {
  value: number | null;
  onChange: (personnelId: number | null) => void;
  placeholder?: string;
  /** فقط افرادی که کاربر جاری به آن‌ها دسترسی دارد */
  accessibleToMe?: boolean;
  className?: string;
  "aria-label"?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const debounced = useDebouncedValue(query);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();

  const { data: page, isFetching } = usePersonnelList({
    q: debounced || undefined,
    accessible_to_me: accessibleToMe || undefined,
    limit: RESULT_LIMIT,
    offset: 0,
  });
  const results = page?.items ?? [];

  // فردِ انتخاب‌شده ممکن است در نتایجِ جست‌وجوی فعلی نباشد (مثلاً کاربر بعد از
  // انتخاب، عبارت دیگری تایپ کرده). بدون این، دکمه به «هیچ‌کس انتخاب نشده» برمی‌گشت.
  const { data: selected } = usePersonnelDetail(value);

  // بستن با کلیک بیرون
  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  // با تغییر نتایج، نشانگر نباید بیرون از فهرست بماند
  useEffect(() => setActive(0), [debounced]);

  function choose(person: Personnel | null) {
    onChange(person?.id ?? null);
    setOpen(false);
    setQuery("");
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) return setOpen(true);
      setActive((prev) => {
        const next = event.key === "ArrowDown" ? prev + 1 : prev - 1;
        if (results.length === 0) return 0;
        return (next + results.length) % results.length;
      });
    } else if (event.key === "Enter") {
      if (!open) return;
      event.preventDefault();
      const person = results[active];
      if (person) choose(person);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-haspopup="listbox"
          aria-label={ariaLabel}
          onClick={() => setOpen((v) => !v)}
          onKeyDown={onKeyDown}
          className="flex min-w-0 flex-1 items-center justify-between gap-2 rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-start text-sm text-gray-700 outline-none transition-colors duration-150 hover:bg-gray-50 focus:border-gray-900 focus:bg-white"
        >
          <span className={`truncate ${selected ? "" : "text-gray-400"}`}>
            {selected ? personLabel(selected) : placeholder}
          </span>
          <svg
            viewBox="0 0 20 20"
            className={`h-3.5 w-3.5 shrink-0 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden
          >
            <path d="M6 8l4 4 4-4" />
          </svg>
        </button>
        {value !== null && (
          <button
            type="button"
            onClick={() => choose(null)}
            aria-label="حذف انتخاب فرد"
            title="حذف انتخاب"
            className="shrink-0 rounded-lg border border-gray-200 bg-white px-2 py-2 text-gray-400 transition-colors hover:bg-gray-50 hover:text-gray-600"
          >
            <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M6 6l8 8M14 6l-8 8" />
            </svg>
          </button>
        )}
      </div>

      {open && (
        <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-xl border border-gray-200 bg-white shadow-xl">
          <div className="border-b border-gray-100 p-2">
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="نام یا کد پرسنلی…"
              aria-label="جست‌وجوی پرسنل"
              className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-sm text-gray-700 outline-none focus:border-gray-900 focus:bg-white"
            />
          </div>

          <ul id={listId} role="listbox" className="max-h-64 overflow-y-auto py-1">
            {results.length === 0 ? (
              <li className="px-3 py-6 text-center text-sm text-gray-400">
                {isFetching ? "در حال جست‌وجو…" : "کسی با این مشخصات پیدا نشد."}
              </li>
            ) : (
              results.map((person, index) => (
                <li key={person.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={person.id === value}
                    onMouseEnter={() => setActive(index)}
                    onClick={() => choose(person)}
                    className={`flex w-full items-baseline justify-between gap-2 px-3 py-2 text-start transition-colors ${
                      index === active ? "bg-pulse-50" : ""
                    } ${person.id === value ? "font-bold" : ""}`}
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm text-gray-800">{person.full_name}</span>
                      <span className="block truncate text-[11px] text-gray-400">
                        {person.org_unit} · {person.job_title}
                      </span>
                    </span>
                    <span className="shrink-0 font-mono text-[10px] text-gray-400">
                      {person.personnel_code}
                    </span>
                  </button>
                </li>
              ))
            )}
          </ul>

          {page && page.total > results.length && (
            <p className="border-t border-gray-100 px-3 py-1.5 text-[11px] text-gray-400">
              {results.length.toLocaleString("fa-IR")} نتیجهٔ نخست از{" "}
              {page.total.toLocaleString("fa-IR")} — برای باریک‌کردن، بیشتر تایپ کنید.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
