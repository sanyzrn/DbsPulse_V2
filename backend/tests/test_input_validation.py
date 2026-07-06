from tests.helpers import auth_header, make_personnel, make_user


def _valid_personnel_payload(**overrides) -> dict:
    payload = {
        "personnel_code": "V-100",
        "full_name": "کارمند اعتبارسنجی",
        "job_title": "کارشناس",
        "org_unit": "واحد",
        "contract_start_date": "2025-01-01",
        "contract_end_date": "2026-01-01",
    }
    payload.update(overrides)
    return payload


def test_personnel_with_empty_fields_is_rejected(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()

    r = client.post(
        "/api/personnel",
        json=_valid_personnel_payload(full_name="   ", personnel_code=""),
        headers=auth_header(hr),
    )
    assert r.status_code == 422


def test_personnel_with_reversed_contract_dates_is_rejected(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()

    r = client.post(
        "/api/personnel",
        json=_valid_personnel_payload(
            contract_start_date="2026-01-01", contract_end_date="2025-01-01"
        ),
        headers=auth_header(hr),
    )
    assert r.status_code == 422


def test_personnel_partial_update_cannot_reverse_contract_dates(client, db_session):
    hr = make_user(db_session, "hr")
    personnel = make_personnel(db_session)  # 2025-01-01 تا 2026-01-01
    db_session.commit()

    # فقط تاریخ پایان را به قبل از شروع می‌بریم — باید رد شود
    r = client.patch(
        f"/api/personnel/{personnel.id}",
        json={"contract_end_date": "2024-06-01"},
        headers=auth_header(hr),
    )
    assert r.status_code == 400
    assert "تاریخ پایان" in r.json()["detail"]


def test_user_with_short_password_is_rejected(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()

    r = client.post(
        "/api/users",
        json={"username": "newuser1", "password": "short", "role": "unit_supervisor"},
        headers=auth_header(hr),
    )
    assert r.status_code == 422


def test_user_with_invalid_username_is_rejected(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()

    r = client.post(
        "/api/users",
        json={"username": "نام فارسی", "password": "LongEnough123", "role": "unit_supervisor"},
        headers=auth_header(hr),
    )
    assert r.status_code == 422


def test_blank_comment_is_rejected(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()

    r = client.post(
        "/api/evaluations/999999/comments",
        json={"comment_text": "   "},
        headers=auth_header(hr),
    )
    assert r.status_code == 422


def test_indicator_with_empty_category_is_rejected(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()

    r = client.post(
        "/api/indicators",
        json={"section": "general", "category": " ", "description": "شرح", "display_order": 1},
        headers=auth_header(hr),
    )
    assert r.status_code == 422
