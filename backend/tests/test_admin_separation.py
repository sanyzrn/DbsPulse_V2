"""تفکیک اختیارات مدیر سامانه از کارِ روزمرهٔ منابع انسانی.

دو چیز که تا امروز یکی بودند و این فایل جدا نگهشان می‌دارد:

۱. **«حساب می‌سازم» و «اختیار می‌دهم».** وقتی یک مجوز بودند، هرکس می‌توانست
   حساب بسازد می‌توانست به خودش هم هر اختیاری بدهد — یعنی تفکیک وظایف با یک
   کلیک از بین می‌رفت و هیچ‌جا ثبت نمی‌شد که از بین رفته.

۲. **خواندن لاگ ممیزی و نقش `hr`.** دسترسی به کامل‌ترین ردِ تصمیم‌ها به کسی گره
   خورده بود که خودش در زنجیرهٔ تصمیم می‌ایستد. گرفتنش از او هیچ راهی نداشت جز
   عوض‌کردن نقشش، و دادنش به کس دیگر اصلاً ممکن نبود.
"""
from app.models.enums import Capability
from tests.helpers import auth_header, make_user

#: همان چیزی که منابع انسانی پس از تفکیک دارد: کارِ خودش، بدون اختیارات سامانه.
HR_AFTER_SEPARATION = [Capability.manage_users, Capability.manage_scoring]


def _hr(db_session):
    user = make_user(db_session, "hr", capabilities=HR_AFTER_SEPARATION)
    db_session.commit()
    return user


def _admin(db_session, capabilities=None):
    user = make_user(
        db_session, "support", capabilities=capabilities or list(Capability)
    )
    db_session.commit()
    return user


# ── ۱. منابع انسانی دیگر به مدیریت سامانه نمی‌رسد ───────────────────────────

def test_hr_cannot_read_the_audit_log(client, db_session):
    hr = _hr(db_session)
    assert client.get("/api/audit-log", headers=auth_header(hr)).status_code == 403


def test_hr_cannot_open_the_capability_matrix(client, db_session):
    hr = _hr(db_session)
    assert client.get("/api/administration/capabilities", headers=auth_header(hr)).status_code == 403
    assert client.get("/api/administration/separation", headers=auth_header(hr)).status_code == 403


def test_hr_keeps_its_own_work(client, db_session):
    """تفکیک نباید کارِ روزمره را هم ببرد.

    «کاربران»، «شاخص‌ها» و «طرح نمره‌دهی» بخشی از پنل منابع انسانی می‌مانند؛
    اگر این تست بشکند یعنی تفکیک از هدفش رد شده و صرفاً HR را فلج کرده.
    """
    hr = _hr(db_session)
    assert client.get("/api/users", headers=auth_header(hr)).status_code == 200


def test_creating_accounts_does_not_grant_the_power_to_grant(client, db_session):
    """قلبِ تفکیک: `manage_users` نباید به اختیاردهی راه بدهد.

    بدون این، هرکس حساب می‌سازد می‌تواند حسابی بسازد و به آن — یا به خودش —
    هر اختیاری بدهد، و تمام گاردهای دیگر دور زده می‌شوند.
    """
    hr = _hr(db_session)
    target = make_user(db_session, "deputy", capabilities=[])
    db_session.commit()

    response = client.patch(
        f"/api/administration/capabilities/{target.id}",
        json={"capabilities": [Capability.manage_capabilities.value]},
        headers=auth_header(hr),
    )
    assert response.status_code in (403, 405), response.text


# ── ۲. مدیر سامانه می‌رسد ───────────────────────────────────────────────────

def test_admin_reaches_both(client, db_session):
    admin = _admin(db_session)
    assert client.get("/api/audit-log", headers=auth_header(admin)).status_code == 200
    assert client.get("/api/administration/capabilities", headers=auth_header(admin)).status_code == 200


def test_admin_can_grant_capabilities(client, db_session):
    admin = _admin(db_session)
    target = make_user(db_session, "deputy", capabilities=[])
    db_session.commit()

    response = client.put(
        f"/api/administration/capabilities/{target.id}",
        json={"capabilities": [Capability.view_audit_log.value]},
        headers=auth_header(admin),
    )
    assert response.status_code == 200, response.text
    assert response.json()["capabilities"] == [Capability.view_audit_log.value]


# ── ۳. دامنهٔ دیدِ لاگ، بر پایهٔ مجوز نه نقش ────────────────────────────────

def test_diagnostics_only_never_sees_evaluation_rows(client, db_session):
    """پشتیبانیِ بدون `view_audit_log` نباید هیچ ردی از محتوای پرونده ببیند.

    ادعا روی *داده* است نه کد وضعیت: ۲۰۰ با فهرستی که ردیف پرونده‌دار ندارد،
    همان چیزی است که باید رخ بدهد.
    """
    support = _admin(db_session, capabilities=[Capability.view_diagnostics])
    response = client.get("/api/audit-log", headers=auth_header(support))
    assert response.status_code == 200, response.text
    assert all(row["evaluation_record_id"] is None for row in response.json()["items"])


def test_the_full_log_is_grantable_to_anyone(client, db_session):
    """و برعکس: هرکس این مجوز را بگیرد، لاگ کامل را می‌بیند — حتی بدون نقش hr."""
    reader = make_user(db_session, "deputy", capabilities=[Capability.view_audit_log])
    db_session.commit()
    assert client.get("/api/audit-log", headers=auth_header(reader)).status_code == 200


def test_no_capability_means_no_audit_log(client, db_session):
    stranger = make_user(db_session, "deputy", capabilities=[])
    db_session.commit()
    assert client.get("/api/audit-log", headers=auth_header(stranger)).status_code == 403
