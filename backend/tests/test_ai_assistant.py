"""همکار هوشمند — لایه‌ها، گاردها، و کلِ مسیر.

پوشش نه؛ *این* چند چیز، چون هر کدام یک شکستِ واقعی‌اند.
"""
import json

import pytest

from app.core.crypto import decrypt, encrypt
from app.models.ai import AiSettings, AiUserAccess
from app.models.enums import Capability, UserRole
from app.schemas.auth import CurrentUser
from app.services.ai.prompt import build_system_prompt
from app.services.ai.tools import base as tools_base
from tests.fake_llm import FailingAdapter, NoToolsAdapter, ScriptedAdapter, reset, response, tool_call
from tests.helpers import auth_header, make_user

# ── پروتکلِ جایگزین: تجزیه‌کننده، برابر پاسخ‌هایی که مدل‌ها *واقعاً* می‌دهند ──


def test_fallback_parser_accepts_tool_and_action_shapes():
    blocks = tools_base.parse_fallback_blocks(
        '```pulse\n{"tool": "search_personnel", "arguments": {"q": "احمدی"}}\n```'
    )
    assert blocks == [("search_personnel", {"q": "احمدی"})]

    # شکلِ قدیمیِ action — مدل‌هایی که پرامپتِ قبلی را «از حفظ»اند
    legacy = tools_base.parse_fallback_blocks('```json\n{"action": "find", "query": "x"}\n```')
    assert legacy == [("find", {"query": "x"})]

    # بدون کلیدِ arguments — بقیهٔ کلیدها آرگومان‌اند
    flat = tools_base.parse_fallback_blocks('{"tool": "list_org_units"}')
    assert flat == [("list_org_units", {})]


def test_fallback_parser_ignores_prose_and_broken_json():
    assert tools_base.parse_fallback_blocks("این فقط جمله است.") == []
    assert tools_base.parse_fallback_blocks("```pulse\n{ خراب }\n```") == []


def test_strip_fallback_blocks_leaves_clean_prose():
    text = 'باشه:\n```pulse\n{"tool": "list_org_units"}\n```'
    assert tools_base.strip_fallback_blocks(text) == "باشه:"


def test_openai_schema_matches_registry():
    for spec in tools_base.REGISTRY.values():
        schema = spec.to_openai_schema()
        assert schema["function"]["name"] == spec.name
        assert "description" in schema["function"]


# ── گارد: مجوز در مجری، نه در تبلیغ ───────────────────────────────────────


def _current(user) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        username=user.username,
        role=user.role,
        personnel_id=user.personnel_id,
        must_change_password=False,
        display_name=user.username,
    )


def test_a_tool_the_user_could_not_perform_is_refused(db_session):
    """پرامپت یک پیشنهاد است؛ گارد باید در مجری باشد."""
    from fastapi import HTTPException

    employee = make_user(db_session, "employee", username="ai_emp", capabilities=[])
    db_session.commit()
    ctx_user = _current(employee)

    assert tools_base.is_allowed(tools_base.REGISTRY["search_users"], ctx_user, set()) is False

    spec = tools_base.REGISTRY["search_users"]
    ctx = tools_base.ToolContext(db=db_session, user=ctx_user, caps=frozenset(), conversation_id=0)
    with pytest.raises(HTTPException) as err:
        tools_base.execute_tool(ctx, spec, {"q": ""})
    assert err.value.status_code == 403


def test_allowed_tools_never_offers_writes_when_writes_are_off(db_session):
    user = make_user(db_session, "hr", username="ai_ro", capabilities=[Capability.manage_personnel])
    db_session.commit()
    specs = tools_base.allowed_tools(_current(user), {Capability.manage_personnel}, allow_writes=False)
    assert all(spec.read_only for spec in specs)
    assert any(spec.name == "search_personnel" for spec in specs)
    assert all(spec.name != "create_personnel" for spec in specs)


