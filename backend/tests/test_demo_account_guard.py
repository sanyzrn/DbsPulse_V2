"""گارد استارت‌آپ: بک‌اند نباید در production با حساب دموی فعال بالا بیاید.

مایگریشن seed حالا فلگ‌دار است، ولی آن فقط جلوی محیط‌های *جدید* را می‌گیرد؛ این
گارد محیطی را می‌گیرد که قبلاً مایگریشن خورده و حساب‌ها هنوز در دیتابیس‌اند.
"""
import pytest
from sqlalchemy import select

from app.core.demo_data import DEMO_PASSWORD, DEMO_USERNAMES
from app.core.security import hash_password
from app.core.startup_checks import find_active_demo_accounts
from app.models.user import User
from tests.helpers import make_user


@pytest.fixture(autouse=True)
def _no_preexisting_demo_users(db_session):
    """نقطهٔ شروع تمیز، مستقل از این‌که دیتابیس تست قبلاً با SEED_DEMO_DATA پر شده یا نه.

    همه‌چیز داخل تراکنشی است که در پایان تست rollback می‌شود.
    """
    for user in db_session.scalars(select(User).where(User.username.in_(DEMO_USERNAMES))):
        user.is_active = False
    db_session.flush()


def _demo_user(db_session, username: str) -> User:
    """حساب دمو را می‌سازد یا اگر از قبل هست (دیتابیس تستِ seed شده) برمی‌گرداند."""
    user = db_session.scalar(select(User).where(User.username == username))
    if user is None:
        user = make_user(db_session, "hr", username=username)
    user.is_active = True
    db_session.flush()
    return user


@pytest.mark.parametrize("username", DEMO_USERNAMES)
def test_active_account_with_demo_password_is_reported(db_session, username):
    user = _demo_user(db_session, username)
    user.password_hash = hash_password(DEMO_PASSWORD)
    db_session.flush()

    assert find_active_demo_accounts(db_session) == [username]


def test_demo_username_with_changed_password_is_not_reported(db_session):
    # نام کاربری دموست ولی رمزش عوض شده — یعنی حساب واقعی است و نباید جلوی بوت را بگیرد.
    user = _demo_user(db_session, DEMO_USERNAMES[0])
    user.password_hash = hash_password("Something-Else-Entirely-42")
    db_session.flush()

    assert find_active_demo_accounts(db_session) == []


def test_deactivated_demo_account_is_not_reported(db_session):
    user = _demo_user(db_session, DEMO_USERNAMES[0])
    user.password_hash = hash_password(DEMO_PASSWORD)
    user.is_active = False
    db_session.flush()

    assert find_active_demo_accounts(db_session) == []


def test_non_demo_username_with_demo_password_is_not_scanned(db_session):
    # محدودهٔ آگاهانهٔ گارد: فقط نام‌های کاربری شناخته‌شدهٔ seed بررسی می‌شوند، چون
    # verify آرگون۲ عمداً کند است و اسکن کل جدول کاربران استارت‌آپ را کند می‌کند.
    user = make_user(db_session, "hr")
    user.password_hash = hash_password(DEMO_PASSWORD)
    db_session.flush()

    assert find_active_demo_accounts(db_session) == []


def test_several_demo_accounts_are_all_reported(db_session):
    for username in DEMO_USERNAMES[:3]:
        user = _demo_user(db_session, username)
        user.password_hash = hash_password(DEMO_PASSWORD)
    db_session.flush()

    assert find_active_demo_accounts(db_session) == sorted(DEMO_USERNAMES[:3])
