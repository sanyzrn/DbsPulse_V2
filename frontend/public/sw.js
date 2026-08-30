/* سرویس‌ورکر NafasHR.
 *
 * دو تصمیم که همهٔ این فایل رویشان بنا شده:
 *
 * ۱. **هیچ پاسخِ /api کش نمی‌شود. هرگز.**
 *    این سامانه دادهٔ احراز هویت‌شده و حساس دارد. کش‌کردن پاسخ‌های API سه مشکل
 *    هم‌زمان می‌سازد که هیچ‌کدام قابل جبران نیست:
 *      · نمرهٔ کهنه به‌جای نمرهٔ فعلی نشان داده می‌شود، و در سامانه‌ای که خروجی‌اش
 *        تصمیم تمدید قرارداد است، «کمی قدیمی» یعنی «غلط».
 *      · دادهٔ کاربر پس از خروج روی دستگاه می‌ماند؛ روی دستگاه مشترک یعنی نشتِ
 *        اطلاعات به نفر بعدی.
 *      · CacheStorage به mount شدن روی همان مرزهای دسترسیِ برنامه پایبند نیست،
 *        پس کنترل دسترسی سرور دیگر آخرین حرف را نمی‌زند.
 *    آفلاین‌بودن این برنامه یعنی «پوستهٔ برنامه باز می‌شود و می‌گوید آفلاینی»،
 *    نه «داده‌ها را از حافظه نشانت می‌دهم».
 *
 * ۲. **دارایی‌های هش‌دار cache-first، ناوبری network-first.**
 *    Vite نام فایل‌های build را با هشِ محتوا می‌سازد، پس /assets/* عملاً تغییرناپذیر
 *    است و کش‌کردن دائمی‌اش بی‌خطر. برعکس، index.html نامش ثابت است و اگر cache-first
 *    شود کاربر برای همیشه روی نسخهٔ قدیمی می‌ماند.
 */

// با هر تغییر در استراتژی کش، این عدد را جلو ببرید تا کش قدیمی پاک شود.
const CACHE_VERSION = "nafas-hr-v1";
const SHELL_CACHE = `${CACHE_VERSION}-shell`;
const ASSET_CACHE = `${CACHE_VERSION}-assets`;

// حداقلِ لازم برای اینکه برنامه آفلاین هم *باز شود*. بقیهٔ دارایی‌ها هنگام اولین
// استفاده کش می‌شوند؛ precache کردن کل باندل، اولین بازدید را کند می‌کند.
const SHELL_URLS = ["/", "/manifest.webmanifest", "/icons/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      // یک دارایی که ۴۰۴ بدهد نباید کل نصب را بشکند
      .then((cache) => Promise.allSettled(SHELL_URLS.map((url) => cache.add(url))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => !key.startsWith(CACHE_VERSION))
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

/** آیا این درخواست هرگز نباید کش شود؟ */
function isNeverCached(url) {
  return (
    url.pathname.startsWith("/api/") ||
    // صفحهٔ تأیید اصالت سند: پاسخِ کهنه این‌جا یعنی ادعای نادرست دربارهٔ اصالت
    url.pathname.startsWith("/verify/")
  );
}

/** دارایی‌های ساخته‌شده با هشِ محتوا — تغییرناپذیر، پس cache-first امن است. */
function isImmutableAsset(url) {
  return url.pathname.startsWith("/assets/") || url.pathname.startsWith("/icons/");
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  // فقط GET. یک POST کش‌شده یعنی عملی که کاربر فکر می‌کند انجام شده و نشده.
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (isNeverCached(url)) return; // بگذار مستقیم برود؛ اصلاً دستش نمی‌زنیم

  if (isImmutableAsset(url)) {
    event.respondWith(
      caches.match(request).then(
        (hit) =>
          hit ??
          fetch(request).then((response) => {
            if (response.ok) {
              const copy = response.clone();
              caches.open(ASSET_CACHE).then((cache) => cache.put(request, copy));
            }
            return response;
          }),
      ),
    );
    return;
  }

  if (request.mode === "navigate") {
    // شبکه اول تا نسخهٔ تازه دیده شود؛ پوستهٔ کش‌شده فقط وقتی شبکه نیست.
    // بدون این، کاربر پس از هر استقرار روی نسخهٔ قدیمی گیر می‌کرد.
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(SHELL_CACHE).then((cache) => cache.put("/", copy));
          return response;
        })
        .catch(() => caches.match("/").then((hit) => hit ?? offlineResponse())),
    );
  }
});

/** اگر حتی پوسته هم کش نشده باشد (اولین بازدید، آفلاین). */
function offlineResponse() {
  return new Response(
    `<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8">
     <meta name="viewport" content="width=device-width,initial-scale=1">
     <title>آفلاین</title>
     <body style="font-family:Tahoma,sans-serif;display:grid;place-items:center;height:100vh;margin:0;color:#374151">
       <div style="text-align:center;padding:2rem">
         <h1 style="font-size:1.1rem">اتصال اینترنت برقرار نیست</h1>
         <p style="font-size:.85rem;color:#6b7280">پس از وصل‌شدن، صفحه را دوباره باز کنید.</p>
       </div>
     </body></html>`,
    { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } },
  );
}
