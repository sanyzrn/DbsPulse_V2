"""نیمهٔ دوم P0-03 — جداسازی وظایف مدیر سامانه.

تا امروز `hr` هم‌زمان کاربر عادی و مدیر سامانه بود. اگر روزی نتیجه‌ای زیر سؤال
برود، نمی‌شد ثابت کرد کسی که تصمیم گرفته همان کسی نبوده که قاعده را نوشته.

دو ادعا که این فایل می‌سنجد، و ترتیبشان مهم است:

۱. **حساب پشتیبانی به هیچ پروندهٔ ارزیابی دسترسی ندارد.** کسی که سامانه را نگه
   می‌دارد لازم نیست نمرهٔ کسی را ببیند. این نیمهٔ *امنیتی* ماجراست.
۲. **هیچ استقرار موجودی نمی‌شکند.** HR که دیروز همه‌کاره بود، امروز هم هست —
   تفکیک ممکن می‌شود، نه تحمیل.
"""
import pytest
from sqlalchemy import select

from app.api.routers.audit_log import SYSTEM_EVENT_TYPES
from app.core.modules import MODULES_BY_KEY
from app.models.capability import UserCapability
from app.models.enums import Capability
from app.models.module import ModuleSetting
from tests.helpers import auth_header, make_personnel, make_user

ALL = [c.value for c in Capability]


@pytest.fixture()
def admin(db_session):
    """کاربر HR با همهٔ مجوزها — همان چیزی که مایگریشن ساخته است."""
    user = make_user(db_session, "hr")
    db_session.commit()
    return user


@pytest.fixture()
def support(db_session):
    """حساب پشتیبانی: بدون هیچ جایگاهی در زنجیرهٔ ارزیابی."""
    user = make_user(db_session, "support", capabilities=[Capability.view_diagnostics])
    db_session.commit()
    return user


# ── ۱. حساب پشتیبانی به پرونده‌ها دسترسی ندارد ──────────────────────────────

def test_support_sees_no_evaluation_or_personnel_data(client, db_session, support):
    """مهم‌ترین تست این فایل.

    ادعا روی *داده* است نه روی کد وضعیت: بعضی مسیرها ۴۰۳ می‌دهند (گارد نقش) و
    بعضی ۲۰۰ با فهرست خالی (دامنهٔ دید بر پایهٔ زنجیره). هر دو درست‌اند؛ آنچه
    نباید رخ بدهد این است که ردیفی از دادهٔ کسی به حساب پشتیبانی برسد.

    سنجیدنِ کد وضعیت، تستی می‌ساخت که با تغییر شکل گارد بشکند بی‌آنکه چیزی
    ناامن شده باشد — و بدتر، اگر روزی یکی از این‌ها به «۲۰۰ با همه‌چیز» تبدیل
    می‌شد، همچنان سبز می‌ماند.
    """
    make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    person = make_personnel(db_session, full_name="نامی که پشتیبانی نباید ببیند")
    from tests.helpers import make_access

    make_access(db_session, person, sup, dep, ceo)
    db_session.commit()
    client.post(
        "/api/evaluations",
        json={"subject_personnel_id": person.id},
        headers=auth_header(sup),
    )

    for path in (
        "/api/evaluations",
        "/api/personnel",
        "/api/dashboard/overview",
        "/api/dashboard/report/summary",
        "/api/audit-log",
        "/api/improvement-plans",
        "/api/periods",
    ):
        response = client.get(path, headers=auth_header(support))
        assert response.status_code in (403, 200), f"{path}: {response.status_code}"
        if response.status_code == 200:
            body = response.text
            assert "نامی که پشتیبانی نباید ببیند" not in body, f"{path} نام فرد را افشا کرد"
            payload = response.json()
            rows = payload.get("items", payload) if isinstance(payload, dict) else payload
            assert not rows, f"{path} ردیف برگرداند: {rows}"


def test_support_cannot_score_or_approve(client, db_session, support):
    make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    person = make_personnel(db_session)
    from tests.helpers import make_access

    make_access(db_session, person, sup, dep, ceo)
    db_session.commit()

    record_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": person.id},
        headers=auth_header(sup),
    ).json()["id"]

    assert client.get(f"/api/evaluations/{record_id}", headers=auth_header(support)).status_code == 403
    assert (
        client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(support)).status_code
        == 403
    )


def test_support_can_do_what_it_was_given(client, support):
    """و آن‌چه مجوزش را دارد، کار می‌کند."""
    assert client.get("/api/admin/scheduler-runs", headers=auth_header(support)).status_code == 200


# ── ۲. هیچ استقراری نمی‌شکند ────────────────────────────────────────────────

