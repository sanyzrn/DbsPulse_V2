"""P2-06 — کاربر باید نشست‌های فعال خودش را ببیند و تک‌تک ببندد.

تا پیش از این تنها ابزار موجود «همه‌جا خارج شو» بود (تغییر رمز → token_version).
یعنی برای بستن یک لپ‌تاپِ گم‌شده باید همهٔ دستگاه‌های دیگر را هم از دست می‌دادی —
و پیش از آن، اصلاً راهی نبود که بفهمی چیزی باز مانده است یا نه.
"""
from sqlalchemy import select

from app.api.routers.auth import REFRESH_COOKIE
from app.core.security import create_refresh_token
from app.models.auth_session import AuthSession
from app.services.sessions import create_session
from tests.helpers import auth_header, make_user


def _login(client, user, password="Test1234!", user_agent="Mozilla/5.0 (TestDevice)"):
    return client.post(
        "/api/auth/login",
        json={"username": user.username, "password": password},
        headers={"User-Agent": user_agent},
    )


def test_a_login_shows_up_as_a_session_the_user_can_recognise(client, db_session):
    user = make_user(db_session, "hr")
    db_session.commit()

    assert _login(client, user, user_agent="Mozilla/5.0 (MyLaptop)").status_code == 200

    sessions = client.get("/api/auth/sessions", headers=auth_header(user)).json()

    assert len(sessions) == 1
    # «سه نشست فعال دارید» بی‌فایده است اگر کاربر نتواند بگوید کدام‌یک خودش است
    assert "MyLaptop" in sessions[0]["user_agent"]
    assert sessions[0]["last_used_at"] is not None


def test_each_login_is_its_own_session(client, db_session):
    user = make_user(db_session, "hr")
    db_session.commit()

    _login(client, user, user_agent="DeviceOne")
    client.cookies.clear()
    _login(client, user, user_agent="DeviceTwo")

    agents = [s["user_agent"] for s in client.get(
        "/api/auth/sessions", headers=auth_header(user)
    ).json()]
    assert len(agents) == 2
    assert {"DeviceOne", "DeviceTwo"} == set(agents)


def test_the_current_session_is_marked(client, db_session):
    """بدون این نشانه، کاربر نمی‌داند کدام ردیف را نباید ببندد."""
    user = make_user(db_session, "hr")
    db_session.commit()
    _login(client, user, user_agent="ThisBrowser")

    sessions = client.get("/api/auth/sessions", headers=auth_header(user)).json()

    current = [s for s in sessions if s["is_current"]]
    assert len(current) == 1
    assert current[0]["user_agent"] == "ThisBrowser"


def test_revoking_one_session_leaves_the_others_alone(client, db_session):
    """قلب این یافته: بستن یک دستگاه نباید به معنی خروج از همه‌جا باشد."""
    user = make_user(db_session, "hr")
    db_session.commit()
    _login(client, user, user_agent="DeviceOne")
    client.cookies.clear()
    _login(client, user, user_agent="DeviceTwo")

    sessions = client.get("/api/auth/sessions", headers=auth_header(user)).json()
    doomed = next(s for s in sessions if s["user_agent"] == "DeviceOne")

    assert (
        client.delete(
            f"/api/auth/sessions/{doomed['id']}", headers=auth_header(user)
        ).status_code
        == 204
    )

    remaining = client.get("/api/auth/sessions", headers=auth_header(user)).json()
    assert [s["user_agent"] for s in remaining] == ["DeviceTwo"]


def test_a_revoked_session_can_no_longer_refresh(client, db_session):
    """بستن نشست باید واقعاً ببندد، نه فقط از فهرست پاکش کند."""
    user = make_user(db_session, "hr")
    db_session.commit()
    jti = create_session(db_session, user.id, user_agent="Doomed")
    db_session.commit()
    row = db_session.scalar(select(AuthSession).where(AuthSession.jti == jti))

    client.delete(f"/api/auth/sessions/{row.id}", headers=auth_header(user))

    client.cookies.set(
        REFRESH_COOKIE, create_refresh_token(user.id, user.role.value, user.token_version, jti)
    )
    assert client.post("/api/auth/refresh").status_code == 401


def test_you_cannot_close_someone_elses_session(client, db_session):
    """بدون تطبیق مالکیت، حدس‌زدن یک عدد کافی بود تا کاربر دیگری را بیرون بیندازی."""
    victim = make_user(db_session, "hr")
    attacker = make_user(db_session, "unit_supervisor")
    db_session.commit()
    jti = create_session(db_session, victim.id, user_agent="VictimDevice")
    db_session.commit()
    row = db_session.scalar(select(AuthSession).where(AuthSession.jti == jti))

    assert (
        client.delete(
            f"/api/auth/sessions/{row.id}", headers=auth_header(attacker)
        ).status_code
        == 404
    )

    still_there = client.get("/api/auth/sessions", headers=auth_header(victim)).json()
    assert any(s["user_agent"] == "VictimDevice" for s in still_there)


def test_rotated_sessions_do_not_clutter_the_list(client, db_session):
    """هر refresh یک ردیف تازه می‌سازد و قبلی را «چرخیده» علامت می‌زند. اگر
    چرخیده‌ها هم نمایش داده شوند، فهرست بعد از یک روز پر از ردیف‌های مرده است."""
    user = make_user(db_session, "hr")
    db_session.commit()
    _login(client, user, user_agent="SameBrowser")

    for _ in range(3):
        assert client.post(
            "/api/auth/refresh", headers={"User-Agent": "SameBrowser"}
        ).status_code == 200

    sessions = client.get("/api/auth/sessions", headers=auth_header(user)).json()
    assert len(sessions) == 1
    # هویت دستگاه در چرخش‌ها گم نمی‌شود
    assert sessions[0]["user_agent"] == "SameBrowser"


def test_a_rotation_from_another_device_changes_what_the_list_shows(client, db_session):
    """چرخش، هویت نمایشیِ نشست را *به‌روز* می‌کند و این عمدی است.

    اگر برچسب روی مقدار زمانِ ورود قفل می‌ماند، توکنِ دزدیده‌شده‌ای که از دستگاه
    دیگری refresh می‌شود همچنان «لپ‌تاپ خودم» نشان داده می‌شد — یعنی فهرست
    نشست‌ها دقیقاً همان چیزی را پنهان می‌کرد که برای دیدنش ساخته شده است.
    """
    user = make_user(db_session, "hr")
    db_session.commit()
    _login(client, user, user_agent="MyLaptop")

    assert client.post(
        "/api/auth/refresh", headers={"User-Agent": "SomewhereElse"}
    ).status_code == 200

    sessions = client.get("/api/auth/sessions", headers=auth_header(user)).json()
    assert [s["user_agent"] for s in sessions] == ["SomewhereElse"]


def test_sessions_are_private_to_their_owner(client, db_session):
    first = make_user(db_session, "hr")
    second = make_user(db_session, "hr")
    db_session.commit()
    create_session(db_session, first.id, user_agent="FirstDevice")
    db_session.commit()

    listed = client.get("/api/auth/sessions", headers=auth_header(second)).json()

    assert all(s["user_agent"] != "FirstDevice" for s in listed)
