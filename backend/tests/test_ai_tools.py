"""ابزارها: ماتریسِ مجوز، دامنهٔ دید سطری، و کفّیتِ کارتِ تأیید.

هر تست این‌جا یک پرسش ساده دارد: اگر کاربری در رابط نمی‌توانست این کار را
بکند، آیا از راهِ دستیار هم نمی‌تواند؟
"""
import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.models.ai import AiPendingAction
from app.models.enums import Capability, UserRole
from app.schemas.auth import CurrentUser
from app.services.ai.tools import base as tools_base
from tests.helpers import make_user, make_personnel


def _ctx(db, user: object, caps=None) -> tools_base.ToolContext:
    return tools_base.ToolContext(
        db=db,
        user=CurrentUser(
            id=user.id,
            username=user.username,
            role=user.role,
            personnel_id=user.personnel_id,
            must_change_password=False,
            display_name=user.username,
        ),
        caps=frozenset(caps or set()),
        conversation_id=0,
    )


# ── ماتریسِ مجوز ───────────────────────────────────────────────────────────


def test_employee_reads_own_scope_only(db_session):
    employee = make_user(db_session, "employee", username="tool_emp", capabilities=[])
    db_session.commit()
    ctx = _ctx(db_session, employee)

    # جست‌وجوی پرسنل برای کارمندِ بدون زنجیره = هیچ
    outcome = tools_base.execute_tool(ctx, tools_base.REGISTRY["search_personnel"], {"q": ""})
    payload = json.loads(outcome.content)
    assert payload["matches"] == 0

    # جست‌وجوی حساب‌ها = ۴۰۳
    with pytest.raises(HTTPException) as err:
        tools_base.execute_tool(ctx, tools_base.REGISTRY["search_users"], {})
    assert err.value.status_code == 403

    # گزارش منابع انسانی = ۴۰۳
    with pytest.raises(HTTPException) as err:
        tools_base.execute_tool(ctx, tools_base.REGISTRY["report_summary"], {})
    assert err.value.status_code == 403


def test_supervisor_scoping_matches_the_ui_allowlist(db_session):
    """مسئول واحد فقط پرونده‌های زنجیرهٔ خودش را می‌بیند — همان allowlist رابط."""
    from app.models.evaluation import EvaluationRecord
    from tests.helpers import make_access

    supervisor = make_user(db_session, "unit_supervisor", username="tool_sup")
    stranger_supervisor = make_user(db_session, "unit_supervisor", username="tool_sup2")
    deputy = make_user(db_session, "deputy", username="tool_dep")
    ceo = make_user(db_session, "ceo", username="tool_ceo")
    mine = make_personnel(db_session, full_name="زیرِ دستِ من")
    others = make_personnel(db_session, full_name="زیرِ دستِ دیگری")
    make_access(db_session, mine, supervisor, deputy, ceo)
    make_access(db_session, others, stranger_supervisor, deputy, ceo)
    db_session.add(EvaluationRecord(
        evaluation_code="EVL-T1", subject_personnel_id=mine.id,
        unit_supervisor_user_id=supervisor.id, deputy_user_id=deputy.id, ceo_user_id=ceo.id,
        status=UserRole.employee and __import__("app.models.enums", fromlist=["EvaluationStatus"]).EvaluationStatus.draft,
    ))
    db_session.add(EvaluationRecord(
        evaluation_code="EVL-T2", subject_personnel_id=others.id,
        unit_supervisor_user_id=stranger_supervisor.id, deputy_user_id=deputy.id, ceo_user_id=ceo.id,
        status=__import__("app.models.enums", fromlist=["EvaluationStatus"]).EvaluationStatus.draft,
    ))
    db_session.commit()

    ctx = _ctx(db_session, supervisor)
    outcome = tools_base.execute_tool(ctx, tools_base.REGISTRY["search_evaluations"], {})
    codes = [item["evaluation_code"] for item in json.loads(outcome.content)["evaluations"]]
    assert "EVL-T1" in codes
    assert "EVL-T2" not in codes


def test_support_role_has_no_access_to_case_files(db_session):
    """نقش پشتیبانی فنی به هیچ پرونده‌ای دسترسی ندارد — نه در رابط نه این‌جا."""
    support = make_user(db_session, "support", username="tool_support", capabilities=[])
    db_session.commit()
    ctx = _ctx(db_session, support)
    with pytest.raises(HTTPException) as err:
        tools_base.execute_tool(ctx, tools_base.REGISTRY["search_evaluations"], {})
    assert err.value.status_code == 403


def test_create_evaluation_requires_the_real_chain_seat(db_session):
    """آغاز ارزیابی فقط از مسئولِ واقعیِ زنجیره — گاردِ داخل endpointِ رسمی."""
    from app.models.evaluation_access import EvaluationAccess
    from tests.helpers import make_access

    supervisor = make_user(db_session, "unit_supervisor", username="tool_sup3")
    stranger = make_user(db_session, "unit_supervisor", username="tool_sup4")
    deputy = make_user(db_session, "deputy", username="tool_dep2")
    ceo = make_user(db_session, "ceo", username="tool_ceo2")
    person = make_personnel(db_session, full_name="کارمندِ زنجیره‌دار")
    make_access(db_session, person, supervisor, deputy, ceo)
    db_session.commit()

    ctx = _ctx(db_session, stranger)
    with pytest.raises(HTTPException) as err:
        tools_base.execute_tool(
            ctx, tools_base.REGISTRY["create_evaluation"], {"personnel_id": person.id}
        )
    assert err.value.status_code == 403

    # خودِ مسئول مجاز است
    outcome = tools_base.execute_tool(
        ctx if False else _ctx(db_session, supervisor), tools_base.REGISTRY["create_evaluation"], {"personnel_id": person.id}
    )
    payload = json.loads(outcome.content)
    assert payload["created"] is True


