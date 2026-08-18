"""آیا می‌شود روی این پورت سرور بالا آورد؟

چرا این فایل هست
----------------
راه‌انداز قبلاً پورت را این‌طور چک می‌کرد::

    s.connect_ex(("127.0.0.1", 8000))

ولی `connect` به سؤال دیگری جواب می‌دهد: «الان کسی آن‌جا گوش می‌دهد؟» — و
سؤال ما این است: «آیا *ما* می‌توانیم آن‌جا گوش بدهیم؟» روی ویندوز این دو
جواب یکی نیستند. Hyper-V و WSL2 و Docker Desktop بازه‌هایی از پورت‌ها را
برای خودشان رزرو می‌کنند (excluded port range). در آن بازه هیچ‌کس listen
نکرده — پس connect شکست می‌خورد و چک قدیمی می‌گفت «پورت آزاد است» — ولی
`bind` با خطای WSAEACCES (10013) رد می‌شود. نتیجه‌اش این بود که یووی‌کورن
در پنجرهٔ خودش بلافاصله می‌مرد، راه‌انداز ۴۰ ثانیه منتظر /api/health
می‌ماند، و پیام آخر هم چیز دقیقی نمی‌گفت.

پس این‌جا واقعاً `bind` می‌کنیم — همان کاری که یووی‌کورن می‌کند — و سه حالت
را از هم جدا نگه می‌داریم، چون راه‌حلشان سه چیز متفاوت است.

کدهای خروج
----------
۰  پورت آزاد است
۲  پورت اشغال است (یک پروسهٔ دیگر آن‌جا listen کرده)
۳  پورت رزرو/ممنوع است (بازهٔ excluded ویندوز، یا نبودِ دسترسی)
۴  خطای دیگری در bind

اجرا (از پوشهٔ backend)::

    python -m scripts.check_port --port 8000 [--host 0.0.0.0]
"""
from __future__ import annotations

import argparse
import errno
import socket
import subprocess
import sys

OK = 0
IN_USE = 2
FORBIDDEN = 3
OTHER = 4


def _show_windows_excluded_ranges() -> None:
    """بازه‌های رزروشدهٔ ویندوز را نشان بده.

    خودِ عدد ۱۰۰۱۳ برای کاربر معنایی ندارد؛ دیدن این‌که پورت ۸۰۰۰ داخل یک
    بازهٔ رزروشده افتاده، همان چیزی است که مسئله را حل می‌کند.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        result = subprocess.run(
            ["netsh", "interface", "ipv4", "show", "excludedportrange", "protocol=tcp"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return
    if result.stdout.strip():
        print(result.stdout.strip())


def check(host: str, port: int) -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # روی ویندوز SO_REUSEADDR معنایش «بگذار روی سوکتِ فعالِ دیگری هم bind کنم»
    # است، نه چیزی که روی لینوکس هست. اگر این‌جا ست شود، پورتِ واقعاً اشغال
    # هم «آزاد» گزارش می‌شود — دقیقاً برعکسِ کاری که این اسکریپت باید بکند.
    if not sys.platform.startswith("win"):
        # روی لینوکس/مک برعکس: بدون آن، سوکتِ TIME_WAIT به‌اشتباه «اشغال»
        # دیده می‌شود. یووی‌کورن هم همین گزینه را ست می‌کند.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except OSError as exc:
        win = getattr(exc, "winerror", None)
        if win == 10048 or exc.errno == errno.EADDRINUSE:
            print(f"port {port} is in use")
            return IN_USE
        if win == 10013 or exc.errno == errno.EACCES:
            print(f"port {port} is reserved or not permitted (WSAEACCES/EACCES)")
            _show_windows_excluded_ranges()
            return FORBIDDEN
        print(f"bind on {host}:{port} failed: {exc}")
        return OTHER
    finally:
        sock.close()
    return OK


def main() -> int:
    parser = argparse.ArgumentParser(description="آیا bind روی این پورت ممکن است؟")
    # پیش‌فرض همان چیزی است که یووی‌کورن با --host 0.0.0.0 می‌گیرد. تست‌کردن
    # 127.0.0.1 به‌جای آن، حالتی را جا می‌اندازد که فقط روی همهٔ رابط‌ها رد شود.
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    return check(args.host, args.port)


if __name__ == "__main__":
    raise SystemExit(main())
