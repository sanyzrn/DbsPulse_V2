import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useStageStats } from "../api/queries";
import { StatusBadge } from "./StatusBadge";
import { EASE_SOFT } from "../ui/motion";
import type { EvaluationStatus, StageStat } from "../types";

const faInt = (n: number) => n.toLocaleString("fa-IR");
const fa1 = (n: number) => n.toLocaleString("fa-IR", { maximumFractionDigits: 1 });

/** رنگ نوار هر مرحله — همان زنجیرهٔ StatusBadge، تا نشان و نوار یک زبان باشند.
 *  فقط پله‌های ۴۰۰: تم تیره پله‌های روشن‌تر را به رنگ‌های تیره بازتعریف می‌کند. */
const BAR: Record<string, string> = {
  draft: "bg-gray-400",
  submitted: "bg-blue-400",
  hr_approved: "bg-indigo-400",
  deputy_approved: "bg-amber-400",
  finalized: "bg-green-400",
};

function days(value: number | null): string {
  if (value === null) return "—";
  if (value < 1) return "کمتر از یک روز";
  return `${fa1(value)} روز`;
}

/** وضعیت پرونده‌های ارزیابی: هر مرحله، چند پرونده، و چقدر آن‌جا مانده.
 *
 *  جانشین «قیف گردش‌کار» که فقط یک عدد در هر مرحله می‌داد. آن عدد می‌گفت کجا
 *  شلوغ است ولی نه چرا: صفِ ده‌تایی که هر پرونده‌اش نیم روز می‌ماند سالم است، و
 *  صفِ دوتایی که هر کدام دو هفته مانده‌اند نیست — با یک عدد هر دو یک شکل بودند.
 *
 *  تفکیک به‌ازای شخص با کلیک باز می‌شود. همیشه‌باز بودنش پنج مرحله را به یک
 *  دیوارِ جدول تبدیل می‌کرد؛ «معاونت کند است» تا وقتی سه معاون داری جملهٔ
 *  بی‌مصرفی است، ولی خواندنش هم هر بار لازم نیست.
 */
export function StageStatusCard() {
  const { data: stages = [], isPending } = useStageStats();
  const [expanded, setExpanded] = useState<EvaluationStatus | null>(null);

  if (isPending) return <div className="skeleton h-72 rounded-2xl" />;
  if (stages.length === 0) return null;

  const totalActive = stages.reduce((sum, stage) => sum + stage.active, 0);
  const maxActive = Math.max(1, ...stages.map((stage) => stage.active));

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-3 sm:p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-bold text-gray-900">وضعیت پرونده‌های ارزیابی</h2>
        <p className="text-xs text-gray-500">
          <span className="tabular-nums">{faInt(totalActive)}</span> پرونده در جریان
        </p>
      </div>

      <ul className="divide-y divide-gray-100 overflow-hidden rounded-xl border border-gray-100">
        {stages.map((stage) => (
          <StageRow
            key={stage.status}
            stage={stage}
            maxActive={maxActive}
            open={expanded === stage.status}
            onToggle={() =>
              setExpanded((current) => (current === stage.status ? null : stage.status))
            }
          />
        ))}
      </ul>
    </div>
  );
}

