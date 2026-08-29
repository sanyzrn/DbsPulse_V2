"""مدل‌ها و دیتابیس باید یک چیز بگویند.

تا امروز نمی‌گفتند، و عاقبتش بد بود: ایندکس‌ها و قیدهای یکتا در مایگریشن‌ها با
`op.create_index` ساخته شده بودند و روی هیچ مدلی اعلام نشده بودند. نتیجه این بود
که `alembic revision --autogenerate` آن‌ها را «اضافی» می‌دید و برای *هر* تغییر
کوچکی، مایگریشنی پیشنهاد می‌داد که ۳۷ عملیات حذف داشت — از جمله:

* `uq_open_evaluation_per_personnel` — قانون «هر پرسنل حداکثر یک پروندهٔ باز»؛
* `uq_single_open_period` — قانون «حداکثر یک دورهٔ باز».

هر دو ایندکس یکتای جزئی‌اند و کل ایمنیِ هم‌زمانی این سامانه رویشان بنا شده:
بررسی در کد در برابر دو درخواست هم‌زمان بی‌فایده است، چون هر دو پیش از commit
اولی وضعیت را «آزاد» می‌بینند. یعنی هرکسی که یک‌بار autogenerate را اجرا می‌کرد
و خروجی را بدون خواندن می‌پذیرفت، این دو گارد را بی‌صدا حذف می‌کرد.

این تست همان اتفاق را غیرممکن می‌کند: اگر کسی ستون یا ایندکسی اضافه کند و اعلام
روی مدل را جا بیندازد، این‌جا شکست می‌خورد — نه شش ماه بعد، وسط یک مایگریشن.
"""
import warnings

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.exc import SAWarning

import app.models  # noqa: F401 — واردات مدل‌ها است که آن‌ها را در Base.metadata ثبت می‌کند
from app.db.base import Base

#: ایندکس‌هایی که *باید* در دیتابیس باشند و اگر نبودند فاجعه است. صراحتاً نام
#: برده می‌شوند تا حتی اگر روزی مقایسهٔ کلی تضعیف شد، این دو جدا سنجیده شوند.
CRITICAL_INDEXES = {
    "uq_open_evaluation_per_personnel": "evaluation_records",
    "uq_single_open_period": "evaluation_periods",
}


def _diff(connection) -> list:
    context = MigrationContext.configure(
        connection,
        opts={
            # نوع‌های Enum را نادیده نمی‌گیریم، ولی sequenceهای SERIAL را چرا —
            # Postgres خودش می‌سازدشان و در متادیتا معادلی ندارند.
            "compare_type": False,
        },
    )
    # SQLAlchemy emits this while reflecting valid PostgreSQL NOT VALID
    # constraints: the inspector returns a nested ``dialect_options`` mapping
    # that Table reflection currently treats as a dialect keyword. Keep this
    # narrowly scoped so every other schema/reflection warning remains visible.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"Can't validate argument 'dialect_options'.*",
            category=SAWarning,
        )
        return compare_metadata(context, Base.metadata)


def test_autogenerate_produces_no_changes(db_session):
    """اگر این تست بیفتد، یعنی مدل‌ها و دیتابیس از هم جدا شده‌اند.

    درست‌کردنش دو حالت دارد و *باید* بین این دو تصمیم گرفت، نه اینکه کورکورانه
    مایگریشن ساخت:

    * چیزی در دیتابیس هست که مدل نمی‌شناسد ← روی مدل اعلامش کن.
    * چیزی در مدل هست که دیتابیس ندارد ← برایش مایگریشن بنویس.
    """
    changes = _diff(db_session.connection())

    assert changes == [], (
        "مدل‌ها و شمای دیتابیس هم‌خوان نیستند. تفاوت‌ها:\n  "
        + "\n  ".join(repr(change) for change in changes)
    )


def test_the_concurrency_guards_exist_in_the_database(db_session):
    """دو ایندکس یکتای جزئی که همه‌چیز رویشان بنا شده، واقعاً در دیتابیس هستند.

    این تست عمداً از خودِ Postgres می‌پرسد، نه از متادیتای SQLAlchemy: متادیتا
    فقط می‌گوید کد چه *ادعایی* دارد.
    """
    from sqlalchemy import inspect

    inspector = inspect(db_session.connection())
    for index_name, table in CRITICAL_INDEXES.items():
        names = {index["name"] for index in inspector.get_indexes(table)}
        assert index_name in names, f"ایندکس حیاتی «{index_name}» روی {table} وجود ندارد"


def test_the_open_evaluation_guard_is_partial_and_unique(db_session):
    """جزئی *و* یکتا — هر دو لازم است.

    اگر یکتا نباشد هیچ چیزی را تضمین نمی‌کند؛ اگر جزئی نباشد، هر پرسنل فقط یک
    ارزیابی در کل تاریخش می‌تواند داشته باشد، که یعنی سامانه بعد از اولین دورهٔ
    ارزیابی از کار می‌افتد.
    """
    from sqlalchemy import text

    definition = db_session.execute(
        text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_open_evaluation_per_personnel'")
    ).scalar_one()

    assert "UNIQUE" in definition
    assert "WHERE" in definition
    assert "finalized" in definition and "cancelled" in definition
