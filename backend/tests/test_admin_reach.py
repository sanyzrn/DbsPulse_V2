"""مدیر سامانه باید بتواند سازمان را راه بیندازد.

ایراد گزارش‌شده ساده بود: «دسترسی‌های ادمین کم است». ریشه‌اش این بود که چند کارِ
راه‌اندازی به *نقش* `hr` بسته بودند، نه به مجوز — و حساب مدیر سامانه عمداً نقشی
در زنجیرهٔ ارزیابی ندارد. یعنی مجوزِ ساختِ حساب را داشت، ولی نمی‌توانست پرسنلی
ثبت کند تا آن حساب‌ها را به کسی وصل کند.

مرزِ این باز کردن هم آزموده می‌شود: مدیر سامانه همچنان **نمرهٔ هیچ‌کس را
نمی‌بیند**. اگر آن مرز برداشته شود، کل P0-03 بی‌معنا می‌شود.
"""
import pytest

from app.models.enums import Capability
from tests.helpers import auth_header, make_personnel, make_user


@pytest.fixture()
def admin(db_session):
    """همان حسابی که `scripts.create_admin` و راه‌اندازیِ خودکار می‌سازند."""
    user = make_user(db_session, "support", capabilities=list(Capability))
    db_session.commit()
    return user


def test_the_admin_can_create_every_chain_role(client, admin):
    """معاونت، مدیرعامل، منابع انسانی — همان چیزی که راه‌اندازی لازم دارد."""
    for role in ("hr", "deputy", "ceo", "unit_supervisor"):
        response = client.post(
            "/api/users",
            json={
                "username": f"new_{role}",
                "password": "Setup!Pass#2026",
                "role": role,
                "full_name": f"حساب {role}",
            },
            headers=auth_header(admin),
        )
        assert response.status_code == 201, (role, response.text)


def test_the_admin_can_register_personnel(client, admin):
    """بدون این، حساب‌هایی که ساخته به هیچ‌کس وصل نمی‌شدند."""
    response = client.post(
        "/api/personnel",
        json={
            "personnel_code": "ADM-1",
            "full_name": "کارمند تازه",
            "job_title": "کارشناس",
            "org_unit": "دفتر مرکزی / فروش",
            "contract_start_date": "2026-01-01",
            "contract_end_date": "2026-12-31",
        },
        headers=auth_header(admin),
    )
    assert response.status_code in (200, 201), response.text


def test_the_admin_can_set_an_evaluation_chain(client, db_session, admin):
    person = make_personnel(db_session, full_name="موضوع زنجیره")
    sup = make_user(db_session, "unit_supervisor")
    ceo = make_user(db_session, "ceo", capabilities=[])
    db_session.commit()

    response = client.put(
        f"/api/personnel/{person.id}/access",
        json={
            "unit_supervisor_user_id": sup.id,
            "deputy_user_id": None,
            "ceo_user_id": ceo.id,
        },
        headers=auth_header(admin),
    )
    assert response.status_code == 200, response.text


def test_the_admin_still_cannot_see_anyones_score(client, admin):
    """مرزی که این باز کردن نباید از آن رد شود.

    مدیر سامانه سامانه را نگه می‌دارد؛ لازم نیست بداند نمرهٔ کسی چند است.
    """
    for path in ("/api/dashboard/overview", "/api/evaluations"):
        assert client.get(path, headers=auth_header(admin)).status_code == 403, path


def test_a_plain_hr_user_keeps_working_without_the_new_capability(client, db_session):
    """گارد «یا نقش، یا مجوز» است — نه «فقط مجوز».

    اگر فقط مجوز می‌شد، هر کاربر منابع انسانی بدون یک ردیف تازه در جدول مجوزها
    از کارِ امروزش می‌افتاد.
    """
    hr = make_user(db_session, "hr", capabilities=[])
    db_session.commit()
    response = client.post(
        "/api/personnel",
        json={
            "personnel_code": "HR-1",
            "full_name": "کارمند منابع انسانی",
            "job_title": "کارشناس",
            "org_unit": "دفتر مرکزی / منابع انسانی",
            "contract_start_date": "2026-01-01",
            "contract_end_date": "2026-12-31",
        },
        headers=auth_header(hr),
    )
    assert response.status_code in (200, 201), response.text


def test_someone_without_role_or_capability_is_refused(client, db_session):
    """گاردی که همه را رد نکند، گارد نیست."""
    sup = make_user(db_session, "unit_supervisor", capabilities=[])
    db_session.commit()
    response = client.post(
        "/api/personnel",
        json={
            "personnel_code": "NO-1",
            "full_name": "نباید ثبت شود",
            "job_title": "کارشناس",
            "org_unit": "دفتر مرکزی / فروش",
            "contract_start_date": "2026-01-01",
            "contract_end_date": "2026-12-31",
        },
        headers=auth_header(sup),
    )
    assert response.status_code == 403, response.text


# ── حذف حساب ──────────────────────────────────────────────────────────────

def test_an_unused_account_can_be_deleted(client, db_session, admin):
    """حسابی که اشتباه ساخته شده باید واقعاً پاک شود، نه فقط خاموش."""
    victim = make_user(db_session, "deputy", username="typo_account", capabilities=[])
    db_session.commit()
    assert (
        client.delete(f"/api/users/{victim.id}", headers=auth_header(admin)).status_code == 204
    )
    assert client.get("/api/users?q=typo_account", headers=auth_header(admin)).json()["total"] == 0


def test_an_account_with_history_is_kept_and_the_message_says_why(client, db_session, admin):
    """لاگ ممیزی یک زنجیرهٔ هش است؛ پاک‌کردن یک ردیفش بقیه را غیرقابل‌اثبات می‌کند."""
    from app.services.audit import log_event

    worker = make_user(db_session, "unit_supervisor", capabilities=[])
    db_session.flush()
    log_event(db_session, actor_user_id=worker.id, event_type="login_success")
    db_session.commit()

    response = client.delete(f"/api/users/{worker.id}", headers=auth_header(admin))
    assert response.status_code == 409, response.text
    # پیام باید راهِ درست را بگوید، نه فقط «نمی‌شود».
    assert "غیرفعال" in response.json()["detail"]


def test_nobody_deletes_their_own_account(client, admin):
    response = client.delete(f"/api/users/{admin.id}", headers=auth_header(admin))
    assert response.status_code == 400, response.text
