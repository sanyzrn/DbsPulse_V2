import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://dbspulse:dbspulse_dev_password@localhost:5432/dbspulse_test"
)
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")
# زمان‌بند در تست عمداً خاموش است: هر تست خودش جاروها را صدا می‌زند و یک حلقهٔ
# پس‌زمینه فقط نویز و ناپایداری اضافه می‌کند.
os.environ.setdefault("ENABLE_SCHEDULER", "false")
# حسابِ مدیرِ خودکار در تست‌ها ساخته نمی‌شود: دیتابیس تست مشترک است و آن حساب
# commit می‌شود، پس بین تست‌ها می‌ماند و فرضِ «هیچ مدیری نیست» را می‌شکند.
os.environ.setdefault("BOOTSTRAP_ADMIN", "false")

import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_db():
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        check=True,
    )


@pytest.fixture()
def db_session():
    from app.core.config import settings

    engine = create_engine(settings.database_url)
    connection = engine.connect()
    outer_transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = session_factory()

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()
    engine.dispose()


@pytest.fixture(autouse=True)
def _active_evaluation_period(request):
    """پیش‌فرض تست‌ها همان محیط عملیاتی است: یک بازهٔ فعال HR وجود دارد.

    تست‌های خودِ دوره این fixture را نمی‌گیرند تا ساخت/نبودن دوره را مستقل بسنجند.
    """
    if request.path.name == "test_periods.py" or "db_session" not in request.fixturenames:
        yield
        return

    from app.models.enums import PeriodStatus
    from app.models.evaluation_period import EvaluationPeriod

    db_session = request.getfixturevalue("db_session")
    today = date.today()
    db_session.add(
        EvaluationPeriod(
            name=f"دوره پیش‌فرض تست {request.node.name}",
            starts_on=today - timedelta(days=30),
            ends_on=today + timedelta(days=30),
            status=PeriodStatus.open,
        )
    )
    db_session.flush()
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """سطل محدودیت نرخِ per-IP بین تست‌ها ریست می‌شود.

    همهٔ تست‌ها از یک آدرس (testclient) درخواست می‌زنند، پس بدون این، هر تستی که به
    /api/auth/login می‌زند سهمیهٔ تست‌های بعدی را می‌سوزاند و شکست‌ها به ترتیب اجرا
    وابسته می‌شوند. تست خودِ محدودیت نرخ سالم می‌ماند چون سهمیه‌اش را در یک تست
    مصرف می‌کند.
    """
    from app.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture()
def no_cohort_suppression():
    """سرکوب کوهورت حداقلی (P1-08) را برای این تست خاموش می‌کند.

    تست‌هایی که *ریاضیِ* تجمیع را می‌سنجند با دو-سه رکورد کار می‌کنند، یعنی زیر آستانه
    می‌افتند و میانگینشان درست و حسابی سرکوب می‌شود. آن‌ها به عدد نیاز دارند، نه به
    رفتار سرکوب — رفتار سرکوب خودش در test_cohort_suppression.py تست می‌شود.
    عمداً autouse نیست: پیش‌فرض باید همان رفتار واقعی بماند.
    """
    from app.core.config import settings

    original = settings.min_cohort_size
    settings.min_cohort_size = 1
    yield
    settings.min_cohort_size = original


@pytest.fixture()
def client(db_session):
    from app.db.session import get_db
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
