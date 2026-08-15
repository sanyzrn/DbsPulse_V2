from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import settings
from app.db.base import Base
from app.models import *  # noqa: F401,F403  (register all models on Base.metadata)

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # هر مایگریشن تراکنش خودش را دارد، نه یک تراکنش برای کل زنجیره.
            # لازم است چون Postgres اجازه نمی‌دهد مقدار تازهٔ یک enum در همان تراکنشی
            # که اضافه شده استفاده شود (d7a2c91fb480 مقدار cancelled را اضافه می‌کند و
            # e4b8d03ca712 در predicate ایندکس از آن استفاده می‌کند).
            # ضمناً عملیاتی‌تر هم هست: اگر زنجیرهٔ بلندی وسط راه شکست بخورد،
            # مایگریشن‌های موفقِ قبلی برنمی‌گردند و از همان‌جا ادامه می‌دهید.
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
