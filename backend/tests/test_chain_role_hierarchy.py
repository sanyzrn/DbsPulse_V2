"""مافوق می‌تواند کارِ مرحلهٔ پایین‌تر زنجیره را انجام دهد.

از ساختار واقعی یک سازمان آمد. در فایل پرسنلی که وارد شد، سه نفر از چهار ارزیاب
هم‌زمان دو جایگاه داشتند: مدیرعاملی که برای چهار نفر خودش مسئول مستقیم بود، و دو
معاونت که برای چند نفر نمره‌دهندهٔ اول بودند.

هر حساب یک نقش دارد و گاردها نقشِ *دقیق* را می‌سنجیدند، پس چنین آدمی اصلاً قابل
تنظیم نبود — نه اینکه سخت بود؛ ممکن نبود.

مرزِ این اجازه هم سنجیده می‌شود: پایین‌دست نمی‌تواند بالا برود، و منابع انسانی
اصلاً یک پله در سلسله‌مراتب نیست.
"""
from app.models.enums import EvaluationStatus, UserRole
from app.models.evaluation import EvaluationRecord
from app.models.evaluation_access import EvaluationAccess
from app.services.workflow import may_act_at
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_personnel,
    make_user,
)

# ── قاعده، به‌تنهایی ────────────────────────────────────────────────────────

def test_a_superior_may_stand_in_a_lower_stage():
    assert may_act_at(UserRole.ceo, UserRole.unit_supervisor)
    assert may_act_at(UserRole.ceo, UserRole.deputy)
    assert may_act_at(UserRole.deputy, UserRole.unit_supervisor)


def test_a_subordinate_may_not_reach_upward():
    """جهت‌دار بودنش تمام نکته است؛ بدون آن، این یک حذفِ گارد بود نه یک قاعده."""
    assert not may_act_at(UserRole.unit_supervisor, UserRole.deputy)
    assert not may_act_at(UserRole.unit_supervisor, UserRole.ceo)
    assert not may_act_at(UserRole.deputy, UserRole.ceo)


def test_hr_is_not_a_rung_on_the_ladder():
    """منابع انسانی یک وظیفهٔ جداست، نه پله‌ای در زنجیره.

    اگر مدیرعامل می‌توانست جای منابع انسانی بنشیند، تنها بررسیِ مستقلِ بیرون از
    سلسله‌مراتب هم از بین می‌رفت.
    """
    assert not may_act_at(UserRole.ceo, UserRole.hr)
    assert not may_act_at(UserRole.deputy, UserRole.hr)
    assert may_act_at(UserRole.hr, UserRole.hr)
    assert not may_act_at(UserRole.hr, UserRole.unit_supervisor)


def test_support_stands_nowhere_in_the_chain():
    for stage in (UserRole.unit_supervisor, UserRole.deputy, UserRole.ceo, UserRole.hr):
        assert not may_act_at(UserRole.support, stage)


# ── و در عمل ───────────────────────────────────────────────────────────────

def test_a_ceo_can_be_the_direct_supervisor_and_finalise(client, db_session):
    """همان حالتی که فایل واقعی داشت: مدیرعامل، مسئول مستقیمِ چند نفر."""
    hr = make_user(db_session, "hr")
    ceo = make_user(db_session, "ceo", capabilities=[])
    personnel = make_personnel(db_session)
    db_session.add(
        EvaluationAccess(
            personnel_id=personnel.id,
            unit_supervisor_user_id=ceo.id,
            deputy_user_id=None,
            ceo_user_id=ceo.id,
        )
    )
    db_session.commit()

    created = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": personnel.id},
        headers=auth_header(ceo),
    )
    assert created.status_code == 201, created.text
    record_id = created.json()["id"]

    client.put(
        f"/api/evaluations/{record_id}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(ceo),
    )
    assert client.post(
        f"/api/evaluations/{record_id}/submit", headers=auth_header(ceo)
    ).status_code == 200
    assert client.post(
        f"/api/evaluations/{record_id}/hr-approve", headers=auth_header(hr)
    ).status_code == 200
    assert client.post(
        f"/api/evaluations/{record_id}/ceo-finalize", headers=auth_header(ceo)
    ).status_code == 200

    db_session.expire_all()
    assert db_session.get(EvaluationRecord, record_id).status is EvaluationStatus.finalized


