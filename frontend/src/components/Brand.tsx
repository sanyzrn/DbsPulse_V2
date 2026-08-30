/** نشانِ NafasHR، مشتق‌شده از هویت بصری رسمی نفس زیست فارمد. */

export function BrandMark({ className = "h-9 w-9" }: { className?: string }) {
  return (
    <img
      src="/brand/nafas-mark.png"
      alt=""
      aria-hidden="true"
      className={`${className} object-contain`}
      decoding="async"
    />
  );
}
