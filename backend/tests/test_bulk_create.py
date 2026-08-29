"""P2-03 — ساخت دسته‌ای ارزیابی برای یک کوهورت.

خطر این قابلیت، وسوسهٔ ساده‌کردنش است. در حالت دسته‌ای، «رد شد» شبیه خطا به‌نظر
می‌رسد و آسان است که کسی گاردها را دور بزند تا عدد «ساخته‌شده» بزرگ‌تر شود. ولی
همان گاردها هستند که جلوی دو پروندهٔ هم‌زمان برای یک نفر، و پروندهٔ بی‌مسئول را
می‌گیرند.

پس بیشتر این فایل دربارهٔ رد شدن‌هاست: که رخ می‌دهند، که *دلیلشان* گفته می‌شود،
و که بقیهٔ کار را متوقف نمی‌کنند.
"""
import pytest

from app.models.enums import Capability, EvaluationStatus, PersonnelStatus
from app.models.evaluation import EvaluationRecord
from tests.helpers import auth_header, make_access, make_personnel, make_user


@pytest.fixture()
def cohort(db_session):
    """یک واحد با چهار وضعیت متفاوت — هر کدام یک شاخهٔ متفاوت از منطق."""
    hr = make_user(db_session, "hr", capabilities=[Capability.view_audit_log])
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")

    ready = make_personnel(db_session, full_name="آمادهٔ ارزیابی", org_unit="واحد دسته‌ای")
    make_access(db_session, ready, sup, dep, ceo)

    inactive = make_personnel(
        db_session,
        full_name="غیرفعال",
        org_unit="واحد دسته‌ای",
        status=PersonnelStatus.inactive,
    )
    make_access(db_session, inactive, sup, dep, ceo)

    # بدون هیچ ردیف دسترسی — زنجیره‌اش تعریف نشده است
    orphan = make_personnel(db_session, full_name="بدون زنجیره", org_unit="واحد دسته‌ای")

    # ردیف دسترسی دارد ولی مسئول واحدش خالی است، و مدیر هم نیست
    headless = make_personnel(db_session, full_name="بدون مسئول واحد", org_unit="واحد دسته‌ای")
    make_access(db_session, headless, None, dep, ceo)

    db_session.commit()
    return {
        "hr": hr, "sup": sup, "dep": dep, "ceo": ceo,
        "ready": ready, "inactive": inactive, "orphan": orphan, "headless": headless,
    }


def _preview(client, hr, **cohort_filter):
    return client.post(
        "/api/periods/bulk-create/preview", json=cohort_filter, headers=auth_header(hr)
    ).json()


def _run(client, hr, **cohort_filter):
    return client.post("/api/periods/bulk-create", json=cohort_filter, headers=auth_header(hr)).json()


def _by_name(body) -> dict[str, dict]:
    return {row["full_name"]: row for row in body["results"]}


# ── دسترسی ──────────────────────────────────────────────────────────────────

def test_only_hr_can_open_a_cycle_in_bulk(client, cohort):
    """باز کردن چرخه کارِ منابع انسانی است. ارزیاب پروندهٔ خودش را شروع می‌کند،
    نه چرخهٔ کل یک واحد را."""
    for actor in ("sup", "dep", "ceo"):
        response = client.post(
            "/api/periods/bulk-create",
            json={"org_unit": "واحد دسته‌ای"},
            headers=auth_header(cohort[actor]),
        )
        assert response.status_code == 403, actor


# ── پیش‌نمایش ───────────────────────────────────────────────────────────────

def test_the_preview_writes_nothing(client, db_session, cohort):
    """اگر پیش‌نمایش چیزی بنویسد، دیگر پیش‌نمایش نیست."""
    before = db_session.query(EvaluationRecord).count()

    body = _preview(client, cohort["hr"], org_unit="واحد دسته‌ای")

    assert body["dry_run"] is True
    assert body["counts"].get("created") == 1
    assert db_session.query(EvaluationRecord).count() == before


