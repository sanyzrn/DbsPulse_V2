import { APP_NAME, APP_VERSION, DEVELOPER_NAME } from "../appInfo";
import { BrandMark, DevMark } from "./Brand";

/** فوتر سراسری: نام و نسخه برنامه + توسعه‌دهنده؛ در همه صفحات نمایش داده می‌شود. */
export function Footer() {
  return (
    <footer className="border-t border-gray-100 bg-white">
      {/* خط گرادیانت بالای فوتر */}
      <div className="h-px w-full bg-gradient-to-l from-transparent via-pulse-200 to-transparent" />
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-3 text-xs text-gray-500">
        <div className="flex items-center gap-2">
          <BrandMark className="h-5 w-5" />
          <span className="font-semibold text-gray-700">{APP_NAME}</span>
          <span
            dir="ltr"
            className="rounded-full bg-gradient-to-bl from-pulse-50 to-pulse-violet-50 px-2 py-0.5 font-mono text-[10px] font-medium text-pulse-600"
          >
            v{APP_VERSION}
          </span>
        </div>
        <div dir="ltr" className="flex items-center gap-1.5">
          <span>Developed by</span>
          <span className="font-semibold gradient-text">{DEVELOPER_NAME}</span>
          <DevMark className="h-4 w-4" />
        </div>
      </div>
    </footer>
  );
}
