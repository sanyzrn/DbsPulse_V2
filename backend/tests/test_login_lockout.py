"""P0-04 — قفل حساب پس از تلاش‌های ناموفق پیاپی.

محدودیت نرخِ per-IP (test_rate_limit.py) لایهٔ اول است، ولی دو ضعف دارد: شمارنده‌اش
درون‌پروسه است و اصلاً per-IP است. یک مهاجم که از چند IP یا با فاصلهٔ زمانی بیشتر
روی *یک حساب مشخص* کار می‌کند، هیچ‌وقت به آن سقف نمی‌خورد. Argon2 از رمز محافظت
می‌کند، از حساب نه.

توجه: این تست‌ها عمداً از سهمیهٔ per-IP فاصله می‌گیرند (تعداد کمتر از ۱۰ در دقیقه
یا نام‌های کاربری جدا) تا با test_rate_limit.py تداخل نکنند.
"""
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import settings
from app.core.security import hash_password
from app.models.login_attempt import LoginAttempt
from app.services.login_guard import (
    clear_failures,
    locked_until,
    purge_stale,
    record_failure,
)
from tests.helpers import make_user

PASSWORD = "Correct-Horse-9"


@pytest.fixture()
def account(db_session):
    user = make_user(db_session, "hr")
    user.password_hash = hash_password(PASSWORD)
    db_session.commit()
    return user


def _fail_n_times(db_session, username: str, times: int):
    last = None
    for _ in range(times):
        last = record_failure(db_session, username)
    return last


# ------------------------------------------------------------ service level


def test_account_locks_at_the_threshold(db_session):
    username = "lock-me"

    for attempt in range(settings.login_max_failed_attempts - 1):
        assert record_failure(db_session, username) is None, f"زود قفل شد: تلاش {attempt + 1}"

    locked = record_failure(db_session, username)
    assert locked is not None
    assert locked_until(db_session, username) is not None


def test_a_successful_login_clears_the_history(db_session):
    username = "clear-me"
    _fail_n_times(db_session, username, settings.login_max_failed_attempts - 1)

    clear_failures(db_session, username)

    assert db_session.get(LoginAttempt, username) is None
    # شمارش از صفر شروع می‌شود، نه از جایی که رها شد
    assert record_failure(db_session, username) is None


def test_failures_outside_the_window_do_not_count(db_session):
    username = "stale-window"
    _fail_n_times(db_session, username, settings.login_max_failed_attempts - 1)

    row = db_session.get(LoginAttempt, username)
    row.last_failed_at = datetime.now(UTC) - timedelta(
        minutes=settings.login_attempt_window_minutes + 5
    )
    db_session.flush()

    # شکستِ کهنه نباید در قفلِ امروز نقشی داشته باشد
    assert record_failure(db_session, username) is None


def test_lock_expires_on_its_own(db_session):
    username = "expiring-lock"
    _fail_n_times(db_session, username, settings.login_max_failed_attempts)
    assert locked_until(db_session, username) is not None

    row = db_session.get(LoginAttempt, username)
    row.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    db_session.flush()

    assert locked_until(db_session, username) is None


def test_purge_removes_stale_rows_but_keeps_active_locks(db_session):
    _fail_n_times(db_session, "old-noise", 1)
    stale = db_session.get(LoginAttempt, "old-noise")
    stale.last_failed_at = datetime.now(UTC) - timedelta(
        minutes=settings.login_attempt_window_minutes + 60
    )

    _fail_n_times(db_session, "currently-locked", settings.login_max_failed_attempts)
    locked_row = db_session.get(LoginAttempt, "currently-locked")
    locked_row.last_failed_at = datetime.now(UTC) - timedelta(
        minutes=settings.login_attempt_window_minutes + 60
    )
    db_session.flush()

    purge_stale(db_session)

    assert db_session.get(LoginAttempt, "old-noise") is None
    assert db_session.get(LoginAttempt, "currently-locked") is not None


# ---------------------------------------------------------------- endpoint


def test_login_locks_the_account_and_then_refuses_even_the_right_password(
    client, db_session, account
):
    """مهم‌ترین ادعا: رمز درست هم در پنجرهٔ قفل پذیرفته نمی‌شود.

    وگرنه مهاجمی که رمز را در همان تلاشِ آخر پیدا کرده، از قفل عبور می‌کرد.
    """
    for _ in range(settings.login_max_failed_attempts):
        r = client.post(
            "/api/auth/login", json={"username": account.username, "password": "wrong"}
        )
        assert r.status_code == 401

    blocked = client.post(
        "/api/auth/login", json={"username": account.username, "password": PASSWORD}
    )
    assert blocked.status_code == 429
    assert "قفل" in blocked.json()["detail"]
    assert blocked.headers.get("Retry-After")


def test_a_correct_password_before_the_threshold_still_works_and_resets(
    client, db_session, account
):
    for _ in range(settings.login_max_failed_attempts - 1):
        client.post("/api/auth/login", json={"username": account.username, "password": "wrong"})

    ok = client.post("/api/auth/login", json={"username": account.username, "password": PASSWORD})
    assert ok.status_code == 200

    # تاریخچه پاک شده، پس یک شکست تازه دوباره قفل نمی‌کند
    client.post("/api/auth/login", json={"username": account.username, "password": "wrong"})
    still_open = client.post(
        "/api/auth/login", json={"username": account.username, "password": PASSWORD}
    )
    assert still_open.status_code == 200


def test_unknown_usernames_are_counted_too(client, db_session):
    """اگر فقط حساب‌های واقعی قفل می‌شدند، رفتار قفل به یک اوراکل «این حساب هست»
    تبدیل می‌شد."""
    ghost = "definitely-not-a-real-user"

    for _ in range(settings.login_max_failed_attempts):
        r = client.post("/api/auth/login", json={"username": ghost, "password": "wrong"})
        assert r.status_code == 401

    blocked = client.post("/api/auth/login", json={"username": ghost, "password": "wrong"})
    assert blocked.status_code == 429


def test_locking_one_account_does_not_lock_another(client, db_session, account):
    other = make_user(db_session, "hr")
    other.password_hash = hash_password(PASSWORD)
    db_session.commit()

    for _ in range(settings.login_max_failed_attempts):
        client.post("/api/auth/login", json={"username": account.username, "password": "wrong"})

    assert (
        client.post("/api/auth/login", json={"username": other.username, "password": PASSWORD}).status_code
        == 200
    )


def test_lockout_is_audited_and_hr_is_notified(client, db_session, account):
    from tests.helpers import auth_header

    hr = make_user(db_session, "hr")
    db_session.commit()

    for _ in range(settings.login_max_failed_attempts):
        client.post("/api/auth/login", json={"username": account.username, "password": "wrong"})

    events = client.get(
        "/api/audit-log", params={"event_type": "account_locked"}, headers=auth_header(hr)
    ).json()
    rows = events["items"] if isinstance(events, dict) and "items" in events else events
    assert rows, "قفل‌شدن حساب باید در گزارش رویدادها ثبت شود"

    notifications = client.get("/api/notifications", headers=auth_header(hr)).json()
    items = notifications["items"] if isinstance(notifications, dict) else notifications
    assert any("قفل" in row["message"] for row in items), "HR باید از قفل‌شدن حساب باخبر شود"
