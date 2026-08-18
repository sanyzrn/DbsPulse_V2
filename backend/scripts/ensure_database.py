"""ساخت نقش و دیتابیس محلی، اگر هنوز وجود نداشته باشند.

چرا این فایل هست
----------------
تا پیش از این، وقتی روی یک ویندوزِ تازه دیتابیس ساخته نشده بود، اسکریپت راه‌انداز
با پیام «این دستورها را اجرا کن» متوقف می‌شد:

    psql -U postgres -c "CREATE ROLE dbspulse ..."

ولی نصب‌کنندهٔ رسمی PostgreSQL روی ویندوز مسیر bin را به PATH اضافه نمی‌کند، پس
همان دستور با «'psql' is not recognized» شکست می‌خورد. یعنی کاربر برای رفع خطا،
دستوری را تحویل می‌گرفت که خودش هم اجرا نمی‌شد — و عملاً همان‌جا گیر می‌کرد.

راه‌حل این است که اصلاً سراغ psql نرویم: تا این مرحله venv ساخته شده و psycopg
داخلش نصب است، پس می‌شود مستقیم با خودِ درایور به سرور وصل شد و نقش/دیتابیس را
ساخت. این‌طور نه به PATH وابسته‌ایم و نه به نصب ابزار جانبی.

رفتار
-----
۱. اول با همان DATABASE_URL برنامه وصل می‌شود. اگر جواب داد، کاری لازم نیست.
۲. اگر نداد، به‌عنوان کاربر ادمین (پیش‌فرض: postgres) وصل می‌شود و هرچه کم است
   می‌سازد: نقش، دیتابیس، و دسترسی‌های لازم.
۳. اگر ورود ادمین هم ممکن نبود، با کد خروج مشخص و پیام فارسی برمی‌گردد تا
   راه‌انداز بتواند دقیقاً همان چیزی را بگوید که کاربر باید انجام دهد.

کدهای خروج
----------
۰  دیتابیس آماده است (از قبل بود یا همین حالا ساخته شد)
۲  سرور در دسترس نیست
۳  ورود با کاربر ادمین ممکن نشد (رمز لازم است یا اشتباه است)
۴  وصل شدیم ولی ساخت با خطا مواجه شد (مثلاً دسترسی کافی نبود)

اجرا (از پوشهٔ backend):

    python -m scripts.ensure_database [--admin-user postgres] [--admin-password ...]
"""
from __future__ import annotations

import argparse
import sys
from urllib.parse import unquote, urlparse

try:
    import psycopg
    from psycopg import sql as pgsql
except ModuleNotFoundError:  # pragma: no cover - فقط وقتی venv ناقص است
    print("psycopg نصب نیست. اول وابستگی‌های بک‌اند را نصب کنید.", file=sys.stderr)
    raise SystemExit(4) from None


# کدهای خروج، به‌جای عددِ لخت در جای‌جای فایل.
OK = 0
SERVER_UNREACHABLE = 2
ADMIN_LOGIN_FAILED = 3
CREATE_FAILED = 4


class Target:
    """اجزای DATABASE_URL که برای ساخت لازم‌اند."""

    def __init__(self, url: str) -> None:
        # SQLAlchemy از postgresql+psycopg:// استفاده می‌کند؛ urlparse با آن
        # مشکلی ندارد ولی psycopg خودش این پیشوند را نمی‌شناسد.
        parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://", 1))
        if parsed.scheme not in {"postgresql", "postgres"}:
            raise ValueError(f"DATABASE_URL پشتیبانی‌نشده: {url}")
        self.user = unquote(parsed.username or "postgres")
        self.password = unquote(parsed.password or "")
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 5432
        self.database = (parsed.path or "/").lstrip("/") or "postgres"


def _connect(*, user: str, password: str, host: str, port: int, dbname: str):
    # رمز خالی را عمداً پاس نمی‌دهیم: در آن حالت libpq سراغ PGPASSWORD و فایل
    # pgpass می‌رود. راه‌انداز از همین استفاده می‌کند تا رمز ادمین در خط فرمان
    # (و در نتیجه در فهرست پروسه‌ها) ظاهر نشود.
    optional = {"password": password} if password else {}
    return psycopg.connect(
        user=user, host=host, port=port, dbname=dbname, connect_timeout=5, **optional
    )


def _app_connection_works(target: Target) -> bool:
    try:
        with _connect(
            user=target.user,
            password=target.password,
            host=target.host,
            port=target.port,
            dbname=target.database,
        ):
            return True
    except psycopg.OperationalError:
        return False


