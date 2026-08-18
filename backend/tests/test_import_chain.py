"""ایمپورت، زنجیرهٔ ارزیابی را هم می‌سازد — نه فقط ردیف پرسنل.

تا پیش از این ایمپورت فقط `Personnel` می‌ساخت. یعنی بلافاصله بعد از یک فایل
۴۲ نفره، ۴۲ نفر داشتید که *هیچ‌کس نمی‌توانست ارزیابی‌شان کند*، و تنظیمش ۴۲ بار
باز کردن فرم ویرایش بود — در حالی که همان داده در دو ستون از خودِ فایل بود.

ارزیاب‌ها با *نام* نوشته می‌شوند نه با شناسه: کسی که فایل را در اکسل پر می‌کند
id کاربر را نمی‌داند.
"""
from io import BytesIO

from openpyxl import Workbook

from app.models.enums import Capability, UserRole
from app.models.evaluation_access import EvaluationAccess
from app.services.personnel_import import COLUMNS, parse_workbook
from tests.helpers import auth_header, make_user

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _workbook(rows: list[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(COLUMNS)
    for row in rows:
        ws.append([row.get(column, "") for column in COLUMNS])
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _row(code: str, name: str, **extra) -> dict:
    return {
        "کد پرسنلی": code,
        "نام و نام خانوادگی": name,
        "عنوان شغلی": "کارشناس",
        "واحد سازمانی": "فروش",
        "مدیر": "خیر",
        "وضعیت": "فعال",
        "شروع قرارداد": "۱۴۰۵/۰۱/۰۱",
        "پایان قرارداد": "۱۴۰۶/۰۱/۰۱",
        **extra,
    }


def _evaluators(db_session):
    ceo = make_user(db_session, "ceo", capabilities=[])
    ceo.full_name = "مدیرعامل، آقای شمالی"
    deputy = make_user(db_session, "deputy", capabilities=[])
    deputy.full_name = "معاونت، آقای سلیمی"
    supervisor = make_user(db_session, "unit_supervisor", capabilities=[])
    supervisor.full_name = "مسئول واحد، خانم حسینی"
    db_session.commit()
    return ceo, deputy, supervisor


def test_the_chain_is_built_from_names(client, db_session):
    hr = make_user(db_session, "hr")
    ceo, deputy, supervisor = _evaluators(db_session)
    content = _workbook(
        [
            _row(
                "IMP-1",
                "کارمند یک",
                **{
                    "مسئول مستقیم": supervisor.full_name,
                    "معاونت مربوطه": deputy.full_name,
                    "مدیرعامل": ceo.full_name,
                },
            )
        ]
    )

    response = client.post(
        "/api/personnel/import",
        files={"file": ("p.xlsx", content, XLSX)},
        headers=auth_header(hr),
    )
    assert response.status_code == 200, response.text
    assert response.json()["created_chains"] == 1

    access = db_session.scalar(select_access(db_session, "IMP-1"))
    assert access.unit_supervisor_user_id == supervisor.id
    assert access.deputy_user_id == deputy.id
    assert access.ceo_user_id == ceo.id


def select_access(db_session, personnel_code: str):
    from sqlalchemy import select

    from app.models.personnel import Personnel

    return (
        select(EvaluationAccess)
        .join(Personnel, Personnel.id == EvaluationAccess.personnel_id)
        .where(Personnel.personnel_code == personnel_code)
    )


def test_a_sole_ceo_fills_the_empty_column(client, db_session):
    """نوشتن یک نام تکراری در ۴۲ ردیف، کاری است که فایل می‌تواند نکند."""
    hr = make_user(db_session, "hr")
    ceo, deputy, _ = _evaluators(db_session)
    content = _workbook(
        [_row("IMP-2", "کارمند دو", **{"معاونت مربوطه": deputy.full_name})]
    )

    response = client.post(
        "/api/personnel/import",
        files={"file": ("p.xlsx", content, XLSX)},
        headers=auth_header(hr),
    )
    assert response.status_code == 200, response.text
    access = db_session.scalar(select_access(db_session, "IMP-2"))
    assert access.ceo_user_id == ceo.id


def test_an_unknown_name_is_a_row_error_not_a_silent_skip(client, db_session):
    """اگر بی‌صدا رد می‌شد، ایمپورت «موفق» گزارش می‌داد و آن پرسنل بدون زنجیره
    می‌ماند — همان وضعیتی که این ستون‌ها برای رفعش آمدند، فقط پنهان."""
    _evaluators(db_session)
    hr = make_user(db_session, "hr")
    db_session.commit()
    content = _workbook(
        [_row("IMP-3", "کارمند سه", **{"معاونت مربوطه": "کسی که وجود ندارد"})]
    )
    preview = parse_workbook(content, db_session)
    assert len(preview.invalid) == 1
    assert "پیدا نشد" in preview.invalid[0].errors[0]
    assert hr is not None


def test_nobody_may_be_their_own_evaluator(client, db_session):
    hr = make_user(db_session, "hr")
    _evaluators(db_session)
    content = _workbook(
        [_row("IMP-4", "کارمند چهار", **{"مسئول مستقیم": "کارمند چهار"})]
    )
    preview = parse_workbook(content, db_session)
    assert len(preview.invalid) == 1
    assert "ارزیابِ خودش" in preview.invalid[0].errors[0]
    assert hr is not None


def test_a_dash_means_this_stage_does_not_exist(client, db_session):
    """«-» یعنی این مرحله را ندارد، نه اینکه یادشان رفته پر کنند."""
    hr = make_user(db_session, "hr")
    ceo, _, supervisor = _evaluators(db_session)
    content = _workbook(
        [
            _row(
                "IMP-5",
                "کارمند پنج",
                **{"مسئول مستقیم": supervisor.full_name, "معاونت مربوطه": "-"},
            )
        ]
    )
    response = client.post(
        "/api/personnel/import",
        files={"file": ("p.xlsx", content, XLSX)},
        headers=auth_header(hr),
    )
    assert response.status_code == 200, response.text
    access = db_session.scalar(select_access(db_session, "IMP-5"))
    assert access.deputy_user_id is None
    assert access.ceo_user_id == ceo.id


def test_a_name_that_cannot_hold_that_stage_is_rejected(client, db_session):
    """جهت‌داری سلسله‌مراتب، این‌جا هم اعمال می‌شود."""
    hr = make_user(db_session, "hr")
    _, _, supervisor = _evaluators(db_session)
    content = _workbook(
        [_row("IMP-6", "کارمند شش", **{"معاونت مربوطه": supervisor.full_name})]
    )
    preview = parse_workbook(content, db_session)
    assert len(preview.invalid) == 1
    assert "این مرحله" in preview.invalid[0].errors[0]
    assert hr is not None


def test_the_chain_columns_stay_optional(client, db_session):
    """فایل‌های قدیمی بدون این سه ستون باید همچنان کار کنند."""
    hr = make_user(db_session, "hr")
    db_session.commit()
    wb = Workbook()
    ws = wb.active
    old_columns = COLUMNS[:9]
    ws.append(old_columns)
    ws.append([_row("IMP-7", "کارمند هفت").get(c, "") for c in old_columns])
    buffer = BytesIO()
    wb.save(buffer)

    response = client.post(
        "/api/personnel/import",
        files={"file": ("p.xlsx", buffer.getvalue(), XLSX)},
        headers=auth_header(hr),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created_personnel"] == 1
    assert body["created_chains"] == 0


def test_capability_still_required(client, db_session):
    stranger = make_user(db_session, "deputy", capabilities=[Capability.view_diagnostics])
    db_session.commit()
    response = client.post(
        "/api/personnel/import",
        files={"file": ("p.xlsx", b"x", XLSX)},
        headers=auth_header(stranger),
    )
    assert response.status_code == 403
    assert UserRole.deputy is not None
