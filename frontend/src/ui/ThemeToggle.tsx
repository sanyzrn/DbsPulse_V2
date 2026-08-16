/** انتخاب تم — سه حالته، در نوار بالای صفحه.
 *
 * سه دکمهٔ کنار هم و نه یک کلید دوحالته: با کلید دوحالته، «مثل سیستم» یا وجود
 * ندارد یا حالت پنهانِ سومی می‌شود که کاربر نمی‌داند در آن است.
 */
import { useEffect, useState } from "react";
import {
  applyTheme,
  readStoredChoice,
  resolveTheme,
  storeChoice,
  type ThemeChoice,
} from "./theme";

const OPTIONS: { value: ThemeChoice; label: string; icon: React.ReactNode }[] = [
  {
    value: "light",
    label: "روشن",
    icon: (
      <>
        <circle cx="10" cy="10" r="3.5" />
        <path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.5 4.5l1.4 1.4M14.1 14.1l1.4 1.4M15.5 4.5l-1.4 1.4M5.9 14.1l-1.4 1.4" />
      </>
    ),
  },
  {
    value: "system",
    label: "مثل سیستم",
    icon: (
      <>
        <rect x="2.5" y="3.5" width="15" height="10" rx="1.5" />
        <path d="M7 16.5h6" />
      </>
    ),
  },
  {
    value: "dark",
    label: "شب",
    icon: <path d="M16 11.5A6.5 6.5 0 0 1 8.5 4a6.5 6.5 0 1 0 7.5 7.5z" />,
  },
];

export function ThemeToggle() {
  const [choice, setChoice] = useState<ThemeChoice>(() => readStoredChoice());

  // وقتی انتخاب «مثل سیستم» است، تغییر تنظیم سیستم باید فوراً دیده شود —
  // بدون این، کاربر باید صفحه را رفرش کند تا حرفش را که زده بود بشنویم.
  useEffect(() => {
    applyTheme(resolveTheme(choice));
    if (choice !== "system" || !window.matchMedia) return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme(resolveTheme("system"));
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [choice]);

  function pick(next: ThemeChoice) {
    setChoice(next);
    storeChoice(next);
  }

  return (
    <div
      role="radiogroup"
      aria-label="ظاهر برنامه"
      className="inline-flex items-center gap-0.5 rounded-full border border-gray-200 bg-white p-0.5"
    >
      {OPTIONS.map((option) => {
        const active = choice === option.value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={option.label}
            title={option.label}
            onClick={() => pick(option.value)}
            className={`flex h-7 w-7 cursor-pointer items-center justify-center rounded-full transition-colors ${
              active
                ? "bg-charcoal-900 text-white"
                : "text-gray-400 hover:bg-gray-100 hover:text-gray-700"
            }`}
          >
            <svg
              viewBox="0 0 20 20"
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              {option.icon}
            </svg>
          </button>
        );
      })}
    </div>
  );
}
