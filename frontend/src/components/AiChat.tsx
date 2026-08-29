import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { apiClient, extractErrorMessage } from "../api/client";
import { useToast } from "./Toast";
import { Tooltip } from "../ui/Tooltip";
import { EASE_SOFT } from "../ui/motion";
import type { AiAction, AiMessage, AiStatus } from "../types";

/** دستیار هوشمند — پنجرهٔ گفت‌وگو و کارت‌های تأیید.
 *
 *  اصلِ کل این قابلیت در یک جمله: **مدل پیشنهاد می‌دهد، کاربر تصمیم می‌گیرد.**
 *  وقتی پاسخ به کنش تبدیل می‌شود، JSON نشان داده نمی‌شود؛ یک *جمله* به زبان
 *  کاربر نوشته می‌شود و زیرش یک دکمه. تا آن دکمه فشرده نشود هیچ‌چیز اجرا
 *  نمی‌شود.
 *
 *  چرا قابل مذاکره نیست: مدلی که «کدام نمره را برای احمدی ثبت کردم؟» را
 *  «پروندهٔ احمدی را حذف کن» بفهمد، روی سرویس‌های ارزان یک فرض دور از ذهن
 *  نیست، و عذرخواهیِ بعدش ردیفِ حذف‌شده را برنمی‌گرداند.
 */
export function AiChat() {
  const { data: status } = useQuery({
    queryKey: ["ai", "status"],
    queryFn: async () => (await apiClient.get<AiStatus>("/ai/status")).data,
    // فعال‌سازی دستیار از پنل مدیریت یا تب دیگری باید بدون تأخیر دیده شود.
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
  });
  const [open, setOpen] = useState(false);

  // دکمه‌ای که تنها پاسخش «در دسترس نیست» باشد، از نبودنِ دکمه بدتر است.
  return (
    <>
      <Tooltip label="دستیار هوشمند">
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="دستیار هوشمند"
          className="fixed bottom-5 left-5 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-charcoal-900 text-white shadow-lg transition-transform hover:scale-105"
        >
          <SparkIcon className="h-5 w-5" />
        </button>
      </Tooltip>
      <AnimatePresence>
        {open && <ChatPanel status={status} onClose={() => setOpen(false)} />}
      </AnimatePresence>
    </>
  );
}

