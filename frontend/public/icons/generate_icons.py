"""آیکن‌های PWA را از روی رنگ برند می‌سازد.

    python frontend/public/icons/generate_icons.py

فقط به Pillow نیاز دارد که از قبل در محیط بک‌اند هست:

    backend/.venv/Scripts/python.exe frontend/public/icons/generate_icons.py

این فایل وجود دارد چون نبودنش یک‌بار هزینه داد: آیکن‌های نسخهٔ اول با گرادیان
فیروزه‌ای/بنفشِ قالب اولیه ساخته شده بودند و کسی متوجه نشد که با قرمزِ محصول
هیچ نسبتی ندارند — یعنی اپلیکیشنِ نصب‌شده روی گوشی آیکنی داشت که در هیچ‌جای
خودِ برنامه دیده نمی‌شد. آیکن‌های ساخته‌شده با دست، بی‌صدا از برند جا می‌مانند.
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).parent

#: از frontend/src/index.css — pulse-500 تا pulse-800
FROM_RGB = (0xDB, 0x1A, 0x18)
TO_RGB = (0x76, 0x0F, 0x0F)

#: موج نبض، در دستگاه مختصات ۳۲×۳۲ — همان شکلی که در favicon هست
PULSE = [(5, 17), (10, 17), (12.5, 10), (17.5, 22), (20.5, 13.5), (22, 17), (27, 17)]

#: با چه ضریبی بزرگ رسم و بعد کوچک می‌شود. Pillow آنتی‌الیاسِ خط ندارد، پس
#: تنها راهِ لبهٔ تمیز همین است.
SUPERSAMPLE = 4


def _gradient(size: int) -> Image.Image:
    """گرادیان قطری از FROM_RGB به TO_RGB."""
    base = Image.new("RGB", (size, size))
    pixels = base.load()
    assert pixels is not None
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            pixels[x, y] = tuple(
                round(a + (b - a) * t) for a, b in zip(FROM_RGB, TO_RGB, strict=True)
            )
    return base


def _rounded_mask(size: int, radius_ratio: float) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=round(size * radius_ratio), fill=255
    )
    return mask


def build(size: int, *, maskable: bool = False) -> Image.Image:
    big = size * SUPERSAMPLE
    icon = _gradient(big).convert("RGBA")

    if not maskable:
        # آیکن معمولی گوشهٔ گرد خودش را دارد؛ maskable باید تا لبه پر باشد چون
        # سیستم‌عامل خودش شکل را می‌برد.
        icon.putalpha(_rounded_mask(big, 0.22))

    # maskable: محتوا باید داخل «ناحیهٔ امن» (۸۰٪ مرکزی) بماند وگرنه برش می‌خورد.
    inset = 0.24 if maskable else 0.12
    pad = big * inset
    span = big - pad * 2
    points = [(pad + (x / 32) * span, pad + (y / 32) * span) for x, y in PULSE]

    draw = ImageDraw.Draw(icon)
    draw.line(points, fill=(255, 255, 255, 255), width=round(2.4 * span / 32), joint="curve")
    # `joint="curve"` سرِ خط را گرد نمی‌کند؛ دو سرِ باز را دستی گرد می‌کنیم.
    r = round(1.2 * span / 32)
    for x, y in (points[0], points[-1]):
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 255))

    return icon.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    for name, image in (
        ("icon-192.png", build(192)),
        ("icon-512.png", build(512)),
        ("icon-maskable-512.png", build(512, maskable=True)),
        ("apple-touch-icon.png", build(180)),
    ):
        image.save(OUT / name)
        print(f"{name}  {(OUT / name).stat().st_size} bytes")
