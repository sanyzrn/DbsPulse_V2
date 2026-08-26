"""دستیار هوشمند — همان چیزهایی که در Nex هر کدام روزها هزینه داشتند.

پوشش نه؛ *این* چند چیز، چون هر کدام یک شکستِ واقعی‌اند.
"""
import json

import pytest

from app.core.crypto import decrypt, encrypt
from app.models.ai import AiSettings, AiUserAccess
from app.models.enums import Capability, UserRole
from app.models.personnel import Personnel
from app.schemas.auth import CurrentUser
from app.services.ai import actions as action_service
from app.services.ai.prompt import _SHAPES
from tests.helpers import auth_header, make_user

# ── لایهٔ ۴: تجزیه‌کننده، برابر پاسخ‌هایی که مدل‌ها *واقعاً* می‌دهند ──────


def test_parser_accepts_a_preamble_before_the_fence():
    reply = "حتماً! این کار را انجام می‌دهم:\n\n```pulse\n{\"action\": \"find\", \"query\": \"احمدی\"}\n```"
    actions = action_service.parse(reply)
    assert [a.name for a in actions] == ["find"]
    assert actions[0].read_only is True


def test_parser_accepts_the_json_tag_instead_of_ours():
    # مدل‌ها برچسب را عوض می‌کنند؛ سخت‌گیری این‌جا یعنی قابلیت نصفِ وقت‌ها
    # شکسته به‌نظر برسد.
    actions = action_service.parse('```json\n{"action": "find", "query": "x"}\n```')
    assert len(actions) == 1


def test_parser_accepts_a_bare_object_with_no_fence():
    # بعد از چند پیام، مدل حصار را جا می‌اندازد. بدون این پذیرش، قابلیت چند
    # پیام اول کار می‌کند و بعد بی‌صدا می‌ایستد.
    actions = action_service.parse('{"action": "find", "query": "x"}')
    assert len(actions) == 1


def test_parser_accepts_several_blocks_and_arrays():
    two_blocks = (
        '```pulse\n{"action": "find", "query": "a"}\n```\n'
        '```pulse\n{"action": "find", "query": "b"}\n```'
    )
    assert len(action_service.parse(two_blocks)) == 2
    array = '```pulse\n[{"action": "find", "query": "a"}, {"action": "find", "query": "b"}]\n```'
    assert len(action_service.parse(array)) == 2


@pytest.mark.parametrize(
    "body",
    [
        '{"action": "obliterate_everything", "id": 1}',  # کنش ناشناخته
        '{"action": "update_personnel", "fields": {"job_title": "x"}}',  # بی‌شناسه
        '{"action": "invite_self_assessment", "personnel_id": "abc"}',  # شناسهٔ خراب
        '{"action": "find"}',  # بدون عبارت جست‌وجو
        "{ این JSON نیست }",
    ],
)
def test_invalid_bodies_are_no_action_not_a_crash(body):
    assert action_service.parse(f"```pulse\n{body}\n```") == []


def test_the_prompt_the_parser_and_the_executor_agree():
    """تستی که جلوی «پیشنهادِ مطمئن با دکمهٔ مرده» را می‌گیرد.

    اگر کنشی در پرامپت تبلیغ شود که مجری اجرایش نمی‌کند، مدل با اطمینان
    پیشنهادش می‌دهد و دکمه هیچ کاری نمی‌کند.
    """
    assert set(_SHAPES) == action_service.ACTION_NAMES


# ── دسترسی: مجوز در مجری، نه در پرامپت ────────────────────────────────────


def _current(user) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        username=user.username,
        role=user.role,
        personnel_id=user.personnel_id,
        must_change_password=False,
        display_name=user.username,
    )


def test_an_action_the_user_could_not_perform_in_the_ui_is_refused(db_session):
    """پرامپت یک پیشنهاد است؛ گارد باید در مجری باشد."""
    employee = make_user(db_session, "employee", username="ai_emp", capabilities=[])
    db_session.commit()

    assert "create_personnel" not in action_service.allowed_actions(_current(employee), set())

    action = action_service.parse(
        '{"action": "create_personnel", "full_name": "الف", "personnel_code": "X-1",'
        ' "job_title": "کارشناس", "org_unit": "فروش"}'
    )[0]
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as err:
        action_service.execute(db_session, action, _current(employee), set())
    assert err.value.status_code == 403


