"""آیکن‌های PWA را از نشان رسمی NafasHR بازتولید می‌کند.

    python frontend/public/icons/generate_icons.py

نشان منبع در ``frontend/public/brand/nafas-mark.png`` نگه‌داری می‌شود و از
لوگوی رسمی نفس زیست فارمد مشتق شده است. برای جلوگیری از فاصله‌گرفتن آیکن نصب‌شده
از هویت بصری محصول، آیکن‌ها فقط از همین فایل ساخته می‌شوند.
"""
from pathlib import Path

from PIL import Image

OUT = Path(__file__).parent
MARK = OUT.parent / "brand" / "nafas-mark.png"


def build(size: int, *, maskable: bool = False) -> Image.Image:
    icon = Image.open(MARK).convert("RGBA").resize((size, size), Image.LANCZOS)
    if not maskable:
        return icon

    background = Image.new("RGBA", (size, size), "#b71922")
    inset = round(size * 0.08)
    mark = icon.resize((size - 2 * inset, size - 2 * inset), Image.LANCZOS)
    background.alpha_composite(mark, (inset, inset))
    return background


if __name__ == "__main__":
    for name, image in (
        ("icon-192.png", build(192)),
        ("icon-512.png", build(512)),
        ("icon-maskable-512.png", build(512, maskable=True)),
        ("apple-touch-icon.png", build(180)),
    ):
        image.save(OUT / name)
        print(f"{name}  {(OUT / name).stat().st_size} bytes")