function ChatPanel({
  status,
  onClose,
}: {
  status?: AiStatus;
  onClose: () => void;
}) {
  const { showError } = useToast();
  const queryClient = useQueryClient();
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<AiMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  useEffect(() => {
    function onEscape(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, [onClose]);

  async function send() {
    const text = draft.trim();
    if (!text || busy || !status?.available) return;
    setDraft("");
    setFailure("");
    setMessages((prev) => [...prev, { id: Date.now(), role: "user", content: text, actions: [] }]);
    setBusy(true);
    try {
      const { data } = await apiClient.post<{
        conversation_id: number;
        reply: string;
        actions: AiAction[];
      }>("/ai/chat", { conversation_id: conversationId, message: text });
      setConversationId(data.conversation_id);
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, role: "assistant", content: data.reply, actions: data.actions },
      ]);
    } catch (err) {
      // متنِ خودِ سرویس، نه «مشکلی پیش آمد»: تفاوت ۴۰۱ با «مدل پیدا نشد» دو
      // رفعِ متفاوت است و کاربر روی هر دو می‌تواند کاری بکند.
      setFailure(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function run(action: AiAction, messageId: number) {
    if (conversationId === null) return;
    setBusy(true);
    try {
      const { data } = await apiClient.post<{ result: string }>("/ai/run-action", {
        conversation_id: conversationId,
        name: action.name,
        payload: action.payload,
      });
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId
            ? { ...m, actions: m.actions.filter((a) => a !== action), content: m.content }
            : m,
        ),
      );
      setMessages((prev) => [
        ...prev,
        { id: Date.now(), role: "assistant", content: `✅ ${data.result}`, actions: [] },
      ]);
      // داده عوض شد؛ هر صفحه‌ای که بازش کرده باید تازه‌اش را ببیند.
      await queryClient.invalidateQueries();
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <motion.div
        className="fixed inset-0 z-40 bg-gray-900/30"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      />
      <motion.section
        role="dialog"
        aria-label="دستیار هوشمند"
        className="fixed bottom-4 left-4 z-50 flex h-[min(640px,calc(100vh-2rem))] w-[min(420px,calc(100vw-2rem))] flex-col overflow-hidden rounded-3xl border border-gray-200 bg-white shadow-2xl"
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 16, scale: 0.98 }}
        transition={{ duration: 0.22, ease: EASE_SOFT }}
      >
        <header className="flex shrink-0 items-center gap-2 border-b border-gray-200 px-4 py-3">
          <SparkIcon className="h-4 w-4 text-pulse-600" />
          <h2 className="flex-1 text-sm font-bold text-gray-900">دستیار هوشمند</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="بستن"
            className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <path d="M5 5l10 10M15 5L5 15" />
            </svg>
          </button>
        </header>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
          {status && !status.available && (
            <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-900">
              {status.reason || "دستیار هوشمند هنوز برای این حساب فعال نشده است."}
            </p>
          )}
          {messages.length === 0 && (
            <p className="py-8 text-center text-sm text-gray-400">
              دربارهٔ پرسنل، پرونده‌های ارزیابی و شاخص‌ها بپرسید. برای تغییر داده، پیشنهاد را
              می‌بینید و خودتان تأیید می‌کنید.
            </p>
          )}
          {messages.map((message) => (
            <Bubble key={message.id} message={message} onRun={(a) => run(a, message.id)} busy={busy} />
          ))}
          {busy && <p className="text-xs text-gray-400">در حال پاسخ‌دادن…</p>}
          {failure && (
            <p className="rounded-xl bg-red-50 px-3 py-2 text-xs leading-relaxed text-red-700">
              {failure}
            </p>
          )}
          <div ref={endRef} />
        </div>

        <form
          className="flex shrink-0 items-end gap-2 border-t border-gray-200 p-3"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={!status?.available || busy}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
            rows={2}
            placeholder="پرسشتان را بنویسید…"
            className="max-h-32 min-h-[44px] flex-1 resize-none rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-900 outline-none transition-colors focus:border-gray-900 focus:bg-white disabled:cursor-not-allowed disabled:opacity-60"
          />
          {/* دکمه هنگام درخواستِ در جریان خاموش است: دو درخواست هم‌زمان یعنی
              هرکدام دیرتر تمام شود برنده است، که لزوماً همانی نیست که آخرین
              کلیک خواسته بود. */}
          <button
            type="submit"
            disabled={busy || !status?.available || !draft.trim()}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-pulse-600 text-white transition-colors hover:bg-pulse-700 disabled:opacity-40"
            aria-label="ارسال"
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 3L9 11M17 3l-5 14-3-6-6-3 14-5z" />
            </svg>
          </button>
        </form>
      </motion.section>
    </>
  );
}

function Bubble({
  message,
  onRun,
  busy,
}: {
  message: AiMessage;
  onRun: (action: AiAction) => void;
  busy: boolean;
}) {
  const mine = message.role === "user";
  const text = message.content.trim();

  // پاسخی که *فقط* یک کنش بود، نثری ندارد. بدون این، یک حبابِ خالی روی صفحه
  // می‌ماند — و بعد از تأییدِ کنش، تنها چیزی که از آن پیام باقی می‌ماند.
  if (!text && message.actions.length === 0) return null;

  return (
    <div className={mine ? "flex justify-start" : "flex justify-end"}>
      <div className="max-w-[85%] space-y-2">
        {text && (
          <div
            className={`whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm leading-relaxed ${
              mine ? "bg-pulse-50 text-pulse-700" : "bg-gray-100 text-gray-800"
            }`}
          >
            {text}
          </div>
        )}
        {message.actions.map((action, index) => (
          <div
            key={`${action.name}-${index}`}
            className="rounded-2xl border border-amber-200 bg-amber-50/60 px-3 py-2.5"
          >
            <p className="text-xs font-medium leading-relaxed text-amber-900">{action.summary}</p>
            <button
              type="button"
              disabled={busy}
              onClick={() => onRun(action)}
              className="mt-2 rounded-lg bg-amber-600 px-3 py-1 text-xs font-semibold text-white transition-colors hover:bg-amber-700 disabled:opacity-40"
            >
              تأیید و انجام
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function SparkIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" className={className} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M10 2.5l1.7 4.3 4.3 1.7-4.3 1.7L10 14.5l-1.7-4.3L4 8.5l4.3-1.7L10 2.5z" />
      <path d="M15.5 13.5l.8 1.9 1.9.8-1.9.8-.8 1.9-.8-1.9-1.9-.8 1.9-.8.8-1.9z" />
    </svg>
  );
}
