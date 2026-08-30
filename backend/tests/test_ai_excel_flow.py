"""اکسلِ پرسنل در گفت‌وگو: بارگذاری → خطایابی ردیف‌به‌ردیف → پرسیدن مقدارِ
جاافتاده → اصلاح → اعتبارسنجیِ دوباره → تأیید → ورود.

سناریویی که محصول برایش ساخته شده: فایلِ ناقص نباید «موفق» گزارش شود،
نباید ردیفِ خطادار را بی‌صدا رد کند، و نباید بدون تصمیمِ آدم چیزی بنویسد.
"""
import json
from io import BytesIO

import pytest
from fastapi import HTTPException
from openpyxl import Workbook

from app.models.enums import Capability, PersonnelStatus
from tests.fake_llm import ScriptedAdapter, reset, response, tool_call
from tests.helpers import auth_header, make_user

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

HEADERS = [
    "کد پرسنلی", "نام و نام خانوادگی", "عنوان شغلی", "محل", "واحد سازمانی",
    "مدیر", "وضعیت", "شروع قرارداد", "پایان قرارداد", "نام کاربری",
    "رمز اولیه", "مسئول مستقیم", "معاونت مربوطه", "مدیرعامل",
]

from app.services.ai.tools import base as tools_base  # noqa: E402


