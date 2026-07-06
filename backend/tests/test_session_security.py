from app.core.security import create_access_token
from tests.helpers import auth_header, make_user


def test_password_change_invalidates_old_access_token(client, db_session):
    hr = make_user(db_session, "hr")
    target = make_user(db_session, "unit_supervisor")
    db_session.commit()

    old_token = auth_header(target)

    # HR resets the target user's password
    r = client.patch(f"/api/users/{target.id}", json={"password": "NewPassword1!"}, headers=auth_header(hr))
    assert r.status_code == 200
    assert r.json()["id"] == target.id

    # the token issued before the reset must now be rejected
    r = client.get("/api/auth/me", headers=old_token)
    assert r.status_code == 401


def test_non_password_update_does_not_invalidate_token(client, db_session):
    hr = make_user(db_session, "hr")
    target = make_user(db_session, "unit_supervisor")
    db_session.commit()

    token = auth_header(target)

    r = client.patch(f"/api/users/{target.id}", json={"is_active": True}, headers=auth_header(hr))
    assert r.status_code == 200

    r = client.get("/api/auth/me", headers=token)
    assert r.status_code == 200


def test_token_with_stale_version_claim_is_rejected(client, db_session):
    user = make_user(db_session, "hr")
    db_session.commit()

    stale_token = create_access_token(user.id, user.role.value, user.token_version - 1)
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {stale_token}"})
    assert r.status_code == 401
