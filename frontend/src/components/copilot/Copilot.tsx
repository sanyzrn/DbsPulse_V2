import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { apiClient } from "../../api/client";
import type { AiStatus } from "../../types";
import { CopilotPanel, SparkIcon } from "./CopilotPanel";

/**
 * ورودیِ همکار: دکمهٔ شناور + پنجرهٔ کنارِ صفحه.
 *
 * «در دسترس هست یا نه» یک *حالت* است، نه یک استثنا: پیش از ساختنِ دکمه
 * پرسیده می‌شود؛ دکمه‌ای که تنها پاسخش «در دسترس نیست» باشد، از نبودنش بدتر است.
 * حالتِ «فعال ولی بدون دسترسیِ تغییر» هم دکمه دارد — فقط شکلش فرق می‌کند.
 */
export function Copilot() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  const { data: status } = useQuery({
    queryKey: ["ai", "status"],
    queryFn: async () => (await apiClient.get<AiStatus>("/ai/status")).data,
    // فعال‌سازی دستیار از پنل مدیریت یا تب دیگری باید بدون تأخیر دیده شود.
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
  });

  if (!status?.available) return null;

  return (
    <>
      <motion.button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="همکار هوشمند"
        title="همکار هوشمند"
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 0.3, duration: 0.3 }}
        className="fixed bottom-5 left-5 z-40 flex h-13 w-13 items-center justify-center rounded-full bg-gradient-to-br from-pulse-500 to-pulse-700 text-white shadow-float transition-transform hover:scale-105"
      >
        <SparkIcon className="h-5.5 w-5.5" />
        {status.allow_write_actions && (
          <span
            className="absolute -end-0.5 -top-0.5 h-3 w-3 rounded-full border-2 border-white bg-green-500"
            title="اجازهٔ پیشنهادِ تغییر دارد"
          />
        )}
      </motion.button>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-gray-900/30 backdrop-blur-[2px]"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
            />
            <motion.section
              role="dialog"
              aria-label="همکار هوشمند"
              className="fixed bottom-4 left-4 z-50 flex h-[min(680px,calc(100vh-2rem))] w-[min(560px,calc(100vw-2rem))] flex-col overflow-hidden rounded-3xl border border-gray-200 bg-white shadow-float"
              initial={{ opacity: 0, y: 24, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 16, scale: 0.98 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            >
              <CopilotPanel
                status={status}
                variant="drawer"
                onClose={() => setOpen(false)}
                onExpand={() => {
                  setOpen(false);
                  navigate("/copilot");
                }}
              />
            </motion.section>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