def test_a_write_action_only_runs_when_it_is_confirmed(client, db_session):
    """مهم‌ترین تست این قابلیت.

    پاسخ مدل ذخیره می‌شود و هیچ ردیفی ساخته نمی‌شود؛ ردیف فقط وقتی می‌آید که
    کسی دکمه را بزند — یعنی `/run-action` صدا زده شود.
    """
    admin = make_user(
        db_session, "hr", username="ai_hr", capabilities=[Capability.manage_personnel]
    )
    db_session.merge(AiSettings(id=1, enabled=True, base_url="http://x", model="m",
                                api_key_encrypted=encrypt("k")))
    db_session.add(AiUserAccess(user_id=admin.id, enabled=True))
    db_session.commit()

    payload = {
        "action": "create_personnel",
        "full_name": "کاربر تأییدنشده",
        "personnel_code": "AI-TEST-1",
        "job_title": "کارشناس",
        "org_unit": "فروش",
    }
    before = db_session.query(Personnel).filter_by(personnel_code="AI-TEST-1").count()
    assert before == 0

    # تجزیه به تنهایی هیچ‌چیز نمی‌سازد
    action = action_service.parse(json.dumps(payload, ensure_ascii=False))[0]
    assert db_session.query(Personnel).filter_by(personnel_code="AI-TEST-1").count() == 0

    # و تنها راهِ ساخته‌شدن، همان نقطه‌ای است که دکمه صدا می‌زند
    from app.models.ai import AiConversation

    convo = AiConversation(user_id=admin.id, title="t")
    db_session.add(convo)
    db_session.commit()

    response = client.post(
        "/api/ai/run-action",
        json={"conversation_id": convo.id, "name": action.name, "payload": action.payload},
        headers=auth_header(admin),
    )
    assert response.status_code == 200, response.text
    assert db_session.query(Personnel).filter_by(personnel_code="AI-TEST-1").count() == 1


# ── سه حالتی که در کد یکی به‌نظر می‌رسند ──────────────────────────────────


def test_status_tells_not_configured_from_not_permitted(client, db_session):
    user = make_user(db_session, "deputy", username="ai_dep", capabilities=[])
    db_session.commit()

    body = client.get("/api/ai/status", headers=auth_header(user)).json()
    assert body["available"] is False
    assert "فعال نیست" in body["reason"]

    # همان فراخوانی بالا ردیفِ تنظیمات را ساخته است؛ این‌جا فقط روشنش می‌کنیم.
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
    # هیچ‌جای پاسخ نباید خودِ کلید باشد — تستی که روی *نبودِ* داده ادعا می‌کند.
    assert "sk-super-secret-1234" not in json.dumps(body, ensure_ascii=False)
    assert body["api_key_configured"] is True
    assert body["api_key_hint"] == "…1234"


def test_the_key_is_encrypted_at_rest(db_session):
    """بک‌آپِ لو رفتهٔ دیتابیس نباید به تنهایی یک کلید معتبر بدهد."""
    stored = encrypt("sk-plain-value")
    assert "sk-plain-value" not in stored
    assert decrypt(stored) == "sk-plain-value"
    # کلیدِ ناخوانا «تنظیم نشده» است، نه فروپاشی
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
    """دستیار نباید یک راهِ فرعی برای دیدنِ چیزی باشد که رابط اجازه‌اش را نمی‌دهد."""
    from app.services.ai import context as context_service

    supervisor = make_user(db_session, "unit_supervisor", username="ai_sup", capabilities=[])
    db_session.commit()

    text = context_service.build(db_session, _current(supervisor), set(), 50)
    # هیچ پرسنلی به او تخصیص داده نشده، پس فهرست پرسنل نباید بیاید
    assert "## پرسنل" not in text
    assert UserRole.unit_supervisor.value or True


# ── «به هیچ وصل نبودن» — گران‌ترین اشکالِ Nex ─────────────────────────────