def test_prompt_only_advertises_tools_the_executor_would_run(db_session):
    """تستی که جلوی «پیشنهادِ مطمئن با دکمهٔ مرده» را می‌گیرد."""
    user = make_user(
        db_session, "hr", username="ai_prompt", capabilities=[Capability.manage_personnel]
    )
    db_session.commit()
    caps = {Capability.manage_personnel}
    specs = tools_base.allowed_tools(_current(user), caps, allow_writes=True)
    prompt = build_system_prompt(
        instructions="x",
        context="y",
        user=_current(user),
        caps=caps,
        allow_writes=True,
        restrict_to_platform=True,
        tools=specs,
    )
    for spec in specs:
        assert spec.name in prompt
    # ابزاری که مجاز نیست، تبلیغ هم نمی‌شود
    assert "grant_capabilities" not in prompt
    assert "search_users" not in prompt


def test_risky_tools_are_always_flagged_for_confirmation():
    """کنش‌های تغییردهندهٔ مهم نباید «خودکار» شوند — نه در هیچ نقشی."""
    for name in ("create_personnel", "separate_personnel", "import_personnel", "advance_evaluation", "grant_capabilities"):
        spec = tools_base.REGISTRY[name]
        assert spec.risky is True, name
        assert spec.read_only is False, name


# ── دسترسی: سه حالتی که در کد یکی به‌نظر می‌رسند ──────────────────────────


def _enable_for(db, user, **access_kwargs):
    db.merge(
        AiSettings(id=1, enabled=True, base_url="http://x", model="m", api_key_encrypted=encrypt("k"))
    )
    db.add(AiUserAccess(user_id=user.id, enabled=True, **access_kwargs))
    db.commit()


def test_status_tells_not_configured_from_not_permitted(client, db_session):
    user = make_user(db_session, "deputy", username="ai_dep", capabilities=[])
    db_session.commit()

    body = client.get("/api/ai/status", headers=auth_header(user)).json()
    assert body["available"] is False
    assert "فعال نیست" in body["reason"]

    config = db_session.get(AiSettings, 1) or AiSettings(id=1)
    config.enabled = True
    config.base_url = "http://x"
    config.model = "m"
    db_session.add(config)
    db_session.commit()
    body = client.get("/api/ai/status", headers=auth_header(user)).json()
    assert "حساب شما" in body["reason"]

    db_session.add(AiUserAccess(user_id=user.id, enabled=True))
    db_session.commit()
    body = client.get("/api/ai/status", headers=auth_header(user)).json()
    assert "کلید" in body["reason"]