def _workbook(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(HEADERS)
    for row in rows:
        ws.append(row)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _enable_ai(db, user) -> None:
    from app.core.crypto import encrypt
    from app.models.ai import AiSettings, AiUserAccess

    db.merge(AiSettings(id=1, enabled=True, base_url="http://x", model="m", api_key_encrypted=encrypt("k")))
    db.add(AiUserAccess(user_id=user.id, enabled=True))
    db.commit()


def _upload(client, user, filename: str, content: bytes, conversation_id: int):
    return client.post(
        f"/api/ai/conversations/{conversation_id}/attachments",
        files={"file": (filename, content, XLSX)},
        headers=auth_header(user),
    )


def _new_conversation(client, user) -> int:
    response = client.post("/api/ai/conversations", headers=auth_header(user))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _tool_ctx(db, user, conversation_id=0):
    from app.schemas.auth import CurrentUser
    from app.services.ai.tools.base import ToolContext
    from app.services.authorization import capabilities_of

    return ToolContext(
        db=db,
        user=CurrentUser(
            id=user.id, username=user.username, role=user.role,
            personnel_id=user.personnel_id, must_change_password=False,
            display_name=user.username,
        ),
        caps=frozenset(capabilities_of(db, user.id)),
        conversation_id=conversation_id,
    )


def tools_call(ctx, name, arguments):
    from app.services.ai.tools.base import execute_tool

    return execute_tool(ctx, tools_base.REGISTRY[name], arguments)


BROKEN_ROW = ["X-1", "نفرِ ناقص", "کارشناس", "", "فروش", "خیر", "فعال", "1405/01/01", "", "", "", "", "", ""]


# ── مرحله‌بندی: هیچ ردیفی ساخته نمی‌شود ───────────────────────────────────


def test_upload_stages_the_file_and_reports_row_errors(client, db_session):
    hr = make_user(db_session, "hr", username="xu_hr", capabilities=[Capability.manage_personnel])
    _enable_ai(db_session, hr)
    conversation_id = _new_conversation(client, hr)

    content = _workbook(
        [
            [
                "X-1",
                "نفرِ سالم",
                "کارشناس",
                "دفتر مرکزی",
                "فروش",
                "خیر",
                "فعال",
                "1405/01/01",
                "1406/01/01",
                "",
                "",
                "",
                "",
                "",
            ],
            BROKEN_ROW,
        ]
    )
    response = _upload(client, hr, "people.xlsx", content, conversation_id)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["kind"] == "personnel_import"
    assert body["total_rows"] == 2
    assert body["valid_count"] == 1
    assert body["invalid_count"] == 1

    from app.models.personnel import Personnel
    assert db_session.query(Personnel).filter_by(personnel_code="X-1").count() == 0


def test_upload_requires_a_conversation_of_your_own(client, db_session):
    stranger = make_user(db_session, "employee", username="xu_emp", capabilities=[])
    _enable_ai(db_session, stranger)
    response = _upload(client, stranger, "people.xlsx", _workbook([]), 1)
    assert response.status_code == 404


def test_upload_rejects_oversized_files(client, db_session):
    from app.models.ai import AiSettings

    hr = make_user(db_session, "hr", username="xu_big", capabilities=[Capability.manage_personnel])
    _enable_ai(db_session, hr)
    conversation_id = _new_conversation(client, hr)

    config = db_session.get(AiSettings, 1)
    config.max_upload_mb = 1
    db_session.commit()

    response = _upload(client, hr, "people.xlsx", b"x" * (1024 * 1024 + 10), conversation_id)
    assert response.status_code == 413


def test_non_personnel_excel_is_inspected_not_staged(client, db_session):
    hr = make_user(db_session, "hr", username="xu_xl", capabilities=[Capability.manage_personnel])
    _enable_ai(db_session, hr)
    conversation_id = _new_conversation(client, hr)

    content = _workbook([])  # بدون ستون‌های الزامیِ پرسنل
    body = _upload(client, hr, "other.xlsx", content, conversation_id).json()
    assert body["kind"] == "excel"


# ── بازرسی، اصلاح، ورود ────────────────────────────────────────────────────


def test_inspect_tool_reports_each_problematic_row(client, db_session):
    hr = make_user(db_session, "hr", username="xu_ins", capabilities=[Capability.manage_personnel])
    _enable_ai(db_session, hr)
    conversation_id = _new_conversation(client, hr)
    upload = _upload(client, hr, "people.xlsx", _workbook([BROKEN_ROW]), conversation_id).json()
    ctx = _tool_ctx(db_session, hr, conversation_id)

    outcome = tools_call(ctx, "inspect_upload", {"upload_id": upload["id"]})
    payload = json.loads(outcome.content)
    row = payload["rows"][0]
    assert row["row_number"] == 2
    assert any("پایان قرارداد" in e for e in row["errors"])


def test_patch_completes_the_missing_value_and_revalidation_passes(client, db_session):
    hr = make_user(db_session, "hr", username="xu_patch", capabilities=[Capability.manage_personnel])
    _enable_ai(db_session, hr)
    conversation_id = _new_conversation(client, hr)
    upload = _upload(client, hr, "people.xlsx", _workbook([BROKEN_ROW]), conversation_id).json()
    ctx = _tool_ctx(db_session, hr, conversation_id)

    # همان چیزی که مدل از جوابِ کاربر می‌سازد: تاریخِ شمسیِ پایان قرارداد
    outcome = tools_call(ctx, "patch_upload_rows", {
        "upload_id": upload["id"],
        "edits": [{"row_number": 2, "fields": {"پایان قرارداد": "۱۴۰۶/۰۵/۰۱"}}],
    })
    payload = json.loads(outcome.content)
    assert payload["valid_count"] == 1
    assert payload["invalid_count"] == 0

    # اصلاحِ ستونِ ناموجود بی‌صدا نپذیرفته نمی‌شود
    with pytest.raises(HTTPException) as err:
        tools_call(ctx, "patch_upload_rows", {
            "upload_id": upload["id"],
            "edits": [{"row_number": 2, "fields": {"ستونِ خیالی": "۱"}}],
        })
    assert err.value.status_code == 400


def test_import_is_risky_and_runs_only_through_confirmation(client, db_session):
    """پیشنهادِ ورود هیچ ردیفی نمی‌سازد؛ درج فقط از نقطهٔ تأیید رخ می‌دهد."""
    from app.models.ai import AiPendingAction
    from app.models.evaluation_access import EvaluationAccess
    from app.models.personnel import Personnel

    supervisor = make_user(db_session, "unit_supervisor", username="xu_sup")
    ceo = make_user(db_session, "ceo", username="xu_ceo")
    ceo.full_name = "مدیرعاملِ سازمان"  # تطبیقِ «تنها مدیرعامل» با نامِ اوست
    hr = make_user(db_session, "hr", username="xu_imp", capabilities=[Capability.manage_personnel])
    _enable_ai(db_session, hr)
    db_session.commit()

    conversation_id = _new_conversation(client, hr)
    upload = _upload(
        client,
        hr,
        "people.xlsx",
        _workbook(
            [["X-1", "نفرِ ناقص", "کارشناس", "", "فروش", "خیر", "فعال", "1405/01/01", "", "", "", "xu_sup", "", ""]]
        ),
        conversation_id,
    ).json()
    ctx = _tool_ctx(db_session, hr, conversation_id)

    # تکمیل مقدارِ جاافتاده توسط مدل (پس از پرسیدن از کاربر)
    tools_call(ctx, "patch_upload_rows", {
        "upload_id": upload["id"],
        "edits": [{"row_number": 2, "fields": {"پایان قرارداد": "1406/06/01"}}],
    })

    # ۱) پیشنهاد: اعتبارسنجی می‌شود، چیزی درج نمی‌شود
    proposal = tools_call(ctx, "import_personnel", {"upload_id": upload["id"]})
    payload = json.loads(proposal.content)
    assert payload["ready_for_confirmation"] is True
    assert payload["valid_rows"] == 1
    assert db_session.query(Personnel).filter_by(personnel_code="X-1").count() == 0

    # ۲) تأیید از نقطهٔ رسمی
    pending = AiPendingAction(
        conversation_id=conversation_id,
        user_id=hr.id,
        tool_name="import_personnel",
        arguments_json=json.dumps({"upload_id": upload["id"]}),
        summary="پیشنهاد ورود یک ردیف",
        status="pending",
    )
    ctx.db.add(pending)
    ctx.db.commit()

    from app.models.ai import AiSettings, AiUserAccess
    from app.services.ai import confirmations

    config = ctx.db.get(AiSettings, 1)
    access = ctx.db.query(AiUserAccess).filter_by(user_id=hr.id).one()
    row, summary = confirmations.confirm(ctx.db, user=ctx.user, pending_id=pending.id, config=config, access=access)
    assert row.status == "confirmed"

    person = db_session.query(Personnel).filter_by(personnel_code="X-1").one()
    assert person.status is PersonnelStatus.active
    chain = db_session.query(EvaluationAccess).filter_by(personnel_id=person.id).one()
    assert chain.unit_supervisor_user_id == supervisor.id
    assert chain.ceo_user_id == ceo.id  # ستونِ خالیِ مدیرعامل با تنها مدیرعامل پر شده

    # ۳) ورودِ دوبارهٔ همان فایل ممنوع
    with pytest.raises(HTTPException) as err:
        tools_call(ctx, "import_personnel", {"upload_id": upload["id"]})
    assert err.value.status_code == 400


def test_full_turn_model_proposes_import_and_user_confirms(client, db_session, monkeypatch):
    """مدلِ قلابی سناریو را کامل می‌کند: بازرسی ← پیشنهادِ اصلاح ← تأییدِ کاربر ←
    پیشنهادِ ورود ← تأییدِ کاربر. اصلاحِ لایه هم تغییرِ داده است و مثل ورود،
    فقط با تأییدِ صریح کاربر اجرا می‌شود (H-1)."""
    from app.models.personnel import Personnel

    hr = make_user(db_session, "hr", username="xu_turn", capabilities=[Capability.manage_personnel])
    _enable_ai(db_session, hr)
    conversation_id = _new_conversation(client, hr)
    upload = _upload(client, hr, "people.xlsx", _workbook([BROKEN_ROW]), conversation_id).json()
    monkeypatch.setattr("app.api.routers.ai.OpenAiCompatibleAdapter", ScriptedAdapter)
    reset(ScriptedAdapter)
    ScriptedAdapter.script = [
        response(
            "خطای ردیف ۲ را می‌بینم؛ اصلاحش را پیشنهاد می‌دهم.",
            calls=[
                tool_call("c1", "inspect_upload", {"upload_id": upload["id"]}),
                tool_call("c2", "patch_upload_rows", {
                    "upload_id": upload["id"],
                    "edits": [{"row_number": 2, "fields": {"پایان قرارداد": "1406/07/01"}}],
                }),
            ],
        ),
        response("منتظر تأیید شما برای اصلاح هستم."),
    ]
    body = client.post(
        "/api/ai/chat",
        json={"conversation_id": conversation_id, "message": "این فایل را درست کن و وارد کن"},
        headers=auth_header(hr),
    ).json()

    assert [s["status"] for s in body["steps"]] == ["ok", "awaiting_confirmation"]
    assert len(body["pending"]) == 1
    assert body["pending"][0]["tool"] == "patch_upload_rows"

    # تأییدِ کاربر: اصلاحِ لایه اعمال و اعتبارسنجیِ رسمی از نو اجرا می‌شود
    confirmed = client.post(
        f"/api/ai/pending/{body['pending'][0]['id']}/confirm", headers=auth_header(hr)
    )
    assert confirmed.status_code == 200, confirmed.text

    # نوبت بعدی: مدل پیشنهادِ ورود می‌دهد
    reset(ScriptedAdapter)
    ScriptedAdapter.script = [
        response(
            "آماده است.",
            calls=[tool_call("c3", "import_personnel", {"upload_id": upload["id"]})],
        ),
        response("منتظر تأیید شما برای ورود هستم."),
    ]
    body2 = client.post(
        "/api/ai/chat",
        json={"conversation_id": conversation_id, "message": "خب واردش کن"},
        headers=auth_header(hr),
    ).json()
    assert len(body2["pending"]) == 1
    assert body2["pending"][0]["tool"] == "import_personnel"

    # تأیید کاربر: درج واقعی
    confirmed = client.post(
        f"/api/ai/pending/{body2['pending'][0]['id']}/confirm", headers=auth_header(hr)
    )
    assert confirmed.status_code == 200, confirmed.text

    person = db_session.query(Personnel).filter_by(personnel_code="X-1").one()
    assert person.full_name == "نفرِ ناقص"
    # تاریخِ شمسیِ ۱۴۰۶/۰۷/۰۱ همان ۲۰۲۷-۰۹-۲۳ میلادی است
    from datetime import date

    assert person.contract_end_date == date(2027, 9, 23)


def test_employee_cannot_use_import_tools(client, db_session):
    employee = make_user(db_session, "employee", username="xu_no", capabilities=[])
    db_session.commit()
    ctx = _tool_ctx(db_session, employee)
    with pytest.raises(HTTPException) as err:
        tools_call(ctx, "patch_upload_rows", {"upload_id": 1, "edits": []})
    assert err.value.status_code == 403
