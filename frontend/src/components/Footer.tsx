import { APP_NAME, APP_VERSION, DEVELOPER_NAME, DEVELOPER_URL } from "../appInfo";
import { BrandMark, DevMark } from "./Brand";

/** فوتر سراسری: نام و نسخه برنامه + توسعه‌دهنده.
 *  هم‌راستا با نوار بالا تمام‌عرض است و با یک خط مرزی از محتوا جدا می‌شود؛
 *  کارتِ شناورِ قبلی در انتهای هر صفحه یک بلوکِ سفیدِ برجسته می‌ساخت که
 *  به‌اندازهٔ محتوای صفحه به چشم می‌آمد، در حالی که فقط یک امضاست. */
export function Footer() {
  return (
    <footer className="border-t border-gray-200 bg-white">
      <div className="mx-auto flex w-full max-w-[1600px] flex-wrap items-center justify-between gap-2 px-4 py-4 text-xs text-gray-500 sm:px-6">
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
