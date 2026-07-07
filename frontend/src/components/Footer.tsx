import { APP_NAME, APP_VERSION, DEVELOPER_NAME } from "../appInfo";
import { BrandMark, DevMark } from "./Brand";

/** فوتر سراسری: نام و نسخه برنامه + توسعه‌دهنده؛ کارت شناور مشابه هدر، در همه صفحات. */
export function Footer() {
  return (
    <footer className="mt-6 flex flex-wrap items-center justify-between gap-2 rounded-3xl border border-gray-100 bg-white px-5 py-3.5 text-xs text-gray-500 shadow-float">
      <div className="flex items-center gap-2">
        <BrandMark className="h-5 w-5" />
        <span className="font-semibold text-gray-700">{APP_NAME}</span>
        <span dir="ltr" className="rounded-full bg-pulse-50 px-2 py-0.5 font-mono text-[10px] font-medium text-pulse-600">
          v{APP_VERSION}
        </span>
      </div>
      <div dir="ltr" className="flex items-center gap-1.5">
        <span>Developed by</span>
        <span className="font-semibold text-pulse-700">{DEVELOPER_NAME}</span>
        <DevMark className="h-4 w-4" />
      </div>
    </footer>
  );
}
