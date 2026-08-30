/** مشخصات برنامه — نام و نسخه در هدر، فوتر و صفحه ورود استفاده می‌شود.
 * نسخه را همگام با `package.json` به‌روز نگه دارید. */
export const APP_NAME = "NafasHR";
export const APP_NAME_FA = "سامانه ارزیابی عملکرد نفس زیست فارمد";
export const APP_TAGLINE =
  "مدیریت شفاف ارزیابی عملکرد؛ از ثبت شواهد تا تصمیم نهایی";
/** نسخه در زمان بیلد از `package.json` تزریق می‌شود (`vite.config.ts`).
 *  پیش از این در دو جا نوشته شده بود و باید دستی همگام می‌ماند — که نماند. */
// Keep a source-level value as well, so development sessions that keep Vite's
// configuration cache alive still show the version of this release.
export const APP_VERSION = "0.9.5";
export const DEVELOPER_NAME = "DbsStudio";

/** پرچم‌های ویژگی — برای روشن/خاموش کردن بخش‌ها بدون حذف کد.
 *
 * «دوره‌های ارزیابی» از P1-07 روشن است. سمت سرور از قبل کامل بود (ساخت دوره،
 * قانون «حداکثر یک دورهٔ باز» با ایندکس یکتای جزئی، برچسب‌خوردن خودکار پرونده‌های
 * جدید، اعلان به ارزیاب‌ها، پیشرفت و بستن) ولی پشت همین پرچم پنهان می‌ماند —
 * در حالی که README آن را به‌عنوان یک قابلیت معرفی می‌کرد و فیلتر «دورهٔ ارزیابی»
 * در گزارش‌ها همیشه خالی بود، چون هیچ دوره‌ای اصلاً قابل ساخت نبود. */
export const FEATURE_PERIODS_ENABLED = true;