def test_an_existing_hr_user_keeps_everything(client, admin):
    """HR که دیروز همه‌کاره بود، امروز هم هست. تحمیل تفکیک در یک مایگریشن یعنی
    کسی صبح بیدار شود و نتواند وارد بخشی شود که دیروز مالِ او بود."""
    for path in ("/api/users", "/api/scoring-schemes", "/api/administration/modules"):
        assert client.get(path, headers=auth_header(admin)).status_code == 200


def test_the_migration_granted_every_capability_to_hr(db_session, admin):
    held = set(
        db_session.scalars(
            select(UserCapability.capability).where(UserCapability.user_id == admin.id)
        )
    )
    assert held == set(Capability)


# ── مجوز، نه نقش ────────────────────────────────────────────────────────────

def test_an_hr_user_without_the_capability_is_refused(client, db_session):
    """گارد نقش را نگاه نمی‌کند. تنها راهِ داشتنِ اختیار، داشتنِ خودِ مجوز است —
    همان چیزی که «مدیر سامانه» را از «کاربر پرمشغله» جدا می‌کند."""
    stripped = make_user(db_session, "hr", capabilities=[])
    db_session.commit()

    assert client.get("/api/users", headers=auth_header(stripped)).status_code == 403
    # خواندنِ فهرست شاخص‌ها عمداً برای همه باز است — هر ارزیابی برای رندر فرم
    # به آن نیاز دارد. فقط *نوشتن* مجوز می‌خواهد.
    assert client.get("/api/indicators", headers=auth_header(stripped)).status_code == 200
    assert (
        client.post(
            "/api/indicators",
            json={"section": "general", "category": "الف", "description": "ب", "display_order": 99},
            headers=auth_header(stripped),
        ).status_code
        == 403
    )


def test_capabilities_are_granular(client, db_session):
    """یک مجوزِ همه‌کاره دقیقاً همان مشکلی را می‌ساخت که این تفکیک برای حلش آمده."""
    scoring_only = make_user(db_session, "hr", capabilities=[Capability.manage_scoring])
    db_session.commit()

    assert (
        client.post(
            "/api/indicators",
            json={"section": "general", "category": "الف", "description": "ب", "display_order": 98},
            headers=auth_header(scoring_only),
        ).status_code
        == 201
    )
    assert client.get("/api/users", headers=auth_header(scoring_only)).status_code == 403


def test_granting_and_revoking_is_recorded(client, db_session, admin):
    target = make_user(db_session, "support", capabilities=[])
    db_session.commit()

    granted = client.put(
        f"/api/administration/capabilities/{target.id}",
        json={"capabilities": [Capability.view_diagnostics.value]},
        headers=auth_header(admin),
    )
    assert granted.status_code == 200
    assert granted.json()["capabilities"] == [Capability.view_diagnostics.value]

    events = client.get(
        "/api/audit-log", params={"limit": 20}, headers=auth_header(admin)
    ).json()["items"]
    entry = next(e for e in events if e["event_type"] == "capabilities_changed")
    assert entry["new_value"]["capabilities"] == [Capability.view_diagnostics.value]
    assert entry["old_value"]["capabilities"] == []


def test_an_unknown_capability_is_refused(client, admin, support):
    response = client.put(
        f"/api/administration/capabilities/{support.id}",
        json={"capabilities": ["become_root"]},
        headers=auth_header(admin),
    )
    assert response.status_code == 422
    assert "ناشناخته" in response.json()["detail"]


def test_a_plain_employee_cannot_hold_capabilities(client, db_session, admin):
    person = make_personnel(db_session)
    employee = make_user(db_session, "employee", personnel_id=person.id, capabilities=[])
    db_session.commit()

    response = client.put(
        f"/api/administration/capabilities/{employee.id}",
        json={"capabilities": [Capability.view_diagnostics.value]},
        headers=auth_header(admin),
    )
    assert response.status_code == 400


def test_the_last_grantor_cannot_strip_themselves(client, db_session):
    """بدون این گارد، یک کلیک اشتباه سامانه را در حالتی قفل می‌کند که هیچ‌کس
    نمی‌تواند به کسی مجوز بدهد — و تنها راه خروج، SQL دستی روی پروداکشن است."""
    only = make_user(db_session, "hr")
    db_session.commit()

    response = client.put(
        f"/api/administration/capabilities/{only.id}",
        json={"capabilities": []},
        headers=auth_header(only),
    )

    assert response.status_code == 400
    assert "تنها حساب فعالی" in response.json()["detail"]


