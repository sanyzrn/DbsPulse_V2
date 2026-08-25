import { APP_NAME, APP_VERSION, DEVELOPER_NAME, DEVELOPER_URL } from "../appInfo";
import { BrandMark, DevMark } from "./Brand";

/** پاصفحهٔ سراسری: نام و نسخه برنامه + توسعه‌دهنده.
 *  مثل نوار بالا و ناوبری، یک قابِ گردِ جدا از لبه‌هاست تا پوستهٔ برنامه یک
 *  زبان داشته باشد. تایپوگرافی‌اش عمداً ریز و کم‌رنگ می‌ماند: این فقط یک
 *  امضاست و نباید هم‌وزنِ محتوای صفحه دیده شود. */
export function Footer() {
  return (
    <footer className="shrink-0 rounded-2xl border border-gray-200 bg-white shadow-sm">
      <div className="flex w-full flex-wrap items-center justify-between gap-2 px-4 py-3.5 text-xs text-gray-500 sm:px-6">
        <div className="flex items-center gap-2">
          <BrandMark className="h-5 w-5" />
          <span className="font-semibold text-gray-700">{APP_NAME}</span>
          <span dir="ltr" className="rounded-full bg-gray-100 px-2 py-0.5 font-mono text-[10px] font-medium text-gray-600">
            v{APP_VERSION}
          </span>
        </div>
        <a
          dir="ltr"
          href={DEVELOPER_URL}
          target="_blank"
          rel="noreferrer noopener"
          className="flex items-center gap-1.5 rounded-lg transition-colors hover:text-gray-700"
        >
          <span>Developed by {DEVELOPER_NAME}</span>
          <DevMark className="h-4 w-4" />
        </a>
      </div>
    </footer>
  );
}
