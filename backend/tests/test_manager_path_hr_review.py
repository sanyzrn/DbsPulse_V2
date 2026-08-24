"""مسیر «مدیر» هم مرحلهٔ بررسی منابع انسانی دارد.

تا پیش از این نداشت: پروندهٔ پرسنلِ «مدیر» مستقیماً در `hr_approved` ساخته
می‌شد، معاونت نمره می‌داد و **خودش همان نمره را تأیید می‌کرد** و پرونده می‌رفت
روی میز مدیرعامل. مرحلهٔ `submitted` — بررسی منابع انسانی — در این مسیر هرگز رخ
نمی‌داد.

یعنی پروندهٔ مدیران، پرامدترین ارزیابی‌های سازمان، با دو چشم بسته می‌شد در حالی
که پروندهٔ یک کارشناس با چهار. برعکسِ چیزی که باید باشد.

نکتهٔ ظریفِ مسیر تازه این است که مرحلهٔ معاونت **پریده** می‌شود، نه اینکه دوباره
لازم شود: معاونت نمره‌اش را داده، پس تأیید منابع انسانی مستقیماً پرونده را روی
میز مدیرعامل می‌گذارد. قرینهٔ همان منطقی که برای زنجیرهٔ بی‌معاونت داریم.
"""
import pytest

from app.models.enums import EvaluationStatus
from app.models.notification import Notification
from sqlalchemy import select
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


@pytest.fixture()
def manager_case(client, db_session):
    hr = make_user(db_session, "hr")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo", capabilities=[])
    manager = make_personnel(
        db_session, full_name="یک مدیر واحد", job_title="مدیر", is_manager=True
    )
    make_access(db_session, manager, None, dep, ceo)
    db_session.commit()

    record_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": manager.id},
        headers=auth_header(dep),
    ).json()["id"]
    client.put(
        f"/api/evaluations/{record_id}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(dep),
    )
    return {"record_id": record_id, "hr": hr, "dep": dep, "ceo": ceo, "manager": manager}


def test_the_deputy_cannot_reach_the_ceo_without_hr(client, manager_case):
    """قلبِ ماجرا: نمره‌دهنده نمی‌تواند پرونده را خودش از بررسی HR عبور دهد."""
    record_id = manager_case["record_id"]
    submitted = client.post(
        f"/api/evaluations/{record_id}/submit", headers=auth_header(manager_case["dep"])
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"

    # و تأییدِ خودش هم جایی ندارد
    assert (
        client.post(
            f"/api/evaluations/{record_id}/deputy-approve",
            headers=auth_header(manager_case["dep"]),
        ).status_code
        == 403
    )
    # مدیرعامل هم نمی‌تواند از روی مرحلهٔ HR رد شود
    assert (
        client.post(
            f"/api/evaluations/{record_id}/ceo-finalize",
            headers=auth_header(manager_case["ceo"]),
        ).status_code
        in (400, 403)
    )


def test_hr_approval_hands_it_straight_to_the_ceo(client, manager_case):
    """مرحلهٔ معاونت پریده می‌شود چون *انجام شده*، نه چون وجود ندارد."""
    record_id = manager_case["record_id"]
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(manager_case["dep"]))
    approved = client.post(
        f"/api/evaluations/{record_id}/hr-approve", headers=auth_header(manager_case["hr"])
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "deputy_approved"
    assert approved.json()["stage"] == "ceo_final"

    finalized = client.post(
        f"/api/evaluations/{record_id}/ceo-finalize", headers=auth_header(manager_case["ceo"])
    )
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["status"] == "finalized"


def test_the_result_is_computed_when_the_deputy_submits(client, manager_case):
    """محاسبه جای درستش را عوض کرد: پایانِ نمره‌دهی، نه تأیید معاونت."""
    record_id = manager_case["record_id"]
    result = client.post(
        f"/api/evaluations/{record_id}/submit", headers=auth_header(manager_case["dep"])
    ).json()
    assert result["final_weighted_pct"] is not None
    assert result["base_weighted_pct"] is not None


def test_hr_can_return_it_and_the_deputy_is_told(client, db_session, manager_case):
    """برگشتِ HR در این مسیر به هیچ‌کس اعلان نمی‌داد.

    گیرندهٔ اعلان `unit_supervisor_user_id` بود، که در این مسیر خالی است — پس
    پرونده به `draft` برمی‌گشت و معاونت هیچ‌وقت نمی‌فهمید.
    """
    record_id = manager_case["record_id"]
    dep = manager_case["dep"]
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(dep))
    returned = client.post(
        f"/api/evaluations/{record_id}/return",
        json={"reason": "شواهد شاخص سوم کافی نیست"},
        headers=auth_header(manager_case["hr"]),
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["status"] == "draft"

    told = db_session.scalars(
        select(Notification).where(
            Notification.user_id == dep.id,
            Notification.evaluation_record_id == record_id,
            Notification.type == "workflow_hr_return",
        )
    ).all()
    assert told, "معاونت باید بفهمد پرونده‌اش برگشته"


def test_a_ceo_return_goes_back_to_hr_not_to_a_stage_that_is_done(client, manager_case):
    """برگشت مدیرعامل نباید پرونده را به مرحله‌ای بفرستد که مصرف شده.

    وگرنه پرونده در `hr_approved` می‌نشست و معاونت باید یک تأییدِ توخالی می‌زد.
    """
    record_id = manager_case["record_id"]
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(manager_case["dep"]))
    client.post(f"/api/evaluations/{record_id}/hr-approve", headers=auth_header(manager_case["hr"]))

    returned = client.post(
        f"/api/evaluations/{record_id}/return",
        json={"reason": "نتیجه با شناختِ من از این مدیر نمی‌خواند"},
        headers=auth_header(manager_case["ceo"]),
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["status"] == EvaluationStatus.submitted.value


def test_the_ordinary_path_is_untouched(client, db_session):
    """چهار مرحلهٔ مسیر عادی باید دقیقاً همان چهار مرحله بماند."""
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo", capabilities=[])
    person = make_personnel(db_session, full_name="کارشناس عادی")
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
    statuses = []
    for step, actor in [
        ("submit", sup),
        ("hr-approve", hr),
        ("deputy-approve", dep),
        ("ceo-finalize", ceo),
    ]:
        response = client.post(
            f"/api/evaluations/{record_id}/{step}", headers=auth_header(actor)
        )
        assert response.status_code == 200, (step, response.text)
        statuses.append(response.json()["status"])

    assert statuses == ["submitted", "hr_approved", "deputy_approved", "finalized"]
