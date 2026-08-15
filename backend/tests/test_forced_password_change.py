"""تغییر اجباری رمز باید در سمت سرور اعمال شود، نه فقط با ریدایرکت فرانت.

پیش از این `must_change_password` تنها در Layout.tsx بررسی می‌شد؛ یعنی کاربری که
HR رمزش را ریست کرده بود، با یک درخواست مستقیم به API (curl/Postman) کل سامانه را
بدون تغییر رمز در اختیار داشت.
"""
from app.core.security import hash_password
from tests.helpers import auth_header, make_user


def _user_who_must_change_password(db_session, role: str = "hr"):
    user = make_user(db_session, role)
    user.password_hash = hash_password("Temp-Password-1")
    user.must_change_password = True
    db_session.flush()
    return user


def test_normal_endpoint_is_blocked_until_password_is_changed(client, db_session):
    user = _user_who_must_change_password(db_session)

    r = client.get("/api/personnel", headers=auth_header(user))

    assert r.status_code == 403
    assert "رمز عبور" in r.json()["detail"]


def test_me_stays_reachable_so_the_ui_can_render(client, db_session):
    user = _user_who_must_change_password(db_session)

    r = client.get("/api/auth/me", headers=auth_header(user))

    assert r.status_code == 200
    assert r.json()["must_change_password"] is True


def test_changing_the_password_unblocks_the_rest_of_the_api(client, db_session):
    user = _user_who_must_change_password(db_session)

    r = client.post(
        "/api/auth/change-password",
        json={"current_password": "Temp-Password-1", "new_password": "A-Real-Password-9"},
        headers=auth_header(user),
    )
    assert r.status_code == 200
    assert r.json()["must_change_password"] is False

    # توکن قبلی با بالا رفتن token_version باطل شده، پس با توکن تازهٔ همین پاسخ ادامه می‌دهیم.
    fresh = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/personnel", headers=fresh).status_code == 200


def test_user_without_the_flag_is_unaffected(client, db_session):
    user = make_user(db_session, "hr")

    assert client.get("/api/personnel", headers=auth_header(user)).status_code == 200


def test_hr_password_reset_puts_the_target_behind_the_guard(client, db_session):
    hr = make_user(db_session, "hr")
    target = make_user(db_session, "unit_supervisor")
    db_session.commit()

    r = client.patch(
        f"/api/users/{target.id}",
        json={"password": "Reset-By-Hr-1"},
        headers=auth_header(hr),
    )
    assert r.status_code == 200

    db_session.refresh(target)
    assert target.must_change_password is True
    assert client.get("/api/personnel", headers=auth_header(target)).status_code == 403
