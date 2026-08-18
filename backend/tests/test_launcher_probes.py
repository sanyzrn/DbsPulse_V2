"""دو چکِ راه‌اندازِ ویندوز، که بدون تست بی‌سروصدا از کار می‌افتند.

`scripts/check_deps.py` و `scripts/check_port.py` را setup_and_run.bat صدا
می‌زند، نه برنامه. یعنی اگر خراب شوند، هیچ تستی نمی‌شکند و تنها جایی که
معلوم می‌شود، ماشینِ تازهٔ یک نفر دیگر است — همان‌جا که کمترین امکان
عیب‌یابی وجود دارد.
"""
import re
import socket
from pathlib import Path

from scripts.check_deps import OPTIONAL, REQUIRED
from scripts.check_port import FORBIDDEN, IN_USE, OK, check

_BACKEND = Path(__file__).resolve().parents[1]
_REQUIREMENTS = _BACKEND / "requirements.txt"


def _declared_packages() -> set[str]:
    """نام بسته‌ها از requirements.txt، بدون extra و بدون قید نسخه."""
    packages = set()
    for line in _REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        packages.add(re.split(r"[\[=<>!~;]", line, maxsplit=1)[0].strip())
    return packages


def test_every_requirement_is_classified():
    """هر وابستگیِ تازه باید یا الزامی حساب شود یا صریحاً اختیاری.

    بدون این، اضافه‌شدن یک پکیج به requirements.txt از چکِ راه‌انداز جا
    می‌ماند و دقیقاً همان حالتی برمی‌گردد که check_deps برای حذفش نوشته شد:
    نشانه می‌گوید «نصب است»، ولی یک import کم است.
    """
    known = set(REQUIRED) | set(OPTIONAL)
    assert _declared_packages() - known == set()


def test_no_stale_entries():
    """و برعکس: نامی که از requirements.txt حذف شده نباید این‌جا بماند."""
    known = set(REQUIRED) | set(OPTIONAL)
    assert known - _declared_packages() == set()


def test_required_modules_all_import():
    """جدول باید نام import را درست بدهد، نه نام بسته را.

    PyJWT→jwt و argon2-cffi→argon2 و python-multipart→multipart جاهایی‌اند
    که این دو با هم فرق دارند؛ یک غلط تایپی این‌جا یعنی راه‌انداز روی یک
    venv کاملاً سالم هم شکست می‌خورد.
    """
    import importlib

    for module in REQUIRED.values():
        importlib.import_module(module)


def test_free_port_is_reported_free():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    assert check("127.0.0.1", port) == OK


def test_busy_port_is_reported_busy():
    """چکِ قبلی connect بود، نه bind.

    connect به سؤالِ «کسی آن‌جا گوش می‌دهد؟» جواب می‌دهد و ما سؤالِ «ما
    می‌توانیم گوش بدهیم؟» را داریم. روی ویندوز این دو در بازه‌های رزروشدهٔ
    Hyper-V/WSL2 از هم جدا می‌شوند: connect می‌گوید آزاد است و bind با
    WSAEACCES رد می‌شود.
    """
    with socket.socket() as taken:
        taken.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        taken.bind(("127.0.0.1", 0))
        taken.listen(1)
        port = taken.getsockname()[1]
        assert check("127.0.0.1", port) == IN_USE


def test_forbidden_and_busy_are_different_answers():
    """راه‌حلِ «پروسه را ببند» و «ویندوز پورت را رزرو کرده» یکی نیست.

    اگر هر دو یک کد بدهند، راه‌انداز کاربر را دنبال taskkill می‌فرستد برای
    پروسه‌ای که وجود ندارد.
    """
    assert IN_USE != FORBIDDEN
