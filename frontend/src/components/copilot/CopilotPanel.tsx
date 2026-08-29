import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { apiClient, extractErrorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { useToast } from "../Toast";
import { EASE_SOFT } from "../../ui/motion";
import type {
  AiChatTurn,
  AiConversation,
  AiMessage,
  AiPendingAction,
  AiStatus,
  AiTool,
  AiUploadInfo,
} from "../../types";
import { Markdown } from "./Markdown";
import { PendingActionCard, StepTrace, UploadCard } from "./Cards";

/**
 * سطحِ گفت‌وگوی همکار — بین پنجرهٔ شناور و صفحهٔ کامل مشترک است.
 *
 * تاریخچه واقعاً ماندگار است: گفت‌وگوها از سرور می‌آیند و با بازکردنِ دوباره،
 * گام‌ها و کارت‌های تأیید با همان وضعیتِ زنده‌شان بازسازی می‌شوند.
 */

const SUGGESTIONS_BY_ROLE: Record<string, string[]> = {
  hr: [
    "وضعیت پرونده‌های ارزیابی چطور است؟",
    "قراردادهای رو به اتمام را نشانم بده",
    "گزارش میانگین واحدها را بده",
    "اکسل پرسنل را برایم بررسی کن",
  ],
  unit_supervisor: [
    "پرونده‌های بازِ من کدام‌اند؟",
    "چه کسانی زیرمجموعه‌ام ارزیابی نشده‌اند؟",
    "الگوی نمره‌دهی من چطور است؟",
  ],
  deputy: ["صف بررسی من چیست؟", "تحلیل سازمان را نشانم بده"],
  ceo: ["کدام واحد عقب است؟", "پرونده‌های در انتظار تأیید من"],
  employee: ["کارنامه‌های من", "امتیاز نهایی من چند است؟"],
  support: ["وضعیت سامانه و تنظیمات دستیار", "رویدادهای اخیر سامانه"],
};

export function CopilotPanel({
  status,
  variant,
  onClose,
  onExpand,
}: {
  status?: AiStatus;
  variant: "drawer" | "page";
  onClose?: () => void;
  onExpand?: () => void;
}) {
  const { showError, showSuccess } = useToast();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<AiMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [failure, setFailure] = useState("");
  const [pendingList, setPendingList] = useState<AiPendingAction[]>([]);
  const [uploads, setUploads] = useState<AiUploadInfo[]>([]);
  const [showHistory, setShowHistory] = useState(variant === "page");
  const [uploading, setUploading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const canChat = Boolean(status?.available);
  const canUpload = canChat && Boolean(status?.allow_uploads);

  // گفت‌وگوهای پیشین — تاریخچه‌ای که با بستنِ پنجره نمی‌میرد
  const { data: conversations = [] } = useQuery({
    queryKey: ["ai", "conversations"],
    queryFn: async () => (await apiClient.get<AiConversation[]>("/ai/conversations")).data,
    enabled: canChat,
  });

  // ابزارهایی که این کاربر واقعاً دارد — برای «چه می‌توانی برایم بکنی»
  const { data: tools = [] } = useQuery({
    queryKey: ["ai", "tools"],
    queryFn: async () => (await apiClient.get<AiTool[]>("/ai/tools")).data,
    enabled: canChat && variant === "page",
  });

  const suggestions = useMemo(
    () => SUGGESTIONS_BY_ROLE[user?.role ?? ""] ?? SUGGESTIONS_BY_ROLE.hr!,
    [user?.role],
  );

  const livePendingCount = useMemo(
    () => pendingList.filter((p) => p.status === "pending").length,
    [pendingList],
  );

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, livePendingCount, failure, uploading]);

  useEffect(() => {
    function onEscape(e: KeyboardEvent) {
      if (e.key === "Escape" && variant === "drawer") onClose?.();
    }
    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, [onClose, variant]);

  function openConversation(id: number) {
    setConversationId(id);
    setShowHistory(false);
    void loadConversation(id);
  }

  async function loadConversation(id: number) {
    try {
      const { data: history } = await apiClient.get<AiMessage[]>(`/ai/conversations/${id}`);
      setMessages(history);
      setPendingList(history.flatMap((m) => m.pending ?? []));
      const { data: attachmentList } = await apiClient.get<AiUploadInfo[]>(
        `/ai/conversations/${id}/attachments`,
      );
      setUploads(attachmentList);
    } catch (err) {
      showError(extractErrorMessage(err));
    }
  }

  function newConversation() {
    setConversationId(null);
    setMessages([]);
    setPendingList([]);
    setUploads([]);
    setFailure("");
    setShowHistory(false);
  }

  const sendMutation = useMutation({
    mutationFn: async (text: string) => {
      const { data } = await apiClient.post<AiChatTurn>("/ai/chat", {
        conversation_id: conversationId,
        message: text,
      });
      return data;
    },
    onSuccess: (data) => {
      setConversationId(data.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: "assistant",
          content: data.reply,
          actions: [],
          steps: data.steps,
        },
      ]);
      setPendingList((prev) => [
        ...prev.filter((p) => !data.pending.some((np) => np.id === p.id)),
        ...data.pending,
      ]);
      void queryClient.invalidateQueries({ queryKey: ["ai", "conversations"] });
    },
    onError: (err) => setFailure(extractErrorMessage(err)),
  });

  const confirmMutation = useMutation({
    mutationFn: async (id: number) => {
      const { data } = await apiClient.post<AiChatTurn>(`/ai/pending/${id}/confirm`, {});
      return data;
    },
    onSuccess: (_data, id) => {
      // وضعیتِ زنده از سرور: کارت‌ها از حقیقتِ الان می‌آیند، نه عکسِ لحظهٔ ارسال
      if (conversationId) {
        void loadPendingState(conversationId);
        void loadConversationMessagesOnly(conversationId);
      }
      setPendingList((prev) => prev.map((p) => (p.id === id ? { ...p, status: "confirmed" as const } : p)));
      showSuccess("انجام شد");
      // دادهٔ سامانه عوض شد؛ صفحه‌های باز باید تازه‌اش را ببینند
      void queryClient.invalidateQueries();
    },
    onError: (err) => showError(extractErrorMessage(err)),
  });

  const rejectMutation = useMutation({
    mutationFn: async (id: number) => {
      const { data } = await apiClient.post<AiPendingAction>(`/ai/pending/${id}/reject`, {});
      return data;
    },
    onSuccess: (data) => {
      if (conversationId) {
        void loadPendingState(conversationId);
        void loadConversationMessagesOnly(conversationId);
      }
      setPendingList((prev) =>
        prev.map((p) => (p.id === data.id ? { ...p, status: "rejected" as const } : p)),
      );
    },
    onError: (err) => showError(extractErrorMessage(err)),
  });

  async function loadPendingState(id: number) {
    try {
      const { data } = await apiClient.get<AiPendingAction[]>("/ai/pending", {
        params: { conversation_id: id },
      });
      setPendingList(data);
    } catch {
      /* حالتِ آفلاینِ کوچک؛ کارت‌ها با رفرش بعدی درست می‌شوند */
    }
  }

  async function loadConversationMessagesOnly(id: number) {
    try {
      const { data: history } = await apiClient.get<AiMessage[]>(`/ai/conversations/${id}`);
      setMessages(history);
    } catch {
      /* بی‌صدا: پیامِ نتیجه در رفرش بعدی هم می‌آید */
    }
  }

  async function send() {
    const text = draft.trim();
    if (!text || sendMutation.isPending || !canChat) return;
    setDraft("");
    setFailure("");
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: "user", content: text, actions: [] },
    ]);
    sendMutation.mutate(text);
  }

  async function uploadFile(file: File) {
    if (!conversationId) {
      // گفت‌وگوی تازه: اول یک شناسه بساز تا پیوست به چیزی بچسبد
      try {
        const { data } = await apiClient.post<AiConversation>("/ai/conversations", {});
        setConversationId(data.id);
        void queryClient.invalidateQueries({ queryKey: ["ai", "conversations"] });
        await doUpload(data.id, file);
      } catch (err) {
        showError(extractErrorMessage(err));
      }
      return;
    }
    await doUpload(conversationId, file);
  }

  async function doUpload(conversationIdValue: number, file: File) {
    setUploading(true);
    setFailure("");
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await apiClient.post<AiUploadInfo>(
        `/ai/conversations/${conversationIdValue}/attachments`,
        form,
      );
      setUploads((prev) => [...prev, data]);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: "assistant",
          content: `فایل «${data.filename}» را دیدم.` + (data.kind === "personnel_import" ? ` ${data.total_rows} ردیف دارد؛ ${data.valid_count} سالم و ${data.invalid_count} خطادار. بگویید بررسی‌اش کنم تا خطاها را ردیف‌به‌ردیف بگویم.` : ""),
          actions: [],
        },
      ]);
    } catch (err) {
      setFailure(extractErrorMessage(err));
    } finally {
      setUploading(false);
    }
  }

  const busy = sendMutation.isPending || confirmMutation.isPending || rejectMutation.isPending;

  return (
    <div className="flex h-full min-h-0">
      {/* ستونِ تاریخچه — در پنجرهٔ شناور جمع است، در صفحهٔ کامل باز */}
      <AnimatePresence>
        {showHistory && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 220, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: EASE_SOFT }}
            className="hidden shrink-0 flex-col overflow-hidden border-e border-gray-100 md:flex"
          >
            <div className="flex items-center justify-between px-3 pt-3">
              <p className="text-xs font-bold text-gray-500">گفت‌وگوها</p>
              <button
                type="button"
                onClick={newConversation}
                className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
                aria-label="گفت‌وگوی تازه"
              >
                <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                  <path d="M10 4v12M4 10h12" />
                </svg>
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-2">
              {conversations.length === 0 && (
                <p className="px-2 py-4 text-[11px] leading-relaxed text-gray-400">
                  هنوز گفت‌وگویی ندارید. اولین پرسش، اولین گفت‌وگو را می‌سازد.
                </p>
              )}
              {conversations.map((conversation) => (
                <button
                  key={conversation.id}
                  type="button"
                  onClick={() => openConversation(conversation.id)}
                  className={`mb-1 w-full truncate rounded-xl px-3 py-2 text-start text-xs transition-colors ${
                    conversation.id === conversationId
                      ? "bg-pulse-50 font-semibold text-pulse-700"
                      : "text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  {conversation.title || "گفت‌وگوی بی‌نام"}
                </button>
              ))}
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      <section className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="flex shrink-0 items-center gap-2 border-b border-gray-100 px-4 py-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-pulse-500 to-pulse-700 text-white shadow-sm">
            <SparkIcon className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-sm font-bold text-gray-900">همکار DbsPulse</h2>
            <p className="truncate text-[11px] text-gray-400">
              {canChat ? "همان اختیارات شما، در گفت‌وگو" : "در دسترس نیست"}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowHistory((prev) => !prev)}
            className="hidden rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700 md:block"
            aria-label="تاریخچهٔ گفت‌وگوها"
            title="تاریخچهٔ گفت‌وگوها"
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              <path d="M4 5h12M4 10h9M4 15h6" />
            </svg>
          </button>
          {onExpand && (
            <button
              type="button"
              onClick={onExpand}
              className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
              aria-label="بازکردن در صفحهٔ کامل"
              title="صفحهٔ کامل"
            >
              <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 3h5v5M8 17H3v-5M17 3l-6 6M3 17l6-6" />
              </svg>
            </button>
          )}
          {onClose && (
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
          )}
        </header>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
          {status && !status.available && (
            <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-900">
              {status.reason || "همکار هنوز برای این حساب فعال نشده است."}
            </p>
          )}

          {canChat && messages.length === 0 && pendingList.length === 0 && (
            <Welcome suggestions={suggestions} tools={tools} onPick={(text) => { setDraft(text); void send(); }} />
          )}

          {uploads.map((upload) => (
            <div key={upload.id} className="flex justify-end">
              <div className="w-full max-w-[85%]">
                <UploadCard upload={upload} />
              </div>
            </div>
          ))}

          {messages.map((message) => (
            <MessageRow key={message.id} message={message} />
          ))}

          {pendingList.map((action) => (
            <div key={`pending-${action.id}`} className="flex justify-end">
              <div className="w-full max-w-[85%]">
                <PendingActionCard
                  action={action}
                  busy={busy}
                  onConfirm={(id) => confirmMutation.mutate(id)}
                  onReject={(id) => rejectMutation.mutate(id)}
                />
              </div>
            </div>
          ))}

          {sendMutation.isPending && <ThinkingIndicator />}
          {uploading && <p className="text-xs text-gray-400">در حال دریافت فایل…</p>}
          {failure && (
            <p className="rounded-xl bg-red-50 px-3 py-2 text-xs leading-relaxed text-red-700">
              {failure}
            </p>
          )}
          <div ref={endRef} />
        </div>

        <form
          className="flex shrink-0 items-end gap-2 border-t border-gray-100 p-3"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xlsm"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void uploadFile(file);
              e.target.value = "";
            }}
          />
          {canUpload && (
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={busy || uploading}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-gray-200 bg-white text-gray-500 transition-colors hover:bg-gray-50 disabled:opacity-40"
              aria-label="بارگذاری فایل اکسل"
              title="بارگذاری اکسل پرسنل"
            >
              <svg viewBox="0 0 20 20" className="h-4.5 w-4.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 13V4M6.5 7.5L10 4l3.5 3.5" />
                <path d="M4 13v2.5h12V13" />
              </svg>
            </button>
          )}
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={!canChat || busy}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
            rows={2}
            placeholder={canChat ? "بپرسید یا بخواهید… (مثلاً: قراردادهای رو به اتمام را نشانم بده)" : "همکار در دسترس نیست"}
            className="max-h-32 min-h-[44px] flex-1 resize-none rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-900 outline-none transition-colors focus:border-gray-900 focus:bg-white disabled:cursor-not-allowed disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={busy || !canChat || !draft.trim()}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-pulse-600 text-white transition-colors hover:bg-pulse-700 disabled:opacity-40"
            aria-label="ارسال"
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 3L9 11M17 3l-5 14-3-6-6-3 14-5z" />
            </svg>
          </button>
        </form>
      </section>
    </div>
  );
}

function MessageRow({ message }: { message: AiMessage }) {
  const mine = message.role === "user";
  const text = message.content.trim();

  if (!text && (message.steps ?? []).length === 0) return null;

  return (
    <div className={mine ? "flex justify-start" : "flex justify-end"}>
      <div
        className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
          mine
            ? "bg-pulse-50 text-pulse-800"
            : "border border-gray-100 bg-gray-50 text-gray-800"
        }`}
      >
        {text && <Markdown text={text} />}
        {!mine && <StepTrace steps={message.steps ?? []} />}
      </div>
    </div>
  );
}

function ThinkingIndicator() {
  return (
    <div className="flex justify-end">
      <div className="flex items-center gap-1.5 rounded-2xl border border-gray-100 bg-gray-50 px-3.5 py-3">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="h-1.5 w-1.5 rounded-full bg-gray-400"
            animate={{ opacity: [0.25, 1, 0.25] }}
            transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.18 }}
          />
        ))}
      </div>
    </div>
  );
}