def test_settings_need_the_capability_and_never_return_the_key(client, db_session):
    stranger = make_user(db_session, "hr", username="ai_nokey", capabilities=[Capability.manage_users])
    admin = make_user(db_session, "support", username="ai_admin", capabilities=[Capability.manage_ai])
    db_session.commit()

    assert client.get("/api/ai/settings", headers=auth_header(stranger)).status_code == 403

    saved = client.put(
        "/api/ai/settings",
        json={"api_key": "sk-super-secret-1234", "model": "gpt-x"},
        headers=auth_header(admin),
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert "sk-super-secret-1234" not in json.dumps(body, ensure_ascii=False)
    assert body["api_key_configured"] is True
    assert body["api_key_hint"] == "…1234"


def test_the_key_is_encrypted_at_rest(db_session):
    stored = encrypt("sk-plain-value")
    assert "sk-plain-value" not in stored
    assert decrypt(stored) == "sk-plain-value"
    assert decrypt("not-a-real-token") == ""


def test_disabled_users_cannot_chat(client, db_session):
    user = make_user(db_session, "employee", username="ai_off", capabilities=[])
    db_session.merge(AiSettings(id=1, enabled=True, base_url="http://x", model="m",
                                api_key_encrypted=encrypt("k")))
    db_session.commit()
    response = client.post(
        "/api/ai/chat", json={"message": "سلام"}, headers=auth_header(user)
    )
    assert response.status_code == 403
    assert "فعال نشده" in response.json()["detail"]


def test_context_respects_its_size_setting(db_session):
    from app.services.ai import context as context_service

    user = make_user(db_session, "hr", username="ai_ctx", capabilities=[Capability.manage_personnel])
    db_session.commit()
    current = _current(user)

    off = context_service.build(db_session, current, set(), 0)
    assert "خاموش" in off
    assert "## پرسنل" not in off

    on = context_service.build(db_session, current, {Capability.manage_personnel}, 5)
    assert "## شاخص‌های ارزیابی" in on
    assert "خاموش" not in on


def test_a_supervisor_sees_only_their_own_people(db_session):
    from app.services.ai import context as context_service

    supervisor = make_user(db_session, "unit_supervisor", username="ai_sup", capabilities=[])
    db_session.commit()

    text = context_service.build(db_session, _current(supervisor), set(), 50)
    assert "## پرسنل" not in text


# ── حلقهٔ گفت‌وگو: «به هیچ وصل نبودن» و چندپله‌بودن ────────────────────────


def test_the_chat_endpoint_really_reaches_the_adapter(client, db_session, monkeypatch):
    """قابلیتی که به هیچ وصل نباشد، دقیقاً شبیه قابلیتی است که کار می‌کند."""
    from app.services.ai.tools import people  # noqa: F401  (ثبت ابزارها)

    user = make_user(db_session, "hr", username="ai_wired", capabilities=[Capability.manage_personnel])
    _enable_for(db_session, user)
    monkeypatch.setattr("app.api.routers.ai.OpenAiCompatibleAdapter", ScriptedAdapter)
    reset(ScriptedAdapter)
    ScriptedAdapter.script = [
        response(content="می‌جستم…", calls=[tool_call("c1", "search_personnel", {"q": "تست"})]),
        response(content="یک نفر پیدا شد: کارمند تست."),
    ]

    response_body = client.post(
        "/api/ai/chat", json={"message": "کارمند تست کیست؟"}, headers=auth_header(user)
    )

    assert response_body.status_code == 200, response_body.text
    body = response_body.json()
    assert body["reply"] == "یک نفر پیدا شد: کارمند تست."
    assert [s["tool"] for s in body["steps"]] == ["search_personnel"]
    assert body["steps"][0]["status"] == "ok"
    # آداپتور دو بار صدا خورده و در پلهٔ دوم شِمای ابزار داده شده است
    assert len(ScriptedAdapter.seen) == 2


def test_failure_surfaces_the_providers_own_message(client, db_session, monkeypatch):
    """۴۰۱ و «مدل پیدا نشد» دو رفعِ متفاوت‌اند؛ «مشکلی پیش آمد» هیچ‌کدام را نمی‌گوید."""
    user = make_user(db_session, "hr", username="ai_fail", capabilities=[])
    _enable_for(db_session, user)
    monkeypatch.setattr("app.api.routers.ai.OpenAiCompatibleAdapter", FailingAdapter)
    reset(FailingAdapter)

    response_body = client.post("/api/ai/chat", json={"message": "سلام"}, headers=auth_header(user))
    assert response_body.status_code == 502
    assert "Incorrect API key" in response_body.json()["detail"]


def test_unsupported_tool_protocol_falls_back_to_json(client, db_session, monkeypatch):
    """سرویسِ بدونِ tool-calling نباید قابلیت را ببندد؛ پروتکلِ جایگزین می‌آید."""
    user = make_user(db_session, "hr", username="ai_fallback", capabilities=[])
    _enable_for(db_session, user)
    monkeypatch.setattr("app.api.routers.ai.OpenAiCompatibleAdapter", NoToolsAdapter)
    reset(NoToolsAdapter)
    NoToolsAdapter.script = [
        response('واحدها را می‌گیرم:\n```pulse\n{"tool": "list_org_units"}\n```'),
        response("فهرست واحد خالی است."),
    ]

    body = client.post(
        "/api/ai/chat", json={"message": "واحدها چی هستن؟"}, headers=auth_header(user)
    ).json()
    assert body["reply"] == "فهرست واحد خالی است."
    assert [s["tool"] for s in body["steps"]] == ["list_org_units"]


def test_off_platform_answers_are_a_setting(db_session):
    user = make_user(db_session, "hr", username="ai_scope", capabilities=[])
    db_session.commit()
    kwargs = dict(
        instructions="x",
        context="y",
        user=_current(user),
        caps=set(),
        allow_writes=False,
    )
    assert "بیرون از این موضوع" in build_system_prompt(**kwargs, restrict_to_platform=True)
    assert "بیرون از این موضوع" not in build_system_prompt(**kwargs, restrict_to_platform=False)


def test_the_user_never_sees_the_raw_json_block():
    reply = 'باشه:\n```pulse\n{"tool": "list_org_units"}\n```'
    assert tools_base.strip_fallback_blocks(reply) == "باشه:"


# ── ابزارهای پرخطر: پیشنهاد می‌شوند، اجرا نمی‌شوند ────────────────────────


def test_a_risky_tool_becomes_a_pending_action_and_only_confirmation_runs_it(client, db_session, monkeypatch):
    """مهم‌ترین تست این قابلیت.

    پاسخ مدل ذخیره می‌شود و هیچ ردیفی ساخته نمی‌شود؛ ردیف فقط وقتی می‌آید که
    کاربر کارتِ تأیید را بپذیرد.
    """
    from app.models.ai import AiPendingAction
    from app.models.personnel import Personnel

    admin = make_user(
        db_session, "hr", username="ai_hr", capabilities=[Capability.manage_personnel]
    )
    _enable_for(db_session, admin)
    monkeypatch.setattr("app.api.routers.ai.OpenAiCompatibleAdapter", ScriptedAdapter)
    reset(ScriptedAdapter)
    ScriptedAdapter.script = [
        response(
            "این کار را پیشنهاد می‌دهم.",
            calls=[
                tool_call(
                    "c1",
                    "create_personnel",
                    {
                        "full_name": "کاربر تأییدنشده",
                        "personnel_code": "AI-TEST-1",
                        "job_title": "کارشناس",
                        "org_unit": "فروش",
                        "contract_end_date": "2027-06-01",
                    },
                )
            ],
        ),
        response("منتظر تأیید شما هستم."),
    ]

    assert db_session.query(Personnel).filter_by(personnel_code="AI-TEST-1").count() == 0

    body = client.post(
        "/api/ai/chat", json={"message": "این فرد را ثبت کن"}, headers=auth_header(admin)
    ).json()

    assert db_session.query(Personnel).filter_by(personnel_code="AI-TEST-1").count() == 0
    assert len(body["pending"]) == 1
    pending_id = body["pending"][0]["id"]
    assert body["pending"][0]["status"] == "pending"
    assert db_session.get(AiPendingAction, pending_id).status == "pending"

    # تأیید: تنها راهِ ساخته‌شدنِ ردیف
    confirmed = client.post(
        f"/api/ai/pending/{pending_id}/confirm", headers=auth_header(admin)
    )
    assert confirmed.status_code == 200, confirmed.text
    assert db_session.query(Personnel).filter_by(personnel_code="AI-TEST-1").count() == 1

    # تأییدِ دوباره: ۴۰۹ — هر پیشنهاد فقط یک‌بار اجرا می‌شود
    again = client.post(f"/api/ai/pending/{pending_id}/confirm", headers=auth_header(admin))
    assert again.status_code == 409


def test_pending_action_cannot_be_confirmed_without_permission(client, db_session):
    """مجوز در لحظهٔ تأیید هم سنجیده می‌شود، نه فقط در لحظهٔ پیشنهاد."""
    from app.models.ai import AiPendingAction

    user = make_user(db_session, "employee", username="ai_np", capabilities=[])
    _enable_for(db_session, user)
    convo = __import__("app.models.ai", fromlist=["AiConversation"]).AiConversation(user_id=user.id, title="t")
    db_session.add(convo)
    db_session.flush()
    row = AiPendingAction(
        conversation_id=convo.id,
        user_id=user.id,
        tool_name="create_personnel",
        arguments_json=json.dumps({"full_name": "x", "personnel_code": "Y-1", "job_title": "j", "org_unit": "u", "contract_end_date": "2026-01-01"}),
        status="pending",
    )
    db_session.add(row)
    db_session.commit()

    response_body = client.post(f"/api/ai/pending/{row.id}/confirm", headers=auth_header(user))
    assert response_body.status_code == 403
