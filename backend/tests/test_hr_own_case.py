"""کارمندِ منابع انسانی و پروندهٔ ارزیابیِ خودش.

سه مرحلهٔ زنجیره از قبل گارد داشتند: هیچ‌کس نمی‌تواند مسئول واحد، معاونت یا
مدیرعاملِ *خودش* باشد. مرحلهٔ منابع انسانی این گارد را نداشت — و اتفاقاً تنها
مرحله‌ای است که صاحبِ از پیش تعیین‌شده ندارد و از یک صف مشترک برداشته می‌شود.

نتیجه‌اش دقیقاً همان چیزی بود که ممیزی پیدا کرد: کارمند منابع انسانی می‌توانست
پروندهٔ خودش را از صف بردارد، تأییدش کند، لغوش کند، یا اعتراض خودش را رد کند.
همهٔ آن endpointها فقط «نقش = hr» را می‌سنجیدند و نقش، این را نمی‌گوید.
"""
import pytest

from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


@pytest.fixture()
def hr_under_review(client, db_session):
    """یک کارمند منابع انسانی که خودش هم ارزیابی می‌شود.

    این حالت عجیب نیست؛ هر کارمند HR هم پرسنل است و ارزیابی می‌شود.
    """
    person = make_personnel(db_session, full_name="کارشناس منابع انسانی", org_unit="واحد HR")
    subject_hr = make_user(db_session, "hr", personnel_id=person.id)
    other_hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo", capabilities=[])
    make_access(db_session, person, sup, dep, ceo)
    db_session.commit()

    record_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": person.id},
        headers=auth_header(sup),
    ).json()["id"]
    client.put(
        f"/api/evaluations/{record_id}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(sup),
    )
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(sup))
    return {
        "record_id": record_id,
        "subject_hr": subject_hr,
        "other_hr": other_hr,
        "sup": sup,
        "dep": dep,
        "ceo": ceo,
        "person": person,
    }


def test_they_cannot_read_their_own_case_from_the_hr_panel(client, hr_under_review):
    """پروندهٔ در جریان شواهدِ ارزیاب را دارد؛ موضوعِ پرونده نباید از این‌جا بخواندش."""
    response = client.get(
        f"/api/evaluations/{hr_under_review['record_id']}",
        headers=auth_header(hr_under_review["subject_hr"]),
    )
    assert response.status_code == 403, response.text
    assert "خودِ شما" in response.json()["detail"]


def test_they_cannot_approve_their_own_case(client, hr_under_review):
    response = client.post(
        f"/api/evaluations/{hr_under_review['record_id']}/hr-approve",
        headers=auth_header(hr_under_review["subject_hr"]),
    )
    assert response.status_code == 403, response.text


def test_they_cannot_claim_their_own_case(client, hr_under_review):
    response = client.post(
        f"/api/evaluations/{hr_under_review['record_id']}/hr-claim",
        headers=auth_header(hr_under_review["subject_hr"]),
    )
    assert response.status_code == 403, response.text


def test_they_cannot_cancel_their_own_case(client, hr_under_review):
    """لغو، خروجیِ نهاییِ یک پروندهٔ نامطلوب است — و بی‌سروصداترین راه فرار."""
    response = client.post(
        f"/api/evaluations/{hr_under_review['record_id']}/cancel",
        json={"reason": "دلخواه"},
        headers=auth_header(hr_under_review["subject_hr"]),
    )
    assert response.status_code == 403, response.text


def test_they_cannot_resolve_their_own_objection(client, db_session, hr_under_review):
    record_id = hr_under_review["record_id"]
    for step, actor in [
        ("hr-approve", hr_under_review["other_hr"]),
        ("deputy-approve", hr_under_review["dep"]),
        ("ceo-finalize", hr_under_review["ceo"]),
    ]:
        assert (
            client.post(f"/api/evaluations/{record_id}/{step}", headers=auth_header(actor)).status_code
            == 200
        )

    employee = make_user(
        db_session, "employee", personnel_id=hr_under_review["person"].id
    )
    db_session.commit()
    client.post(f"/api/evaluations/{record_id}/acknowledge", headers=auth_header(employee))
    client.post(
        f"/api/me/evaluations/{record_id}/acknowledge", headers=auth_header(employee)
    )
    client.post(
        f"/api/me/evaluations/{record_id}/object",
        json={"reason": "به این نتیجه اعتراض دارم"},
        headers=auth_header(employee),
    )

    response = client.post(
        f"/api/evaluations/{record_id}/resolve-objection",
        json={"resolution": "اعتراض خودم را رد می‌کنم"},
        headers=auth_header(hr_under_review["subject_hr"]),
    )
    assert response.status_code == 403, response.text


def test_the_case_cannot_be_handed_over_to_the_subject(client, hr_under_review):
    """گاردِ بالا از راهِ دیگر: یک HR دیگر پرونده را به خودِ او بدهد."""
    response = client.post(
        f"/api/evaluations/{hr_under_review['record_id']}/hr-handover",
        json={
            "new_hr_user_id": hr_under_review["subject_hr"].id,
            "reason": "تلاش برای دور زدن گارد",
        },
        headers=auth_header(hr_under_review["other_hr"]),
    )
    assert response.status_code == 400, response.text


def test_another_hr_user_handles_it_normally(client, hr_under_review):
    """گاردی که مسیر درست را هم ببندد، یک قفل است نه یک قاعده."""
    response = client.post(
        f"/api/evaluations/{hr_under_review['record_id']}/hr-approve",
        headers=auth_header(hr_under_review["other_hr"]),
    )
    assert response.status_code == 200, response.text


def test_they_still_see_their_own_result_through_their_own_panel(client, db_session, hr_under_review):
    """گارد دربارهٔ *رسیدگی* است، نه دربارهٔ حقِ دیدنِ نتیجهٔ خود.

    مسیر کارمند جداست و فقط نتیجهٔ نهایی را می‌دهد — بدون شواهد و کامنت‌های زنجیره.
    """
    record_id = hr_under_review["record_id"]
    client.post(f"/api/evaluations/{record_id}/hr-approve", headers=auth_header(hr_under_review["other_hr"]))
    client.post(f"/api/evaluations/{record_id}/deputy-approve", headers=auth_header(hr_under_review["dep"]))
    client.post(f"/api/evaluations/{record_id}/ceo-finalize", headers=auth_header(hr_under_review["ceo"]))

    employee = make_user(db_session, "employee", personnel_id=hr_under_review["person"].id)
    db_session.commit()
    mine = client.get("/api/me/evaluations", headers=auth_header(employee))
    assert mine.status_code == 200
    assert mine.json()["total"] == 1