function Welcome({
  suggestions,
  tools,
  onPick,
}: {
  suggestions: string[];
  tools: AiTool[];
  onPick: (text: string) => void;
}) {
  const categories = useMemo(() => {
    const counts = new Map<string, { total: number; risky: number }>();
    for (const tool of tools) {
      const entry = counts.get(tool.category) ?? { total: 0, risky: 0 };
      entry.total += 1;
      if (tool.risky) entry.risky += 1;
      counts.set(tool.category, entry);
    }
    return [...counts.entries()];
  }, [tools]);

  return (
    <div className="space-y-3 py-4">
      <div className="rounded-2xl border border-gray-100 bg-gradient-to-bl from-pulse-50/70 to-transparent px-4 py-3.5">
        <p className="text-sm font-bold text-gray-900">سلام! من همکارِ شما در DbsPulse هستم.</p>
        <p className="mt-1 text-xs leading-relaxed text-gray-500">
          می‌توانم داده‌ها را بخوانم، گزارش بسازم و فایل اکسل را بررسی و وارد کنم. هر کاری هم
          که خودتان در سامانه اجازه‌اش را نداشته باشید، از من برنمی‌آید — و برای هر تغییری،
          کارتِ تأیید می‌بینید و خودتان تصمیم می‌گیرید.
        </p>
      </div>
      {categories.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {categories.map(([category, counts]) => (
            <span
              key={category}
              className="rounded-lg bg-gray-100 px-2 py-1 text-[11px] text-gray-600"
              title={`${counts.total} ابزار${counts.risky ? ` (${counts.risky} با تأیید)` : ""}`}
            >
              {category}
              <span className="ms-1 text-gray-400">{counts.total}</span>
            </span>
          ))}
        </div>
      )}
      {suggestions.length > 0 && (
        <div className="space-y-1.5">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => onPick(suggestion)}
              className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-start text-xs text-gray-600 transition-colors hover:border-pulse-200 hover:bg-pulse-50/50 hover:text-pulse-700"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function SparkIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 20 20"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M10 2.5l1.7 4.3 4.3 1.7-4.3 1.7L10 14.5l-1.7-4.3L4 8.5l4.3-1.7L10 2.5z" />
      <path d="M15.5 13.5l.8 1.9 1.9.8-1.9.8-.8 1.9-.8-1.9-1.9-.8 1.9-.8.8-1.9z" />
    </svg>
  );
}
