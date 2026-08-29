"""قاعده‌های سازمانی از پنل، نه از `.env`.

«مهلت اعتراض هفت روز است یا ده روز» یک تصمیم سازمانی است، ولی تا امروز
عوض‌کردنش به دسترسی SSH نیاز داشت. حالا از پنل مدیریت عوض می‌شود — با همان
سازوکاری که تنظیمات ارسال دارد: دیتابیس روی `.env` را می‌پوشاند، و تغییر
بی‌درنگ اثر می‌کند.
"""
from app.core.config import settings
from app.models.enums import Capability
from tests.helpers import auth_header, make_user


def _admin(db_session):
    user = make_user(db_session, "support", capabilities=[Capability.manage_modules])
    db_session.commit()
    return user


def test_the_capability_is_required(client, db_session):
    stranger = make_user(db_session, "hr", capabilities=[Capability.manage_users])
    db_session.commit()
    assert client.get("/api/administration/policy", headers=auth_header(stranger)).status_code == 403


def test_reads_the_value_that_actually_applies(client, db_session):
    admin = _admin(db_session)
    body = client.get("/api/administration/policy", headers=auth_header(admin)).json()
    fields = {f["key"]: f for f in body["fields"]}

    assert fields["min_cohort_size"]["value"] == settings.min_cohort_size
    # فرم باید همان قاعده‌ای را نشان بدهد که سرور اعمال می‌کند
    assert fields["min_cohort_size"]["minimum"] == 1
    assert fields["objection_window_days"]["maximum"] == 365
    assert fields["self_assessment_visible_to_hr"]["value"] is True
    assert fields["self_assessment_visible_to_unit_supervisor"]["value"] is False
    assert fields["self_assessment_visible_to_deputy"]["value"] is False
    assert fields["self_assessment_visible_to_ceo"]["value"] is False


def test_saving_takes_effect_immediately(client, db_session):
    """«ذخیره شد» نباید تا ری‌استارت بعدی دروغ باشد."""
    admin = _admin(db_session)
    original = settings.objection_window_days
    try:
        response = client.put(
            "/api/administration/policy",
            json={"values": {"objection_window_days": 21}},
            headers=auth_header(admin),
        )
        assert response.status_code == 200, response.text
        assert settings.objection_window_days == 21
        saved = {f["key"]: f["value"] for f in response.json()["fields"]}
        assert saved["objection_window_days"] == 21
    finally:
        settings.objection_window_days = original


def test_out_of_range_is_refused_by_the_server(client, db_session):
    """کف و سقف فقط در فرم نیست.

    «حداقل جمعیت = ۰» ناشناس‌ماندن را خاموش می‌کند. اگر تنها گاردش یک
    `min` در HTML باشد، یک درخواستِ مستقیم آن را دور می‌زند و هیچ‌جا خطایی
    دیده نمی‌شود.
    """
    admin = _admin(db_session)
    original = settings.min_cohort_size

    response = client.put(
        "/api/administration/policy",
        json={"values": {"min_cohort_size": 0}},
        headers=auth_header(admin),
    )

    assert response.status_code == 400
    assert "کمتر" in response.json()["detail"]
    assert settings.min_cohort_size == original


def test_self_assessment_visibility_can_be_changed_from_the_admin_panel(client, db_session):
    admin = _admin(db_session)
    original = settings.self_assessment_visible_to_deputy
    try:
        response = client.put(
            "/api/administration/policy",
            json={"values": {"self_assessment_visible_to_deputy": True}},
            headers=auth_header(admin),
        )
        assert response.status_code == 200, response.text
        assert settings.self_assessment_visible_to_deputy is True
    finally:
        settings.self_assessment_visible_to_deputy = original


def test_the_policy_form_cannot_write_integration_keys(client, db_session):
    """هر صفحه فقط کلیدهای گروه خودش را می‌نویسد."""
    admin = _admin(db_session)
    original = settings.sms_method

    response = client.put(
        "/api/administration/policy",
        json={"values": {"sms_method": "GET", "sla_reminder_days": 4}},
        headers=auth_header(admin),
    )

    assert response.status_code == 200, response.text
    assert settings.sms_method == original
    assert settings.sla_reminder_days == 4
    settings.sla_reminder_days = 3


def test_the_integration_form_cannot_write_policy_keys(client, db_session):
    """و برعکس — وگرنه فرمِ ایمیل می‌توانست مهلت اعتراض را عوض کند."""
    admin = make_user(
        db_session,
        "support",
        capabilities=[Capability.manage_integrations],
        username="int_admin",
    )
    db_session.commit()
    original = settings.objection_window_days

    response = client.put(
        "/api/administration/integrations",
        json={"values": {"objection_window_days": 99}},
        headers=auth_header(admin),
    )

    assert response.status_code == 200, response.text
    assert settings.objection_window_days == original
