import { useCallback, useLayoutEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";

/** فاصلهٔ پاپ‌آور از دکمه‌اش، و حاشیهٔ امنِ لبهٔ صفحه. */
const GAP = 6;
const EDGE = 8;

/**
 * موقعیت‌دهیِ یک پاپ‌آور نسبت به دکمه‌اش، بیرون از جریانِ صفحه.
 *
 * مسئله‌ای که حل می‌کند
 * ---------------------
 * پاپ‌آورها `absolute` بودند، یعنی داخلِ همان درختی می‌ماندند که دکمه در آن است.
 * هر جدی که `overflow` غیرِ `visible` داشت آن‌ها را می‌بُرید — و در این پروژه
 * دقیقاً همین اتفاق افتاده بود: نوارِ فیلترها با انیمیشنِ باز/بستهٔ ارتفاع کار
 * می‌کند و برای آن انیمیشن `overflow-hidden` لازم دارد. نتیجه این بود که تقویم
 * از لبهٔ پایینِ نوارِ فیلتر بریده می‌شد؛ نیمهٔ پایینش نه دیده می‌شد و نه کلیک
 * می‌گرفت (`elementFromPoint` روی آن ناحیه، `main` را برمی‌گرداند نه تقویم را).
 *
 * بالابردنِ `z-index` این را درست نمی‌کند: بریدگیِ `overflow` ربطی به لایه‌بندی
 * ندارد. تنها راهِ قطعی این است که پاپ‌آور اصلاً فرزندِ آن ظرف نباشد.
 *
 * پس مثل `ui/Modal.tsx`، پاپ‌آور با `createPortal` روی `body` می‌رود و با
 * `position: fixed` سرِ جای دکمه‌اش می‌نشیند. این هم بریدگی را حذف می‌کند و هم
 * وابستگی به بافتِ لایه‌بندیِ جدها را.
 *
 * چند نکتهٔ رفتاری
 * ----------------
 * * اگر پایینِ صفحه جا نباشد، بالای دکمه باز می‌شود.
 * * تا وقتی اندازه‌اش سنجیده نشده `visibility: hidden` است، تا یک فریم در جای
 *   غلط دیده نشود.
 * * با اسکرول و تغییرِ اندازهٔ پنجره دوباره جای‌گذاری می‌شود. `scroll` را در فازِ
 *   capture می‌گیریم چون اسکرول ممکن است داخلِ یک ظرفِ داخلی رخ دهد و به
 *   `window` حباب نکند.
 */
export function useAnchoredPopover<A extends HTMLElement, P extends HTMLElement>(
  open: boolean,
  { matchAnchorWidth = false }: { matchAnchorWidth?: boolean } = {}
) {
  const anchorRef = useRef<A>(null);
  const popoverRef = useRef<P>(null);
  const [style, setStyle] = useState<CSSProperties>({
    position: "fixed",
    top: 0,
    left: 0,
    visibility: "hidden",
  });

  const place = useCallback(() => {
    const anchor = anchorRef.current;
    if (!anchor) return;
    const a = anchor.getBoundingClientRect();
    const p = popoverRef.current?.getBoundingClientRect();
    const height = p?.height ?? 0;
    const width = matchAnchorWidth ? a.width : (p?.width ?? 0);

    // پایین، مگر آن‌که جا نباشد و بالا جا باشد.
    const below = a.bottom + GAP;
    const above = a.top - GAP - height;
    const fitsBelow = below + height <= window.innerHeight - EDGE;
    const top = fitsBelow || above < EDGE ? below : above;

    // راست‌چین: لبهٔ راستِ پاپ‌آور با لبهٔ راستِ دکمه یکی می‌شود.
    const rawLeft = matchAnchorWidth ? a.left : a.right - width;
    const left = Math.min(Math.max(EDGE, rawLeft), Math.max(EDGE, window.innerWidth - width - EDGE));

    setStyle({
      position: "fixed",
      top: Math.min(Math.max(EDGE, top), Math.max(EDGE, window.innerHeight - height - EDGE)),
      left,
      ...(matchAnchorWidth ? { width: a.width } : null),
      visibility: "visible",
    });
  }, [matchAnchorWidth]);

  useLayoutEffect(() => {
    if (!open) {
      setStyle((s) => (s.visibility === "hidden" ? s : { ...s, visibility: "hidden" }));
      return;
    }
    place();
    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
    };
  }, [open, place]);

  /** آیا این گره داخلِ پاپ‌آور است؟
   *
   * چون پاپ‌آور پورتال است، تشخیصِ «کلیکِ بیرون» دیگر با `contains` روی ریشهٔ
   * کامپوننت کامل نیست. این را هوک می‌دهد تا فراخوان مجبور نباشد `.current` را
   * داخلِ افکت بخواند (و لینتر هم به‌درستی از وابستگی‌های ناپایدار شکایت نکند).
   */
  const containsNode = useCallback(
    (node: Node) => !!popoverRef.current?.contains(node),
    []
  );

  return { anchorRef, popoverRef, style, containsNode, reposition: place };
}