function StageRow({
  stage,
  maxActive,
  open,
  onToggle,
}: {
  stage: StageStat;
  maxActive: number;
  open: boolean;
  onToggle: () => void;
}) {
  const hasOwners = stage.by_owner.length > 0;
  const terminal = stage.status === "finalized";
  // نوارِ صفر هم یک ردِ نازک می‌گیرد تا مرحله از قلم نیفتد.
  const width = stage.active === 0 ? 0 : Math.max(6, (stage.active / maxActive) * 100);

  return (
    <li>
      <button
        type="button"
        onClick={onToggle}
        disabled={!hasOwners}
        aria-expanded={open}
        title={
          terminal
            ? `${faInt(stage.total)} پرونده نهایی‌شده`
            : `روی میز: ${stage.holder} · میانگین توقف: ${days(stage.avg_dwell_days)}`
        }
        className={`flex min-h-10 w-full items-center gap-2.5 px-3 py-2 text-right transition-colors ${
          hasOwners ? "hover:bg-gray-50" : "cursor-default"
        }`}
      >
        <div className="flex w-32 shrink-0 items-center gap-1.5 sm:w-40">
          {hasOwners ? (
            <svg
              viewBox="0 0 20 20"
              className={`h-3.5 w-3.5 shrink-0 text-gray-400 transition-transform ${open ? "-rotate-90" : ""}`}
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              <path d="M12 5l-5 5 5 5" />
            </svg>
          ) : (
            <span className="w-3.5 shrink-0" aria-hidden />
          )}
          <StatusBadge status={stage.status} />
        </div>

        <div className="h-2 min-w-16 flex-1 overflow-hidden rounded-full bg-gray-100">
          <motion.div
            className={`h-full rounded-full ${BAR[stage.status] ?? "bg-gray-400"}`}
            initial={{ width: 0 }}
            animate={{ width: `${width}%` }}
            transition={{ duration: 0.45, ease: EASE_SOFT }}
          />
        </div>

        <div className="flex shrink-0 items-baseline gap-1">
          <span className="text-sm font-extrabold tabular-nums text-gray-900">
            {faInt(stage.active)}
          </span>
          <span className="text-[11px] text-gray-400">
            / {faInt(stage.total)}
          </span>
        </div>

        {/* جزئیات عملیاتی در همان ردیف، فقط جایی که عرض کافی دارد؛ در نمایش
            باریک، عنوان دکمه و بازشدن ردیف همان اطلاعات را بدون بلندکردن کارت
            در اختیار می‌گذارند. */}
        {!terminal && (
          <div className="hidden shrink-0 items-center gap-2 border-r border-gray-100 pr-2 text-[11px] text-gray-500 xl:flex">
            <span>روی میز: <b className="font-medium text-gray-700">{stage.holder}</b></span>
            <span>توقف: <b className="font-medium text-gray-700">{days(stage.avg_dwell_days)}</b></span>
            {stage.longest_active_days !== null && (
              <span>قدیمی‌ترین: <b className="font-medium text-gray-700">{days(stage.longest_active_days)}</b></span>
            )}
          </div>
        )}
      </button>

      <AnimatePresence initial={false}>
        {open && hasOwners && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: EASE_SOFT }}
            className="overflow-hidden border-t border-gray-100"
          >
            <div className="flex flex-wrap gap-x-4 gap-y-1 border-b border-gray-100 bg-gray-50 px-3 py-2 text-[11px] text-gray-500">
              <span>بسته‌شده: <b className="font-medium text-gray-700">{faInt(stage.closed)}</b></span>
              {stage.passes > stage.total && (
                <span className="text-amber-700">
                  برگشت به این مرحله: {faInt(stage.passes - stage.total)} بار
                </span>
              )}
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-[11px] text-gray-400">
                  <th className="px-3 py-1.5 text-right font-medium">مسئول</th>
                  <th className="px-3 py-1.5 text-right font-medium">در جریان</th>
                  <th className="px-3 py-1.5 text-right font-medium">کل</th>
                  <th className="px-3 py-1.5 text-right font-medium">بسته</th>
                  <th className="px-3 py-1.5 text-right font-medium">میانگین توقف</th>
                </tr>
              </thead>
              <tbody>
                {stage.by_owner.map((owner) => (
                  <tr key={owner.name} className="border-b border-gray-50 last:border-0">
                    <td className="px-3 py-1.5 font-medium text-gray-800">{owner.name}</td>
                    <td className="px-3 py-1.5 tabular-nums text-gray-900">{faInt(owner.active)}</td>
                    <td className="px-3 py-1.5 tabular-nums text-gray-500">{faInt(owner.total)}</td>
                    <td className="px-3 py-1.5 tabular-nums text-gray-500">{faInt(owner.closed)}</td>
                    <td className="px-3 py-1.5 text-gray-500">{days(owner.avg_dwell_days)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  );
}
