/** ثبت و مدیریت سرویس‌ورکر (P2-04).
 *
 * سرویس‌ورکر فقط در build ثبت می‌شود. در حالت توسعه، ورکرِ کش‌کننده باعث می‌شود
 * hot reload گاهی نسخهٔ قدیمی را نشان دهد — و بدترین نوع اشکال، اشکالی است که
 * فقط روی دستگاه توسعه‌دهنده و فقط گاهی رخ می‌دهد.
 */

/** پاک‌کردن همهٔ کش‌های سرویس‌ورکر — هنگام خروج از حساب.
 *
 * پوستهٔ برنامه دادهٔ کاربر ندارد (پاسخ‌های /api اصلاً کش نمی‌شوند؛ رجوع به
 * public/sw.js)، ولی روی دستگاه مشترک «هیچ ردی نماند» چیزی است که کاربر حق دارد
 * از دکمهٔ خروج انتظار داشته باشد. این کار ارزان است و ابهام را حذف می‌کند.
 */
export async function clearAppCaches(): Promise<void> {
  if (!("caches" in window)) return;
  try {
    const keys = await caches.keys();
    await Promise.all(keys.map((key) => caches.delete(key)));
  } catch {
    // پاک‌نشدن کش نباید جلوی خروج را بگیرد؛ خروج واقعی سمت سرور انجام می‌شود.
  }
}

export function registerServiceWorker(): void {
  if (!("serviceWorker" in navigator)) return;
  if (!import.meta.env.PROD) return;

  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // نصب‌نشدن سرویس‌ورکر یعنی برنامه فقط آنلاین کار می‌کند — که حالت عادیِ
      // قبل از این تغییر بود. دلیلی برای نگران‌کردن کاربر نیست.
    });
  });

  // وقتی ورکر تازه کنترل را گرفت، یک‌بار صفحه را نو می‌کنیم تا کاربر بین
  // دارایی‌های نسخهٔ قدیم و جدید گیر نکند. محافظ `refreshing` لازم است وگرنه
  // این رویداد می‌تواند حلقهٔ بی‌پایان reload بسازد.
  let refreshing = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (refreshing) return;
    refreshing = true;
    window.location.reload();
  });
}