def _server_is_up(target: Target, admin_user: str, admin_password: str) -> bool:
    """آیا اصلاً سروری آن‌جا هست؟

    تفاوت «سرور بالا نیست» و «رمز غلط است» را نگه می‌داریم، چون راه‌حلشان یکی
    نیست و پیام درهم، کاربر را دنبال نخود سیاه می‌فرستد.
    """
    for user, password in ((admin_user, admin_password), (target.user, target.password)):
        try:
            with _connect(
                user=user,
                password=password,
                host=target.host,
                port=target.port,
                dbname="postgres",
            ):
                return True
        except psycopg.OperationalError as exc:
            # پیام احراز هویت یعنی سرور جواب داده — پس بالاست.
            if "authentication" in str(exc).lower() or "password" in str(exc).lower():
                return True
    return False


def _provision(target: Target, admin_user: str, admin_password: str) -> int:
    try:
        conn = _connect(
            user=admin_user,
            password=admin_password,
            host=target.host,
            port=target.port,
            dbname="postgres",
        )
    except psycopg.OperationalError as exc:
        message = str(exc).lower()
        if "authentication" in message or "password" in message:
            return ADMIN_LOGIN_FAILED
        return SERVER_UNREACHABLE if not _server_is_up(target, admin_user, admin_password) else ADMIN_LOGIN_FAILED

    # CREATE DATABASE داخل تراکنش اجرا نمی‌شود.
    conn.autocommit = True
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (target.user,))
            if cur.fetchone() is None:
                # شناسه‌ها را نمی‌شود پارامتری داد؛ با psycopg.sql امن نقل‌قول می‌شوند.
                cur.execute(
                    pgsql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                        pgsql.Identifier(target.user),
                        pgsql.Literal(target.password),
                    )
                )
                print(f"    نقش «{target.user}» ساخته شد")
            else:
                print(f"    نقش «{target.user}» از قبل وجود دارد")

            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target.database,))
            if cur.fetchone() is None:
                cur.execute(
                    pgsql.SQL("CREATE DATABASE {} OWNER {}").format(
                        pgsql.Identifier(target.database),
                        pgsql.Identifier(target.user),
                    )
                )
                print(f"    دیتابیس «{target.database}» ساخته شد")
            else:
                print(f"    دیتابیس «{target.database}» از قبل وجود دارد")
    except psycopg.Error as exc:
        print(f"    ساخت با خطا مواجه شد: {exc}", file=sys.stderr)
        return CREATE_FAILED
    finally:
        conn.close()

    # روی PostgreSQL 15 به بعد، CREATE روی schema عمومی به‌صورت پیش‌فرض برای
    # کاربر غیرمالک بسته است؛ بدون این، مایگریشن اول با «permission denied for
    # schema public» می‌شکند — خطایی که ربطش به مالکیت schema اصلاً واضح نیست.
    try:
        with _connect(
            user=admin_user,
            password=admin_password,
            host=target.host,
            port=target.port,
            dbname=target.database,
        ) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    pgsql.SQL("ALTER SCHEMA public OWNER TO {}").format(
                        pgsql.Identifier(target.user)
                    )
                )
    except psycopg.Error as exc:
        # مالکیت schema برای نصب‌های قدیمی‌تر لازم نیست؛ اگر نشد، بگذار مایگریشن
        # خودش قضاوت کند تا این‌جا بی‌دلیل کل راه‌اندازی را متوقف نکنیم.
        print(f"    (هشدار) تنظیم مالکیت schema انجام نشد: {exc}")

    return OK


def main() -> int:
    parser = argparse.ArgumentParser(description="ساخت نقش/دیتابیس محلی در صورت نبود")
    parser.add_argument("--admin-user", default="postgres")
    parser.add_argument("--admin-password", default="")
    parser.add_argument(
        "--database-url",
        default=None,
        help="پیش‌فرض: همان DATABASE_URL تنظیمات برنامه",
    )
    args = parser.parse_args()

    url = args.database_url
    if url is None:
        from app.core.config import settings

        url = settings.database_url

    target = Target(url)

    if _app_connection_works(target):
        print(f"    اتصال با کاربر «{target.user}» برقرار است — نیازی به ساخت نیست")
        return OK

    if not _server_is_up(target, args.admin_user, args.admin_password):
        return SERVER_UNREACHABLE

    return _provision(target, args.admin_user, args.admin_password)


if __name__ == "__main__":
    raise SystemExit(main())