def test_being_senior_does_not_let_you_touch_someone_else_s_case(client, db_session):
    """مرزِ واقعی این تغییر.

    اجازهٔ سلسله‌مراتبی فقط می‌گوید «می‌توانی در چنین جایگاهی *نشانده شوی*». اقدام
    روی یک پروندهٔ مشخص همچنان به این بند است که در زنجیرهٔ همان پرونده نشسته
    باشی — وگرنه هر مدیرعاملی می‌توانست پروندهٔ هر کسی را امضا کند.
    """
    hr = make_user(db_session, "hr")
    supervisor = make_user(db_session, "unit_supervisor", capabilities=[])
    deputy = make_user(db_session, "deputy", capabilities=[])
    ceo = make_user(db_session, "ceo", capabilities=[])
    outsider_ceo = make_user(db_session, "ceo", capabilities=[])
    personnel = make_personnel(db_session)
    db_session.add(
        EvaluationAccess(
            personnel_id=personnel.id,
            unit_supervisor_user_id=supervisor.id,
            deputy_user_id=deputy.id,
            ceo_user_id=ceo.id,
        )
    )
    db_session.commit()

    created = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": personnel.id},
        headers=auth_header(supervisor),
    )
    assert created.status_code == 201, created.text
    record_id = created.json()["id"]

    # مدیرعاملِ بیرون از این زنجیره، با اینکه نقشش بالاترین است، رد می‌شود.
    blocked = client.post(
        f"/api/evaluations/{record_id}/submit", headers=auth_header(outsider_ceo)
    )
    assert blocked.status_code == 403, blocked.text
    assert hr is not None


def test_a_supervisor_still_cannot_finalise(client, db_session):
    hr = make_user(db_session, "hr")
    supervisor = make_user(db_session, "unit_supervisor", capabilities=[])
    ceo = make_user(db_session, "ceo", capabilities=[])
    personnel = make_personnel(db_session)
    db_session.add(
        EvaluationAccess(
            personnel_id=personnel.id,
            unit_supervisor_user_id=supervisor.id,
            deputy_user_id=None,
            ceo_user_id=ceo.id,
        )
    )
    db_session.commit()

    created = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": personnel.id},
        headers=auth_header(supervisor),
    )
    record_id = created.json()["id"]
    client.put(
        f"/api/evaluations/{record_id}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(supervisor),
    )
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(supervisor))
    client.post(f"/api/evaluations/{record_id}/hr-approve", headers=auth_header(hr))

    blocked = client.post(
        f"/api/evaluations/{record_id}/ceo-finalize", headers=auth_header(supervisor)
    )
    assert blocked.status_code == 403, blocked.text


def test_hr_can_assign_a_ceo_as_the_direct_supervisor(client, db_session):
    hr = make_user(db_session, "hr")
    ceo = make_user(db_session, "ceo", capabilities=[])
    personnel = make_personnel(db_session)
    db_session.commit()

    response = client.put(
        f"/api/personnel/{personnel.id}/access",
        json={
            "unit_supervisor_user_id": ceo.id,
            "deputy_user_id": None,
            "ceo_user_id": ceo.id,
        },
        headers=auth_header(hr),
    )
    assert response.status_code == 200, response.text
    assert response.json()["unit_supervisor_user_id"] == ceo.id


def test_a_supervisor_cannot_be_assigned_as_deputy(client, db_session):
    """جهت‌داری، در نقطهٔ تخصیص هم اعمال می‌شود."""
    hr = make_user(db_session, "hr")
    supervisor = make_user(db_session, "unit_supervisor", capabilities=[])
    ceo = make_user(db_session, "ceo", capabilities=[])
    personnel = make_personnel(db_session)
    db_session.commit()

    response = client.put(
        f"/api/personnel/{personnel.id}/access",
        json={
            "unit_supervisor_user_id": None,
            "deputy_user_id": supervisor.id,
            "ceo_user_id": ceo.id,
        },
        headers=auth_header(hr),
    )
    assert response.status_code == 400, response.text