def test_every_refusal_states_its_own_reason(client, cohort):
    """«۳ نفر رد شدند» بی‌فایده است؛ HR باید بداند برای هرکدام چه کاری باید بکند."""
    rows = _by_name(_preview(client, cohort["hr"], org_unit="واحد دسته‌ای"))

    assert rows["آمادهٔ ارزیابی"]["outcome"] == "created"
    assert rows["غیرفعال"]["outcome"] == "blocked_inactive"
    assert rows["بدون زنجیره"]["outcome"] == "blocked_no_access_row"
    assert rows["بدون مسئول واحد"]["outcome"] == "blocked_no_supervisor"
    # و هر کدام یک جملهٔ فارسی برای نمایش مستقیم دارند
    assert all(row["reason"] for row in rows.values())


def test_an_inactive_person_is_reported_not_hidden(client, cohort):
    """فیلترکردنِ بی‌صدای غیرفعال‌ها یعنی HR هرگز نمی‌فهمد چرا فلانی در فهرست
    نیست، و دنبال یک باگ می‌گردد که وجود ندارد."""
    rows = _by_name(_preview(client, cohort["hr"], org_unit="واحد دسته‌ای"))

    assert "غیرفعال" in rows
    assert rows["غیرفعال"]["outcome"] == "blocked_inactive"


def test_the_preview_matches_what_execution_does(client, cohort):
    """قلبِ این قابلیت: پیش‌نمایش نباید چیزی وعده بدهد که اجرا انجام نمی‌دهد.

    اگر این دو از هم جدا شوند، کاربر بر اساس چیزی تصمیم می‌گیرد که اتفاق
    نمی‌افتد — و بدترین جای ممکن برای این خطا، عملیاتی است که دویست پرونده
    می‌سازد.
    """
    preview = _preview(client, cohort["hr"], org_unit="واحد دسته‌ای")
    executed = _run(client, cohort["hr"], org_unit="واحد دسته‌ای")

    assert executed["dry_run"] is False
    assert preview["counts"] == executed["counts"]
    assert {r["personnel_id"]: r["outcome"] for r in preview["results"]} == {
        r["personnel_id"]: r["outcome"] for r in executed["results"]
    }


# ── اجرا ────────────────────────────────────────────────────────────────────

def test_the_created_record_lands_in_the_right_evaluators_queue(client, db_session, cohort):
    """HR چرخه را باز می‌کند، ولی نمره‌دهی دست خودِ ارزیاب می‌ماند."""
    body = _run(client, cohort["hr"], org_unit="واحد دسته‌ای")
    created = _by_name(body)["آمادهٔ ارزیابی"]

    record = db_session.get(EvaluationRecord, created["evaluation_id"])
    db_session.refresh(record)
    assert record.unit_supervisor_user_id == cohort["sup"].id
    assert record.status == EvaluationStatus.draft


def test_one_blocked_person_does_not_undo_the_others(client, db_session, cohort):
    """savepoint به‌ازای هر رکورد. بدون آن، یک تعارض وسط کار صد پروندهٔ
    ساخته‌شدهٔ قبلی را برمی‌گرداند و HR باید از صفر شروع کند."""
    body = _run(client, cohort["hr"], org_unit="واحد دسته‌ای")

    assert body["counts"]["created"] == 1
    assert sum(v for k, v in body["counts"].items() if k.startswith("blocked")) == 3
    # و آن یک پرونده واقعاً در دیتابیس هست
    created_id = _by_name(body)["آمادهٔ ارزیابی"]["evaluation_id"]
    assert db_session.get(EvaluationRecord, created_id) is not None


def test_running_twice_does_not_create_a_second_file(client, db_session, cohort):
    """idempotent بودن این‌جا شرط استفادهٔ واقعی است: HR مشکل چند نفر را حل
    می‌کند و دوباره اجرا می‌کند. اگر دور دوم پروندهٔ دوم بسازد، ابزار غیرقابل
    استفاده است."""
    first = _run(client, cohort["hr"], org_unit="واحد دسته‌ای")
    second = _run(client, cohort["hr"], org_unit="واحد دسته‌ای")

    assert first["counts"]["created"] == 1
    assert second["counts"].get("created", 0) == 0
    assert second["counts"]["skipped_already_open"] == 1
    # همان پرونده، نه یکی تازه
    assert (
        _by_name(second)["آمادهٔ ارزیابی"]["evaluation_id"]
        == _by_name(first)["آمادهٔ ارزیابی"]["evaluation_id"]
    )
    assert (
        db_session.query(EvaluationRecord)
        .filter_by(subject_personnel_id=cohort["ready"].id)
        .count()
        == 1
    )


