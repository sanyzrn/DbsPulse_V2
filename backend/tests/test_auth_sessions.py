"""تست‌های جریان نشست/کوکی refresh و تغییر رمز.

نکته: برای اجتناب از مصرف سهمیه rate limit مسیر /login (که test_rate_limit به‌طور
انحصاری مصرفش می‌کند)، کوکی refresh مستقیماً از روی سرویس نشست ساخته می‌شود.
"""
from datetime import UTC, datetime, timedelta

from app.api.routers.auth import REFRESH_COOKIE
from app.core.security import create_refresh_token
from app.models.auth_session import AuthSession
from app.services.sessions import create_session
from tests.helpers import auth_header, make_user


def _refresh_cookie_for(db, user) -> str:
    jti = create_session(db, user.id)
    db.commit()
    return create_refresh_token(user.id, user.role.value, user.token_version, jti)


def test_refresh_with_valid_cookie_rotates_session(client, db_session):
    user = make_user(db_session, "hr")
    db_session.commit()
    token = _refresh_cookie_for(db_session, user)

    client.cookies.set(REFRESH_COOKIE, token)
    r = client.post("/api/auth/refresh")
    assert r.status_code == 200
    assert r.json()["access_token"]
    # کوکی جدید (توکن چرخیده) باید ست شده باشد و با قبلی فرق کند
    assert r.cookies.get(REFRESH_COOKIE) not in (None, token)


def test_refresh_without_cookie_fails(client, db_session):
    r = client.post("/api/auth/refresh")
    assert r.status_code == 401


def test_reused_rotated_token_after_grace_revokes_all_sessions(client, db_session):
    user = make_user(db_session, "hr")
    db_session.commit()
    old_token = _refresh_cookie_for(db_session, user)

    client.cookies.set(REFRESH_COOKIE, old_token)
    r = client.post("/api/auth/refresh")
    assert r.status_code == 200
    new_token = r.cookies.get(REFRESH_COOKIE)
    assert new_token and new_token != old_token

    # شبیه‌سازی گذشت زمان: rotated_at را به قبل از مهلت grace می‌بریم
    for session in db_session.query(AuthSession).all():
        if session.rotated_at is not None:
            session.rotated_at = datetime.now(UTC) - timedelta(minutes=5)
    db_session.commit()

    # استفاده دوباره از توکن قدیمی = سرقت → 401 و ابطال کل خانواده
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, old_token)
    assert client.post("/api/auth/refresh").status_code == 401

    # حتی توکن جدید (قربانی) هم دیگر کار نمی‌کند
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, new_token)
    assert client.post("/api/auth/refresh").status_code == 401


def test_logout_revokes_session(client, db_session):
    user = make_user(db_session, "hr")
    db_session.commit()
    token = _refresh_cookie_for(db_session, user)

    client.cookies.set(REFRESH_COOKIE, token)
    assert client.post("/api/auth/logout").status_code == 204

    client.cookies.set(REFRESH_COOKIE, token)
    assert client.post("/api/auth/refresh").status_code == 401


def test_change_password_requires_correct_current_password(client, db_session):
    user = make_user(db_session, "hr")
    db_session.commit()

    r = client.post(
        "/api/auth/change-password",
        json={"current_password": "wrong-password", "new_password": "BrandNewPass123"},
        headers=auth_header(user),
    )
    assert r.status_code == 400


def test_change_password_rotates_credentials_and_clears_flag(client, db_session):
    hr = make_user(db_session, "hr")
    user = make_user(db_session, "unit_supervisor")
    db_session.commit()

    # HR رمز را ریست می‌کند → پرچم اجبار به تغییر رمز فعال می‌شود
    r = client.patch(
        f"/api/users/{user.id}", json={"password": "TempPassword123"}, headers=auth_header(hr)
    )
    assert r.status_code == 200
    db_session.refresh(user)
    assert user.must_change_password is True

    # کاربر با رمز موقت وارد شده (توکن تازه) و رمزش را عوض می‌کند
    fresh_header = auth_header(user)
    old_header = fresh_header
    r = client.post(
        "/api/auth/change-password",
        json={"current_password": "TempPassword123", "new_password": "MyOwnSecret456"},
        headers=fresh_header,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["must_change_password"] is False

    # توکن قبلی باطل شده؛ توکن جدید پاسخ کار می‌کند
    assert client.get("/api/auth/me", headers=old_header).status_code == 401
    r = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert r.status_code == 200
    assert r.json()["must_change_password"] is False