# ── پیشنهاد → تأیید: چرخهٔ کاملِ یک کنش پرخطر ──────────────────────────────


def _make_pending(db, user, tool="create_personnel", arguments=None, status="pending", expires=None) -> AiPendingAction:
    from app.models.ai import AiConversation

    convo = AiConversation(user_id=user.id, title="t")
    db.add(convo)
    db.flush()
    row = AiPendingAction(
        conversation_id=convo.id,
        user_id=user.id,
        tool_name=tool,
        arguments_json=json.dumps(arguments or {
            "full_name": "آزمون", "personnel_code": "PT-TZ-1", "job_title": "کارشناس",
            "org_unit": "واحد تست", "contract_end_date": "2027-01-01",
        }),
        summary="پیشنهاد آزمایشی",
        status=status,
        expires_at=expires or (datetime.now(UTC) + timedelta(hours=24)),
    )
    db.add(row)
    db.commit()
    return row


def test_confirm_runs_the_real_action_and_writes_an_assistant_message(client, db_session):
    from app.models.ai import AiMessage
    from app.models.personnel import Personnel

    hr = make_user(db_session, "hr", username="tool_cf", capabilities=[Capability.manage_personnel])
    db_session.merge(__import__("app.models.ai", fromlist=["AiSettings"]).AiSettings(
        id=1, enabled=True, base_url="http://x", model="m", api_key_encrypted=__import__("app.core.crypto", fromlist=["encrypt"]).encrypt("k")
    ))
    db_session.add(__import__("app.models.ai", fromlist=["AiUserAccess"]).AiUserAccess(user_id=hr.id, enabled=True))
    row = _make_pending(db_session, hr)
    code = json.loads(row.arguments_json)["personnel_code"]

    response = client.post(f"/api/ai/pending/{row.id}/confirm", headers=auth_header_of(hr))
    assert response.status_code == 200, response.text
    assert db_session.query(Personnel).filter_by(personnel_code=code).count() == 1

    refreshed = db_session.get(AiPendingAction, row.id)
    assert refreshed.status == "confirmed"

    # پیامِ دستیارِ نتیجه در گفت‌وگو ثبت شده باشد
    messages = db_session.query(AiMessage).filter_by(conversation_id=row.conversation_id).all()
    assert any("✅" in m.content for m in messages)


def auth_header_of(user):
    from app.core.security import create_access_token

    return {"Authorization": "Bearer " + create_access_token(user.id, user.role.value, user.token_version)}


def test_reject_leaves_no_trace_in_data(client, db_session):
    from app.models.personnel import Personnel

    hr = make_user(db_session, "hr", username="tool_rj", capabilities=[Capability.manage_personnel])
    db_session.merge(__import__("app.models.ai", fromlist=["AiSettings"]).AiSettings(
        id=1, enabled=True, base_url="http://x", model="m", api_key_encrypted=__import__("app.core.crypto", fromlist=["encrypt"]).encrypt("k")
    ))
    db_session.add(__import__("app.models.ai", fromlist=["AiUserAccess"]).AiUserAccess(user_id=hr.id, enabled=True))
    db_session.commit()
    row = _make_pending(db_session, hr)
    code = json.loads(row.arguments_json)["personnel_code"]

    response = client.post(f"/api/ai/pending/{row.id}/reject", headers=auth_header_of(hr))
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert db_session.query(Personnel).filter_by(personnel_code=code).count() == 0


def test_expired_pending_is_declined(client, db_session):
    hr = make_user(db_session, "hr", username="tool_exp", capabilities=[Capability.manage_personnel])
    db_session.merge(__import__("app.models.ai", fromlist=["AiSettings"]).AiSettings(
        id=1, enabled=True, base_url="http://x", model="m", api_key_encrypted=__import__("app.core.crypto", fromlist=["encrypt"]).encrypt("k")
    ))
    db_session.add(__import__("app.models.ai", fromlist=["AiUserAccess"]).AiUserAccess(user_id=hr.id, enabled=True))
    db_session.commit()
    row = _make_pending(
        db_session, hr,
        expires=datetime.now(UTC) - timedelta(hours=1),
    )
    response = client.post(f"/api/ai/pending/{row.id}/confirm", headers=auth_header_of(hr))
    assert response.status_code == 410
    assert db_session.get(AiPendingAction, row.id).status == "expired"


def test_someone_elses_pending_is_not_found(client, db_session):
    owner = make_user(db_session, "hr", username="tool_owner", capabilities=[Capability.manage_personnel])
    stranger = make_user(db_session, "hr", username="tool_stranger", capabilities=[Capability.manage_personnel])
    db_session.merge(__import__("app.models.ai", fromlist=["AiSettings"]).AiSettings(
        id=1, enabled=True, base_url="http://x", model="m", api_key_encrypted=__import__("app.core.crypto", fromlist=["encrypt"]).encrypt("k")
    ))
    db_session.add(__import__("app.models.ai", fromlist=["AiUserAccess"]).AiUserAccess(user_id=stranger.id, enabled=True))
    db_session.commit()
    row = _make_pending(db_session, owner)

    response = client.post(f"/api/ai/pending/{row.id}/confirm", headers=auth_header_of(stranger))
    assert response.status_code == 404