def test_a_manager_goes_down_the_manager_path(client, db_session, cohort):
    """پرسنل «مدیر» نمره‌دهندهٔ اولش معاونت است و پرونده مستقیماً در وضعیت
    hr_approved ساخته می‌شود — همان قاعدهٔ مسیر تک‌رکوردی."""
    manager = make_personnel(
        db_session, full_name="مدیر واحد", org_unit="واحد مدیران", is_manager=True
    )
    make_access(db_session, manager, None, cohort["dep"], cohort["ceo"])
    db_session.commit()

    body = _run(client, cohort["hr"], org_unit="واحد مدیران")
    created = _by_name(body)["مدیر واحد"]
    assert created["outcome"] == "created"

    record = db_session.get(EvaluationRecord, created["evaluation_id"])
    db_session.refresh(record)
    assert record.unit_supervisor_user_id is None
    assert record.status == EvaluationStatus.hr_approved


def test_the_cohort_filters_combine(client, db_session, cohort):
    """فیلترها ترکیب‌پذیرند، وگرنه «مدیران واحد الف» قابل بیان نیست."""
    manager = make_personnel(
        db_session, full_name="مدیر همان واحد", org_unit="واحد دسته‌ای", is_manager=True
    )
    make_access(db_session, manager, None, cohort["dep"], cohort["ceo"])
    db_session.commit()

    managers_only = _preview(
        client, cohort["hr"], org_unit="واحد دسته‌ای", only_managers=True
    )
    assert [r["full_name"] for r in managers_only["results"]] == ["مدیر همان واحد"]

    others_only = _preview(client, cohort["hr"], org_unit="واحد دسته‌ای", only_managers=False)
    assert "مدیر همان واحد" not in _by_name(others_only)


def test_an_empty_cohort_is_an_empty_answer_not_an_error(client, cohort):
    body = _preview(client, cohort["hr"], org_unit="واحدی که وجود ندارد")

    assert body["total"] == 0
    assert body["results"] == []
    assert body["counts"] == {}


def test_the_bulk_run_is_written_to_the_audit_log(client, cohort):
    """باز کردن یک چرخه برای کل یک واحد، یک تصمیم سازمانی است. باید بعداً بشود
    پرسید «چه کسی، چه کوهورتی، با چه نتیجه‌ای»."""
    _run(client, cohort["hr"], org_unit="واحد دسته‌ای")

    events = client.get(
        "/api/audit-log", params={"limit": 50}, headers=auth_header(cohort["hr"])
    ).json()["items"]
    entry = next(e for e in events if e["event_type"] == "evaluations_bulk_created")

    assert entry["new_value"]["cohort"]["org_unit"] == "واحد دسته‌ای"
    assert entry["new_value"]["counts"]["created"] == 1


def test_the_assignee_is_told_once_not_once_per_file(client, db_session, cohort):
    """یک مسئول واحد ممکن است ده نفر بگیرد. ده اعلانِ پشت‌سرهم یعنی هیچ اعلانی."""
    for index in range(3):
        person = make_personnel(
            db_session, full_name=f"نفر {index}", org_unit="واحد پراعلان"
        )
        make_access(db_session, person, cohort["sup"], cohort["dep"], cohort["ceo"])
    db_session.commit()

    _run(client, cohort["hr"], org_unit="واحد پراعلان")

    page = client.get("/api/notifications", headers=auth_header(cohort["sup"])).json()
    bulk = [n for n in page["items"] if n["type"] == "bulk_evaluations_assigned"]
    assert len(bulk) == 1
    assert "3" in bulk[0]["message"], "پیام باید بگوید چند تا، وگرنه باید همه را باز کند تا بفهمد"