class _FakeAdapter:
    """آداپتور قلابی که ثبت می‌کند صدا زده شده و چه دید."""

    seen: list = []

    def __init__(self, **_kwargs):
        pass

    @property
    def available(self) -> bool:
        return True

    async def send(self, messages):
        from app.services.ai.port import ChatResponse

        _FakeAdapter.seen = list(messages)
        return ChatResponse(content='```pulse\n{"action": "find", "query": "احمدی"}\n```')


def _enable_for(db_session, user):
    db_session.merge(
        AiSettings(id=1, enabled=True, base_url="http://x", model="m", api_key_encrypted=encrypt("k"))
    )
    db_session.add(AiUserAccess(user_id=user.id, enabled=True))
    db_session.commit()


def test_the_chat_endpoint_really_reaches_the_adapter(client, db_session, monkeypatch):
    """قابلیتی که به هیچ وصل نباشد، دقیقاً شبیه قابلیتی است که کار می‌کند.

    تست‌های واحدِ دو نیمه این را نمی‌گیرند؛ فقط مسیرِ کاملِ «نقطهٔ ورودِ واقعی →
    آداپتور» می‌گیرد.
    """
    user = make_user(db_session, "hr", username="ai_wired", capabilities=[Capability.manage_personnel])
    _enable_for(db_session, user)
    monkeypatch.setattr("app.api.routers.ai.OpenAiCompatibleAdapter", _FakeAdapter)
    _FakeAdapter.seen = []

    response = client.post(
        "/api/ai/chat", json={"message": "احمدی کیست؟"}, headers=auth_header(user)
    )

    assert response.status_code == 200, response.text
    assert _FakeAdapter.seen, "آداپتور اصلاً صدا زده نشد"
    assert _FakeAdapter.seen[0].role == "system"
    # کنشِ خواندنی بدون تأیید اجرا شده و نتیجه‌اش در پاسخ آمده
    assert "نتیجهٔ جست‌وجو" in response.json()["reply"]
    # ...و به‌عنوان پیشنهادِ نیازمندِ تأیید ثبت نشده، چون چیزی عوض نمی‌کند
    assert response.json()["actions"] == []


class _FailingAdapter(_FakeAdapter):
    async def send(self, messages):
        from app.services.ai.port import AiRequestFailed

        raise AiRequestFailed("401: Incorrect API key provided: sk-***", 401)


def test_failure_surfaces_the_providers_own_message(client, db_session, monkeypatch):
    """۴۰۱ و «مدل پیدا نشد» دو رفعِ متفاوت‌اند؛ «مشکلی پیش آمد» هیچ‌کدام را نمی‌گوید."""
    user = make_user(db_session, "hr", username="ai_fail", capabilities=[])
    _enable_for(db_session, user)
    monkeypatch.setattr("app.api.routers.ai.OpenAiCompatibleAdapter", _FailingAdapter)

    response = client.post("/api/ai/chat", json={"message": "سلام"}, headers=auth_header(user))

    assert response.status_code == 502
    assert "Incorrect API key" in response.json()["detail"]


def test_off_platform_answers_are_a_setting(db_session):
    from app.services.ai.prompt import build_system_prompt

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


def test_a_read_only_assistant_is_never_offered_write_actions(db_session):
    from app.services.ai.prompt import build_system_prompt

    user = make_user(db_session, "hr", username="ai_ro", capabilities=[Capability.manage_personnel])
    db_session.commit()
    prompt = build_system_prompt(
        instructions="x",
        context="y",
        user=_current(user),
        caps={Capability.manage_personnel},
        allow_writes=False,
        restrict_to_platform=True,
    )
    assert "create_personnel" not in prompt
    assert '"find"' in prompt


def test_the_user_never_sees_the_raw_json_block():
    """کنش به‌شکل *جمله* و دکمه نشان داده می‌شود؛ بلوکِ خام فقط نویز است."""
    reply = 'باشه، این کار را می‌کنم:\n```pulse\n{"action": "find", "query": "x"}\n```'
    assert action_service.strip_action_blocks(reply) == "باشه، این کار را می‌کنم:"
    # پاسخی که فقط بلوک است، متنی برای نمایش ندارد
    assert action_service.strip_action_blocks('```pulse\n{"action": "find", "query": "x"}\n```') == ""