def test_with_a_second_grantor_the_first_can_step_down(client, db_session):
    first = make_user(db_session, "hr")
    second = make_user(db_session, "hr")
    db_session.commit()

    response = client.put(
        f"/api/administration/capabilities/{first.id}",
        json={"capabilities": []},
        headers=auth_header(second),
    )

    assert response.status_code == 200
    assert client.get("/api/users", headers=auth_header(first)).status_code == 403


# ── ماژول‌ها ────────────────────────────────────────────────────────────────

def test_modules_default_on_without_any_row(client, db_session, admin):
    """ماژول تازه‌ای که به کد اضافه شود، با حالتِ درستش شروع می‌کند — نه با
    «خاموش» فقط چون ردیف ندارد."""
    assert db_session.scalars(select(ModuleSetting)).all() == []

    modules = client.get("/api/administration/modules", headers=auth_header(admin)).json()

    assert {m["key"] for m in modules} == set(MODULES_BY_KEY)
    assert all(m["enabled"] for m in modules)


def test_toggling_a_module_is_recorded(client, admin):
    response = client.put(
        "/api/administration/modules/periods",
        json={"enabled": False},
        headers=auth_header(admin),
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is False

    events = client.get(
        "/api/audit-log", params={"limit": 20}, headers=auth_header(admin)
    ).json()["items"]
    entry = next(e for e in events if e["event_type"] == "module_toggled")
    assert entry["old_value"] == {"module": "periods", "enabled": True}
    assert entry["new_value"] == {"module": "periods", "enabled": False}


def test_an_unknown_module_is_refused(client, admin):
    assert (
        client.put(
            "/api/administration/modules/teleporter",
            json={"enabled": True},
            headers=auth_header(admin),
        ).status_code
        == 404
    )


def test_toggling_needs_the_module_capability(client, db_session):
    without = make_user(db_session, "hr", capabilities=[Capability.manage_users])
    db_session.commit()

    assert (
        client.put(
            "/api/administration/modules/periods",
            json={"enabled": False},
            headers=auth_header(without),
        ).status_code
        == 403
    )


# ── آنچه فرانت‌اند برای چیدن منو لازم دارد ─────────────────────────────────

def test_my_permissions_reports_capabilities_and_modules(client, support):
    """گزینه‌ای که اجازه‌اش را نداری، بهتر است اصلاً نباشد تا اینکه باشد و ۴۰۳ بگیرد."""
    body = client.get("/api/administration/my-permissions", headers=auth_header(support)).json()

    assert body["capabilities"] == [Capability.view_diagnostics.value]
    assert set(body["modules"]) == set(MODULES_BY_KEY)


def test_my_permissions_is_open_to_everyone(client, db_session):
    """هر کاربری باید بتواند مجوزهای خودش را بخواند — وگرنه فرانت‌اند برای
    ساختن منو به یک درخواستِ ۴۰۳شونده نیاز داشت."""
    person = make_personnel(db_session)
    employee = make_user(db_session, "employee", personnel_id=person.id, capabilities=[])
    db_session.commit()

    body = client.get("/api/administration/my-permissions", headers=auth_header(employee)).json()
    assert body["capabilities"] == []


# ── آیا تفکیک واقعاً برقرار است، یا فقط ممکن شده ────────────────────────────

def test_separation_reports_not_separated_while_hr_still_holds_everything(client, admin):
    """حالتِ روزِ اول: مایگریشن همه‌چیز را به HR داد تا استقراری نشکند.

    این تست همان چیزی را تثبیت می‌کند که در کار من جا افتاده بود: سازوکاری
    ساخته شد و خاموش ماند، بی‌آنکه چیزی این را بگوید. سازوکارِ خاموش از همه بدتر
    است — از بیرون «انجام‌شده» به‌نظر می‌رسد.
    """
    body = client.get("/api/administration/separation", headers=auth_header(admin)).json()

    assert body["separated"] is False
    assert [u["username"] for u in body["overlapping_users"]] == [admin.username]
    # فقط مجوزهای «قاعده‌ساز» گزارش می‌شوند، نه هر مجوزی
    assert set(body["overlapping_users"][0]["capabilities"]) == {
        Capability.manage_users.value,
        Capability.manage_scoring.value,
    }


def test_separation_becomes_true_once_rule_changing_moves_off_the_chain(
    client, db_session, admin, support
):
    """و وقتی واقعاً تفکیک شد، باید بگوید شد.

    وگرنه بنری می‌ماند که هیچ‌وقت خاموش نمی‌شود و مثل هر هشدارِ همیشه‌روشنی،
    خوانده نمی‌شود.
    """
    client.put(
        f"/api/administration/capabilities/{support.id}",
        json={"capabilities": ALL},
        headers=auth_header(admin),
    )
    client.put(
        f"/api/administration/capabilities/{admin.id}",
        json={"capabilities": []},
        headers=auth_header(admin),
    )

    body = client.get("/api/administration/separation", headers=auth_header(support)).json()

    assert body["separated"] is True
    assert body["overlapping_users"] == []
    assert body["dedicated_admin_count"] == 1


def test_separation_ignores_inactive_and_non_rule_changing_holders(client, db_session, admin):
    """دو چیزی که نباید بنر را روشن نگه دارند.

    حساب غیرفعال کاری نمی‌کند، و مجوز `view_diagnostics` قاعده‌ای را عوض
    نمی‌کند. اگر این‌ها هم بشمارند، بنر عملاً همیشه روشن است و معنایش را از
    دست می‌دهد.
    """
    stale = make_user(db_session, "hr", capabilities=[Capability.manage_users])
    stale.is_active = False
    make_user(db_session, "deputy", capabilities=[Capability.view_diagnostics])
    db_session.commit()

    body = client.get("/api/administration/separation", headers=auth_header(admin)).json()

    assert [u["username"] for u in body["overlapping_users"]] == [admin.username]


def test_separation_needs_manage_users(client, support):
    """پشتیبانیِ بدون مجوزِ کاربران نباید نقشهٔ اختیارات را ببیند."""
    assert client.get(
        "/api/administration/separation", headers=auth_header(support)
    ).status_code == 403


# ── لاگ ممیزی: یک صفحه، دو دامنهٔ دید ───────────────────────────────────────

def test_support_sees_system_events_but_no_evaluation_content(client, db_session, support):
    """لاگ ممیزی نباید به پنل پشتیبانی «منتقل» شود — باید *تفکیک* شود.

    این لاگ هر دو نوع رویداد را با هم دارد: هم «چه کسی این بخش را خاموش کرد»
    که پشتیبانی برای عیب‌یابی لازمش دارد، و هم ردیف‌هایی که عیناً امتیاز و
    نتیجهٔ نهایی یک نفر را در خود نگه می‌دارند. انتقال کامل، همان چیزی را به
    پشتیبانی می‌داد که کل این تفکیک برای ممنوع‌کردنش ساخته شد.
    """
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    person = make_personnel(db_session, full_name="سوژهٔ لاگ")
    from tests.helpers import active_indicators, full_valid_scores, make_access

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
    # یک رویداد سامانه‌ای هم بسازیم
    client.put(
        "/api/administration/modules/periods",
        json={"enabled": False},
        headers=auth_header(hr),
    )

    hr_view = client.get(
        "/api/audit-log", params={"limit": 200}, headers=auth_header(hr)
    ).json()
    support_response = client.get(
        "/api/audit-log", params={"limit": 200}, headers=auth_header(support)
    )
    assert support_response.status_code == 200, "پشتیبانی باید برای عیب‌یابی دسترسی داشته باشد"
    support_view = support_response.json()

    hr_types = {e["event_type"] for e in hr_view["items"]}
    support_types = {e["event_type"] for e in support_view["items"]}

    # پشتیبانی رویداد سامانه‌ای را می‌بیند
    assert "module_toggled" in support_types
    # ولی هیچ رویدادی از محتوای پرونده را نه
    assert "score_submitted" not in support_types
    assert "scores_draft_saved" not in support_types
    assert "status_changed" not in support_types
    assert support_types <= SYSTEM_EVENT_TYPES
    # و منابع انسانی همه را می‌بیند
    assert {"score_submitted", "module_toggled"} <= hr_types

    # هیچ ردیفی نباید به پرونده‌ای گره خورده باشد یا نمره‌ای در خود داشته باشد
    assert all(e["evaluation_record_id"] is None for e in support_view["items"])
    assert "سوژهٔ لاگ" not in support_response.text
    assert "final_weighted_pct" not in support_response.text


def test_a_new_event_type_is_hidden_from_support_by_default(client, support):
    """فهرست allowlist است، نه blocklist.

    اگر روزی رویداد تازه‌ای اضافه شود و کسی یادش برود این‌جا بیاوردش، از دید
    پشتیبانی پنهان می‌ماند — نه اینکه ناخواسته افشا شود. همان درسی که در
    دامنهٔ دید پرونده‌ها گرفتیم.
    """
    assert "score_submitted" not in SYSTEM_EVENT_TYPES
    assert "evaluation_returned" not in SYSTEM_EVENT_TYPES
    assert "pdf_downloaded" not in SYSTEM_EVENT_TYPES
    assert "personnel_created" not in SYSTEM_EVENT_TYPES
