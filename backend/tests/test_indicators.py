"""تست‌های مدیریت شاخص‌ها: افزودن خودکار به انتهای ترتیب، تغییر ترتیب (drag) و حذف."""
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


def _create(client, hr, category: str, section: str = "general", display_order: int = 999):
    # display_order عمداً مقدار «اشتباه» می‌فرستیم تا ثابت شود سرور آن را نادیده می‌گیرد.
    return client.post(
        "/api/indicators",
        json={
            "section": section,
            "category": category,
            "description": "شرح",
            "display_order": display_order,
        },
        headers=auth_header(hr),
    )


def test_create_ignores_client_order_and_appends_to_end(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()

    # بیشترین ترتیب فعلی بخش general را می‌گیریم تا افزودنی‌ها بعد از آن باشند
    existing = client.get(
        "/api/indicators", params={"section": "general", "include_inactive": True}, headers=auth_header(hr)
    ).json()
    base_max = max((i["display_order"] for i in existing), default=0)

    a = _create(client, hr, "شاخص الف").json()
    b = _create(client, hr, "شاخص ب").json()
    assert a["display_order"] == base_max + 1
    assert b["display_order"] == base_max + 2


def test_reorder_persists_new_order(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()

    a = _create(client, hr, "الف", section="specialized").json()
    b = _create(client, hr, "ب", section="specialized").json()
    c = _create(client, hr, "ج", section="specialized").json()

    all_ids = [
        i["id"]
        for i in client.get(
            "/api/indicators",
            params={"section": "specialized", "include_inactive": True},
            headers=auth_header(hr),
        ).json()
    ]
    # c را به ابتدا می‌بریم، بقیه به همان ترتیب
    new_order = [c["id"]] + [i for i in all_ids if i != c["id"]]

    r = client.patch(
        "/api/indicators/reorder",
        json={"section": "specialized", "ordered_ids": new_order},
        headers=auth_header(hr),
    )
    assert r.status_code == 204, r.text

    after = client.get(
        "/api/indicators",
        params={"section": "specialized", "include_inactive": True},
        headers=auth_header(hr),
    ).json()
    assert [i["id"] for i in after] == new_order
    assert after[0]["id"] == c["id"] and after[0]["display_order"] == 1
    assert {a["id"], b["id"]}.issubset({i["id"] for i in after})


def test_reorder_rejects_mismatched_id_set(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()
    a = _create(client, hr, "الف", section="specialized").json()

    # فهرست ناقص/اضافه → ۴۰۰
    r = client.patch(
        "/api/indicators/reorder",
        json={"section": "specialized", "ordered_ids": [a["id"], 999999]},
        headers=auth_header(hr),
    )
    assert r.status_code == 400


def test_delete_unused_indicator_succeeds(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()
    ind = _create(client, hr, "قابل حذف", section="specialized").json()

    r = client.delete(f"/api/indicators/{ind['id']}", headers=auth_header(hr))
    assert r.status_code == 204, r.text

    remaining = client.get(
        "/api/indicators",
        params={"section": "specialized", "include_inactive": True},
        headers=auth_header(hr),
    ).json()
    assert ind["id"] not in {i["id"] for i in remaining}


def test_delete_scored_indicator_conflicts(client, db_session):
    """شاخصی که در یک ارزیابی امتیاز خورده قابل حذف نیست (۴۰۹) — باید غیرفعال شود."""
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    indicators = active_indicators(db_session)
    eid = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    ).json()["id"]
    client.put(
        f"/api/evaluations/{eid}/scores",
        json={"scores": full_valid_scores(indicators)},
        headers=auth_header(sup),
    )
    client.post(f"/api/evaluations/{eid}/submit", headers=auth_header(sup))

    scored_id = indicators[0].id
    r = client.delete(f"/api/indicators/{scored_id}", headers=auth_header(hr))
    assert r.status_code == 409, r.text


def test_reorder_and_delete_forbidden_for_non_hr(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    db_session.commit()
    ind = _create(client, hr, "الف", section="specialized").json()

    assert (
        client.patch(
            "/api/indicators/reorder",
            json={"section": "specialized", "ordered_ids": [ind["id"]]},
            headers=auth_header(sup),
        ).status_code
        == 403
    )
    assert client.delete(f"/api/indicators/{ind['id']}", headers=auth_header(sup)).status_code == 403
