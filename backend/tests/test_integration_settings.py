"""تنظیمات ارسال بیرونی: چه چیزی از پنل عوض می‌شود و چه چیزی نه.

موتور ارسال از قبل کامل بود؛ چیزی که نبود، جایی برای *وارد کردن* تنظیماتش جز
`.env` روی سرور. ولی بردنِ همه‌چیز به دیتابیس هم درست نیست: رمز و کلید API اگر
آن‌جا بنشینند در هر بک‌آپی هم می‌نشینند، و بک‌آپ دیتابیس معمولاً جاهایی می‌رود
که `.env` نمی‌رود.
"""
from app.core.config import settings
from app.models.enums import Capability
from tests.helpers import auth_header, make_user


def _admin(db_session):
    user = make_user(db_session, "support", capabilities=[Capability.manage_integrations])
    db_session.commit()
    return user


def test_the_capability_is_required(client, db_session):
    stranger = make_user(db_session, "hr", capabilities=[Capability.manage_users])
    db_session.commit()
    assert client.get("/api/administration/integrations", headers=auth_header(stranger)).status_code == 403


def test_secrets_are_never_returned(client, db_session):
    """صفحه می‌گوید «تنظیم شده»، نه اینکه چه چیزی تنظیم شده.

    این تست روی *نبودِ* داده ادعا می‌کند، که همان چیزی است که به‌سادگی از قلم
    می‌افتد: افزودن مقدار به پاسخ، هیچ تستی را نمی‌شکند مگر این یکی.
    """
    admin = _admin(db_session)
    body = client.get("/api/administration/integrations", headers=auth_header(admin)).json()

    secret_keys = {s["key"] for s in body["secrets"]}
    assert "sms_api_key" in secret_keys
    assert "smtp_password" in secret_keys
    for secret in body["secrets"]:
        assert set(secret) == {"key", "label", "configured"}
    # و در بخش قابل ویرایش هم نباید ردی از رمز باشد
    assert not (secret_keys & {field["key"] for field in body["fields"]})


def test_saving_takes_effect_immediately(client, db_session):
    """«ذخیره شد» نباید تا ری‌استارت بعدی دروغ باشد."""
    admin = _admin(db_session)
    original = settings.sms_method
    try:
        response = client.put(
            "/api/administration/integrations",
            json={"values": {"sms_method": "GET"}},
            headers=auth_header(admin),
        )
        assert response.status_code == 200, response.text
        assert settings.sms_method == "GET"
        saved = {f["key"]: f["value"] for f in response.json()["fields"]}
        assert saved["sms_method"] == "GET"
    finally:
        settings.sms_method = original


def test_unknown_keys_cannot_reach_settings(client, db_session):
    """قلبِ امنیتیِ این بخش.

    بدون allowlist، یک کلید دلخواه در بدنهٔ درخواست هر صفتی از `settings` را
    بازنویسی می‌کرد — از جمله `database_url` و `jwt_secret_key`.
    """
    admin = _admin(db_session)
    before = settings.jwt_secret_key

    response = client.put(
        "/api/administration/integrations",
        json={"values": {"jwt_secret_key": "hijacked", "database_url": "postgresql://x/y"}},
        headers=auth_header(admin),
    )
    assert response.status_code == 200, response.text
    assert settings.jwt_secret_key == before


def test_testing_an_unconfigured_channel_reports_instead_of_crashing(client, db_session):
    admin = _admin(db_session)
    response = client.post(
        "/api/administration/integrations/test",
        json={"channel": "sms", "recipient": "09120000000"},
        headers=auth_header(admin),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # در محیط تست هیچ سرویسی تنظیم نشده، پس باید مؤدبانه بگوید، نه ۵۰۰ بدهد.
    assert body["ok"] is False
    assert body["detail"]


def test_unknown_channel_is_rejected(client, db_session):
    admin = _admin(db_session)
    response = client.post(
        "/api/administration/integrations/test",
        json={"channel": "carrier_pigeon", "recipient": "x"},
        headers=auth_header(admin),
    )
    assert response.status_code == 400, response.text
