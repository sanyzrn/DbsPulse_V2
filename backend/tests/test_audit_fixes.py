"""رگرسیونِ یافته‌های ممیزی v1.0.1 — هر تست یک یافته را می‌بندد.

C-1  نهایی‌سازی بدون نتیجه ممنوع + ساختِ دسته‌ایِ مدیران در `draft`
C-2  دامنهٔ دیدِ my_open_cases برای کارمند و معاونت
H-1  همهٔ ابزارهای نوشتنی پرخطرند + سوییچِ نوشتن در لحظهٔ اجرا
H-2  سازنده ≠ فعال‌کننده، داخلِ سرویس
H-3  شکستِ کنش تأییدشده نوشته‌های ناقص را کامیت نمی‌کند
M-1  بازکردنِ پرونده روی صندلیِ غیرفعال ممنوع
M-7  claimingِ تأیید اتمی است؛ اجرا دوبار رخ نمی‌دهد
M-8  پاک‌سازیِ آرگومان‌های لاگ ممیزی بازگشتی است
M-10 قفلِ رهبریِ زمان‌بند با کامیتِ میانه نشت نمی‌کند
"""

# NOTE: بخش‌های مربوط به C-2 و H-1 و H-2 و H-3 و M-7 و M-8 در همین فایل‌اند؛
# C-1 (ساختِ دسته‌ای) در test_bulk_create.py به‌روز شده است.

import json
import threading
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.crypto import encrypt
from app.models.ai import AiPendingAction, AiSettings, AiUserAccess
from app.models.enums import Capability, EvaluationStatus, SchemeStatus
from app.models.evaluation import EvaluationRecord
from app.models.personnel import Personnel
from app.schemas.auth import CurrentUser
from app.services.ai import confirmations
from app.services.ai.tools import base as tools_base
from app.services.ai.tools.base import ToolContext, execute_tool
from app.services.scoring_scheme import activate, next_version
from tests.helpers import auth_header, make_access, make_personnel, make_user

# ── ابزارهای کمکیِ همین فایل ────────────────────────────────────────────────


def _ctx(db, user: object, caps=None, allow_writes=True) -> ToolContext:
    return ToolContext(
        db=db,
        user=CurrentUser(
            id=user.id,
            username=user.username,
            role=user.role,
            personnel_id=user.personnel_id,
            must_change_password=False,
            display_name=user.username,
        ),
        caps=frozenset(caps if caps is not None else []),
        conversation_id=0,
        allow_writes=allow_writes,
    )


@pytest.fixture()
def synthetic_tool():
    """ثبتِ ابزارِ آزمایشی در رجیستری — با پاک‌سازیِ تضمینی."""
    added: list[str] = []

    def _add(name, fn, *, read_only=False, risky=False, caps=(), roles=(), parameters=None):
        tools_base.tool(
            name=name,
            description="ابزارِ آزمایشیِ تست",
            category="تست",
            read_only=read_only,
            risky=risky,
            capabilities=caps,
            roles=roles,
            parameters=parameters or {"type": "object", "properties": {}},
        )(fn)
        added.append(name)
        return fn

    yield _add
    for name in added:
        tools_base.REGISTRY.pop(name, None)


_PARTIAL_CODE = "P-AUDIT-PARTIAL"


def _write_partial_row(db) -> None:
    """نوشتهٔ ناقصِ نمونه: ردیفی که اگر تراکنش درست بسته نشود، باید می‌ماند."""
    db.add(
        Personnel(
            personnel_code=_PARTIAL_CODE,
            full_name="نوشتهٔ ناقص",
            job_title="کارشناس",
            org_unit="واحد تست",
            contract_start_date=date(2025, 1, 1),
            contract_end_date=date(2026, 12, 31),
        )
    )
    db.flush()


def _personnel_marker_exists(db) -> bool:
    return (
        db.scalar(select(Personnel).where(Personnel.personnel_code == _PARTIAL_CODE)) is not None
    )


def _enable_ai(db, user) -> tuple[AiSettings, AiUserAccess]:
    db.merge(
        AiSettings(
            id=1,
            enabled=True,
            base_url="http://x",
            model="m",
            api_key_encrypted=encrypt("k"),
        )
    )
    access = AiUserAccess(user_id=user.id, enabled=True)
    db.add(access)
    db.flush()
    return db.get(AiSettings, 1), access


def _make_pending(db, user, tool: str, arguments: dict | None = None) -> AiPendingAction:
    from app.models.ai import AiConversation

    convo = AiConversation(user_id=user.id, title="t")
    db.add(convo)
    db.flush()
    row = AiPendingAction(
        conversation_id=convo.id,
        user_id=user.id,
        tool_name=tool,
        arguments_json=json.dumps(arguments or {}),
        summary="پیشنهادِ آزمایشی",
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(row)
    db.flush()
    return row


# ── C-1: نهایی‌سازی بدون نتیجه ممنوع (گاردِ apply_transition) ───────────────


def test_finalizing_a_case_without_results_is_refused(client, db_session):
    """پرونده‌ای که نتیجهٔ محاسبه‌شده ندارد (رکوردِ خرابِ مسیرِ قدیمیِ دسته‌ای)
    هرگز «نهایی‌شده» نمی‌شود — نه از رابط، نه از دستیار؛ هر دو از
    apply_transition می‌گذرند."""
    from app.models.evaluation import EvaluationScore

    sup = make_user(db_session, "unit_supervisor", username="af_sup")
    dep = make_user(db_session, "deputy", username="af_dep")
    ceo = make_user(db_session, "ceo", username="af_ceo")
    person = make_personnel(db_session, full_name="کارمندِ گاردِ نتیجه")
    make_access(db_session, person, sup, dep, ceo)
    db_session.commit()

    evaluation = client.post(
        "/api/evaluations", json={"subject_personnel_id": person.id}, headers=auth_header(sup)
    ).json()

    # شبیه‌سازیِ رکوردِ خرابِ legacy: به deputy_approved رسیده ولی نتیجه و
    # امتیازی ندارد — دقیقاً آنچه مسیرِ باگ‌دارِ دسته‌ای می‌ساخت.
    record = db_session.get(EvaluationRecord, evaluation["id"])
    record.status = EvaluationStatus.deputy_approved
    db_session.query(EvaluationScore).filter(
        EvaluationScore.evaluation_record_id == record.id
    ).delete()
    record.final_weighted_pct = None
    db_session.commit()

    response = client.post(f"/api/evaluations/{record.id}/ceo-finalize", headers=auth_header(ceo))

    assert response.status_code == 400, response.text
    db_session.refresh(record)
    assert record.status is EvaluationStatus.deputy_approved, "پرونده نهایی نشد"


# ── C-2: دامنهٔ دیدِ my_open_cases ───────────────────────────────────────────


def test_employee_sees_only_their_own_finalized_cases(db_session):
    """کارمندِ دستیارِ فعال فقط نتیجهٔ نهاییِ *خودش* را می‌بیند؛ پیش از این
    نمره و پیشنهادِ کل سازمان برمی‌گشت."""
    from tests.helpers import make_user as mk

    stranger = make_personnel(db_session, full_name="همکارِ غریبه")
    mine = make_personnel(db_session, full_name="خودِ کارمند")
    employee = mk(db_session, "employee", username="af_emp", personnel_id=mine.id)
    db_session.commit()

    sup = mk(db_session, "unit_supervisor", username="af_emp_sup")
    dep = mk(db_session, "deputy", username="af_emp_dep")
    ceo = mk(db_session, "ceo", username="af_emp_ceo")
    make_access(db_session, stranger, sup, dep, ceo)
    make_access(db_session, mine, sup, dep, ceo)
    db_session.add(
        EvaluationRecord(
            evaluation_code="EVL-AF1",
            subject_personnel_id=stranger.id,
            unit_supervisor_user_id=sup.id,
            deputy_user_id=dep.id,
            ceo_user_id=ceo.id,
            status=EvaluationStatus.finalized,
            final_weighted_pct=91.0,
            recommendation="تمدید ممتاز",
        )
    )
    db_session.add(
        EvaluationRecord(
            evaluation_code="EVL-AF2",
            subject_personnel_id=mine.id,
            unit_supervisor_user_id=sup.id,
            deputy_user_id=dep.id,
            ceo_user_id=ceo.id,
            status=EvaluationStatus.finalized,
            final_weighted_pct=72.0,
            recommendation="تمدید",
        )
    )
    db_session.commit()

    outcome = tools_base.execute_tool(
        _ctx(db_session, employee), tools_base.REGISTRY["my_open_cases"], {}
    )
    payload = json.loads(outcome.content)
    codes = [case["evaluation_code"] for case in payload["cases"]]

    assert codes == ["EVL-AF2"], "کارمند فقط پروندهٔ خودش را می‌بیند"


def test_employee_without_personnel_row_sees_nothing(db_session):
    employee = make_user(db_session, "employee", username="af_emp2", capabilities=[])
    db_session.commit()

    outcome = tools_base.execute_tool(
        _ctx(db_session, employee), tools_base.REGISTRY["my_open_cases"], {}
    )
    assert json.loads(outcome.content)["count"] == 0


def test_deputy_sees_only_their_own_seats_cases(db_session):
    """هر معاونت فقط پرونده‌های صندلیِ خودش: هم صفِ hr_approved و هم
    نمره‌دهیِ در جریانِ مسیرِ مدیر. پیش از این پالِ hr_approved بی‌فیلترِ
    مالک بود و پروندهٔ معاونت‌های دیگر را هم نشان می‌داد."""
    from tests.helpers import make_user as mk

    dep_a = mk(db_session, "deputy", username="af_dep_a")
    dep_b = mk(db_session, "deputy", username="af_dep_b")
    sup = mk(db_session, "unit_supervisor", username="af_dep_sup")
    ceo = mk(db_session, "ceo", username="af_dep_ceo")

    p_for_a = make_personnel(db_session, full_name="زیرِ معاونت الف")
    p_for_b = make_personnel(db_session, full_name="زیرِ معاونت ب")
    manager_for_a = make_personnel(
        db_session, full_name="مدیرِ معاونت الف", is_manager=True
    )
    make_access(db_session, p_for_a, sup, dep_a, ceo)
    make_access(db_session, p_for_b, sup, dep_b, ceo)
    make_access(db_session, manager_for_a, None, dep_a, ceo)
    db_session.commit()

    db_session.add_all(
        [
            EvaluationRecord(
                evaluation_code="EVL-B1",
                subject_personnel_id=p_for_a.id,
                unit_supervisor_user_id=sup.id,
                deputy_user_id=dep_a.id,
                ceo_user_id=ceo.id,
                status=EvaluationStatus.hr_approved,
            ),
            EvaluationRecord(
                evaluation_code="EVL-B2",
                subject_personnel_id=p_for_b.id,
                unit_supervisor_user_id=sup.id,
                deputy_user_id=dep_b.id,
                ceo_user_id=ceo.id,
                status=EvaluationStatus.hr_approved,
            ),
            EvaluationRecord(
                evaluation_code="EVL-B3",
                subject_personnel_id=manager_for_a.id,
                unit_supervisor_user_id=None,
                deputy_user_id=dep_a.id,
                ceo_user_id=ceo.id,
                status=EvaluationStatus.draft,
            ),
        ]
    )
    db_session.commit()

    outcome = tools_base.execute_tool(
        _ctx(db_session, dep_a), tools_base.REGISTRY["my_open_cases"], {}
    )
    codes = [case["evaluation_code"] for case in json.loads(outcome.content)["cases"]]

    assert sorted(codes) == ["EVL-B1", "EVL-B3"], "معاونت الف فقط صندلی خودش"
    assert "EVL-B2" not in codes, "پروندهٔ معاونت ب نشت نکند"


# ── H-1: ابزارهای نوشتنیِ غیرپرخطر وجود ندارند؛ سوییچِ نوشتن در لحظهٔ اجرا ──


def test_every_write_tool_is_risky():
    """هیچ ابزارِ نوشتنی نباید بدونِ تأییدِ انسان اجرا شود — نه امروز، نه فردا."""
    write_tools = [spec for spec in tools_base.REGISTRY.values() if not spec.read_only]
    assert write_tools, "ابزارهای نوشتنی باید ثبت شده باشند"
    not_risky = [spec.name for spec in write_tools if not spec.risky]
    assert not not_risky, f"این ابزارها بدون تأیید اجرا می‌شوند: {not_risky}"


def test_allow_writes_is_enforced_at_execution_time(db_session, synthetic_tool):
    """کاربرِ فقط-خواندنی حتی با صدازدنِ مستقیمِ نامِ ابزارِ نوشتنی (که تبلیغ
    نمی‌شود) نمی‌تواند بنویسد — سنجش در execute_tool، مستقل از تبلیغ."""

    def _silent_write(ctx):
        _write_partial_row(ctx.db)
        return tools_base.ToolOutcome(content="{}", summary="نوشته شد")

    synthetic_tool("af_nonrisky_write", _silent_write, read_only=False, risky=False)
    spec = tools_base.REGISTRY["af_nonrisky_write"]

    user = make_user(db_session, "hr", username="af_ro")
    db_session.commit()

    with pytest.raises(HTTPException) as err:
        execute_tool(_ctx(db_session, user, allow_writes=False), spec, {})
    assert err.value.status_code == 403
    assert not _personnel_marker_exists(db_session), "هیچ نوشته‌ای ماندگار نشده باشد"

    # و با اجازهٔ نوشتن، همان ابزار اجرا می‌شود
    execute_tool(_ctx(db_session, user, allow_writes=True), spec, {})
    assert _personnel_marker_exists(db_session)


# ── H-2: جداسازیِ وظایف داخلِ سرویس ─────────────────────────────────────────


def test_scheme_creator_cannot_activate_even_through_the_copilot(db_session):
    """سازنده ≠ فعال‌کننده، در خودِ سرویس: مسیرِ دستیار (که activate() را
    مستقیم صدا می‌زند) هم از این قانون عبور نمی‌کند."""
    creator = make_user(db_session, "hr", username="af_creator", capabilities=[Capability.manage_scoring])
    scheme = __import__("app.models.scoring_scheme", fromlist=["ScoringScheme"]).ScoringScheme(
        version=next_version(db_session),
        name="طرحِ آزمایشی",
        status=SchemeStatus.draft,
        general_section_weight=0.6,
        specialized_section_weight=0.4,
        evidence_required_scores=[1, 5],
        evidence_min_words=3,
        evidence_max_words=40,
        bonus_max_points=5.0,
        improvement_plan_max_pct=75.0,
        thresholds=[
            {"upper_exclusive": 60, "label": "عدم تمدید"},
            {"upper_exclusive": 101, "label": "تمدید"},
        ],
        indicator_weights={},
        created_by_user_id=creator.id,
    )
    db_session.add(scheme)
    db_session.commit()

    with pytest.raises(HTTPException) as err:
        activate(db_session, scheme, actor_user_id=creator.id)
    assert err.value.status_code == 403
    db_session.refresh(scheme)
    assert scheme.status is SchemeStatus.draft

    # و فعال‌سازیِ همان ابزار از مسیرِ دستیار، با هویتِ سازنده — همان ۴۰۳
    with pytest.raises(HTTPException) as err:
        tools_base.execute_tool(
            _ctx(db_session, creator, caps={Capability.manage_scoring}),
            tools_base.REGISTRY["activate_scoring_scheme"],
            {"scheme_id": scheme.id},
        )
    assert err.value.status_code == 403

    # کاربر دیگری می‌تواند فعالش کند — قانون «دو نفره» است، نه ممنوعیتِ فعال‌سازی
    other = make_user(db_session, "hr", username="af_other_hr")
    activate(db_session, scheme, actor_user_id=other.id)
    db_session.commit()
    db_session.refresh(scheme)
    assert scheme.status is SchemeStatus.active


# ── H-3: شکستِ کنش تأییدشده، نوشته‌های ناقص را کامیت نمی‌کند ────────────────


def _cleanup_confirm_fixture(make_session, hr_id: int) -> None:
    """پاک‌سازیِ دادهٔ commit‌شدهٔ همین تست — دیتابیسِ تست مشترک است.

    خودِ کاربر حذف نمی‌شود: رخدادهای لاگِ ممیزیِ زنجیره‌دار (append-only)
    به او ارجاع می‌دهند و پاک‌کردنِ آن‌ها اصلاً جایز نیست. نامِ کاربرِ یکتا
    (پسوندِ uuid) مانع برخورد در اجراهای بعدی است.
    """
    from app.models.ai import AiConversation

    cleanup = make_session()
    try:
        for convo in cleanup.scalars(select(AiConversation).where(AiConversation.user_id == hr_id)):
            cleanup.delete(convo)
        for acc in cleanup.scalars(select(AiUserAccess).where(AiUserAccess.user_id == hr_id)):
            cleanup.delete(acc)
        # تنظیماتِ AI که با merge ساخته شد — تست‌های بعدی «تنظیم‌نشده» را
        # فرض می‌کنند و این ردیف باید مثل بقیهٔ داده‌ها برود.
        cfg = cleanup.get(AiSettings, 1)
        if cfg is not None:
            cleanup.delete(cfg)
        cleanup.commit()
    finally:
        cleanup.close()


def test_failed_confirmation_rolls_back_partial_writes(db_session, synthetic_tool):
    """ورودیِ گروهیِ نیمه‌کاره: ردیف‌هایی که قبل از شکست flush شده‌اند نباید
    ماندگار شوند — رابط «شکست» می‌خواند، پس دیتابیس هم شکست باید ببیند.

    rollback باید *قبل از* ثبتِ وضعیتِ شکست بیاید؛ وگرنه flushهای نیمه‌کارهٔ
    اجرای شکست‌خورده با همان commitِ bookkeeping ماندگار می‌شوند."""

    def _boom_http(ctx):
        _write_partial_row(ctx.db)
        raise HTTPException(400, "ردیف ۵۰ خراب است")

    synthetic_tool("af_boom_http", _boom_http, read_only=False, risky=True)
    hr = make_user(db_session, "hr", username="af_cf_http", capabilities=[Capability.manage_personnel])
    config, access = _enable_ai(db_session, hr)
    pending = _make_pending(db_session, hr, "af_boom_http", {})
    db_session.commit()

    with pytest.raises(HTTPException) as err:
        confirmations.confirm(
            db_session,
            user=CurrentUser(
                id=hr.id, username=hr.username, role=hr.role,
                personnel_id=hr.personnel_id, must_change_password=False,
                display_name=hr.username,
            ),
            pending_id=pending.id,
            config=config,
            access=access,
        )
    assert err.value.status_code == 400

    db_session.rollback()
    row = db_session.get(AiPendingAction, pending.id)
    assert row.status == "failed"
    assert not _personnel_marker_exists(db_session), "نوشتهٔ ناقص ماندگار شده است!"


def test_failed_confirmation_with_unexpected_error_also_rolls_back(db_session, synthetic_tool):
    def _boom_raw(ctx):
        _write_partial_row(ctx.db)
        raise RuntimeError("حافظه تمام شد")

    synthetic_tool("af_boom_raw", _boom_raw, read_only=False, risky=True)
    hr = make_user(db_session, "hr", username="af_cf_raw", capabilities=[Capability.manage_personnel])
    config, access = _enable_ai(db_session, hr)
    pending = _make_pending(db_session, hr, "af_boom_raw", {})
    db_session.commit()

    with pytest.raises(HTTPException) as err:
        confirmations.confirm(
            db_session,
            user=CurrentUser(
                id=hr.id, username=hr.username, role=hr.role,
                personnel_id=hr.personnel_id, must_change_password=False,
                display_name=hr.username,
            ),
            pending_id=pending.id,
            config=config,
            access=access,
        )
    assert err.value.status_code == 500

    db_session.rollback()
    row = db_session.get(AiPendingAction, pending.id)
    assert row.status == "failed"
    assert not _personnel_marker_exists(db_session)


def test_failed_tool_call_in_the_chat_loop_leaves_no_partial_writes(db_session, synthetic_tool):
    """شکستِ ابزار در حلقهٔ گفت‌وگو: rollback پیش از ثبتِ لاگِ شکست — لاگِ
    ممیزی می‌ماند، نوشتهٔ ناقص نمی‌ماند."""

    def _loop_boom(ctx):
        _write_partial_row(ctx.db)
        raise RuntimeError("کرم در ابزار")

    synthetic_tool("af_loop_boom", _loop_boom, read_only=False, risky=False)
    spec = tools_base.REGISTRY["af_loop_boom"]

    user = make_user(db_session, "hr", username="af_loop", capabilities=[])
    db_session.commit()

    with pytest.raises(HTTPException) as err:
        execute_tool(_ctx(db_session, user), spec, {})
    assert err.value.status_code == 500

    assert not _personnel_marker_exists(db_session), "نوشتهٔ ناقصِ ابزار ماندگار شده"
    from app.models.audit_log import AuditLog

    event = db_session.scalars(
        select(AuditLog).where(
            AuditLog.event_type == "ai_tool_failed",
            AuditLog.new_value["tool"].astext == "af_loop_boom",
        )
    ).first()
    assert event is not None, "شکست ابزار باید در لاگ ممیزی بماند"


# ── M-1: بازکردنِ پرونده روی صندلیِ غیرفعال ممنوع ────────────────────────────


def test_single_create_refuses_an_inactive_seat_holder(client, db_session):
    sup = make_user(db_session, "unit_supervisor", username="af_m1_sup")
    dep = make_user(db_session, "deputy", username="af_m1_dep")
    ceo = make_user(db_session, "ceo", username="af_m1_ceo")
    person = make_personnel(db_session, full_name="کارمندِ صندلیِ مرده")
    make_access(db_session, person, sup, dep, ceo)
    db_session.commit()

    # حسابِ مسئول واحد بعداً غیرفعال می‌شود — وضعیتِ نوشتنِ دسترسی را نمی‌بیند
    sup.is_active = False
    db_session.commit()

    response = client.post(
        "/api/evaluations", json={"subject_personnel_id": person.id}, headers=auth_header(dep)
    )

    assert response.status_code == 400, response.text
    assert "مسئول واحد" in response.json()["detail"]
    assert (
        db_session.query(EvaluationRecord).filter_by(subject_personnel_id=person.id).count() == 0
    )


def test_bulk_preview_reports_an_inactive_seat_as_blocked(client, db_session):
    """در بازکردنِ دسته‌ای هم، صندلیِ مرده «بلاک با دلیل» است نه پروندهٔ گیرکرده."""
    hr = make_user(db_session, "hr", username="af_m1_hr", capabilities=[])
    sup = make_user(db_session, "unit_supervisor", username="af_m1_sup2")
    dep = make_user(db_session, "deputy", username="af_m1_dep2")
    ceo = make_user(db_session, "ceo", username="af_m1_ceo2")
    person = make_personnel(db_session, full_name="آمادهٔ ارزیابیِ صندلی‌مرده", org_unit="واحد صندلی")
    make_access(db_session, person, sup, dep, ceo)
    db_session.commit()

    sup.is_active = False
    db_session.commit()

    body = client.post(
        "/api/periods/bulk-create/preview",
        json={"org_unit": "واحد صندلی"},
        headers=auth_header(hr),
    ).json()
    rows = {row["full_name"]: row for row in body["results"]}

    assert rows["آمادهٔ ارزیابیِ صندلی‌مرده"]["outcome"] == "blocked_inactive_seat"
    assert rows["آمادهٔ ارزیابیِ صندلی‌مرده"]["reason"], "دلیل باید فارسی و نمایش‌پذیر باشد"

    run = client.post(
        "/api/periods/bulk-create",
        json={"org_unit": "واحد صندلی"},
        headers=auth_header(hr),
    ).json()
    assert run["counts"].get("created", 0) == 0
    assert run["counts"].get("blocked_inactive_seat") == 1


# ── M-7: claimingِ اتمیِ تأیید ───────────────────────────────────────────────


def test_a_second_confirm_during_execution_is_refused_and_runs_once(monkeypatch):
    """مسابقهٔ واقعی دو اتصال: تأییدِ دوم وقتی اولی *وسطِ اجراست* باید ۴۰۹
    بگیرد و کنش دقیقاً یک‌بار اجرا شود. UPDATEِ شرط‌دار پیش از اجرا مالکیت را
    می‌گیرد؛ قفلِ ردیفیِ ساده به‌تنهایی کافی نبود چون ابزارها وسطِ کار commit
    می‌کنند و قفل آزاد می‌شود.

    log_event خنثی می‌شود چون این تست روی اتصالِ واقعی commit می‌کند و
    رخدادِ ممیزیِ ماندگار، فرضِ «خالی‌بودنِ لاگ» تست‌های دیگر را در اجرای بعدی
    سوئیت می‌شکند (لاگ ممیزی append-only است و نباید پاک شود).
    """
    monkeypatch.setattr("app.services.ai.confirmations.log_event", lambda *a, **k: None)
    engine = create_engine(settings.database_url)
    marker_code = "P-AUDIT-ONCE"

    def _slow_write(ctx):
        ctx.db.add(
            Personnel(
                personnel_code=marker_code,
                full_name="فقط یک‌بار",
                job_title="کارشناس",
                org_unit="واحد تست",
                contract_start_date=date(2025, 1, 1),
                contract_end_date=date(2026, 12, 31),
            )
        )
        ctx.db.flush()
        # پنجرهٔ مسابقه: تأییدِ دوم باید در همین فاصله رد شود
        threading.Event().wait(0.6)
        return tools_base.ToolOutcome(content="{}", summary="یک‌بار نوشته شد")

    try:
        tools_base.tool(
            name="af_slow_write",
            description="t",
            category="تست",
            read_only=False,
            risky=True,
            parameters={"type": "object", "properties": {}},
        )(_slow_write)

        make_session = sessionmaker(bind=engine)
        setup = make_session()
        hr = make_user(
            setup, "hr",
            username=f"af_race_{uuid.uuid4().hex[:8]}",
            capabilities=[Capability.manage_personnel],
        )
        setup.flush()
        config, access = _enable_ai(setup, hr)
        pending = _make_pending(setup, hr, "af_slow_write", {})
        setup.commit()

        user = CurrentUser(
            id=hr.id, username=hr.username, role=hr.role,
            personnel_id=hr.personnel_id, must_change_password=False,
            display_name=hr.username,
        )

        result: dict = {"first": None, "second": None}

        def _first():
            s = make_session()
            try:
                row, _ = confirmations.confirm(s, user=user, pending_id=pending.id, config=config, access=access)
                result["first"] = row.status
            except Exception as exc:  # noqa: BLE001
                result["first"] = exc
            finally:
                s.close()

        thread = threading.Thread(target=_first)
        thread.start()
        threading.Event().wait(0.25)  # اولی الان وسطِ اجراست (claim شده)

        second = make_session()
        try:
            with pytest.raises(HTTPException) as err:
                confirmations.confirm(second, user=user, pending_id=pending.id, config=config, access=access)
            result["second"] = err.value.status_code
        except AssertionError:
            raise
        finally:
            thread.join(5)
            second.close()

        assert result["second"] == 409, f"تأیید دوم باید ۴۰۹ بگیرد، نه {result['second']!r}"
        assert result["first"] == "confirmed"
        checker = make_session()
        try:
            written = checker.scalars(
                select(Personnel).where(Personnel.personnel_code == marker_code)
            ).all()
            assert len(written) == 1, "اجرای دوباره یعنی claiming اتمی نیست"
        finally:
            checker.close()

        # پاک‌سازیِ داده‌ای که عمداً commit شده (پرسنلِ نشان‌دار + دادهٔ AI)
        cleanup = make_session()
        try:
            person = cleanup.scalars(
                select(Personnel).where(Personnel.personnel_code == marker_code)
            ).first()
            if person is not None:
                cleanup.delete(person)
            cleanup.commit()
        finally:
            cleanup.close()
        _cleanup_confirm_fixture(make_session, hr.id)
    finally:
        tools_base.REGISTRY.pop("af_slow_write", None)
        engine.dispose()


# ── M-8: پاک‌سازیِ بازگشتیِ آرگومان‌ها در لاگ ممیزی ─────────────────────────


def test_audit_argument_sanitization_is_recursive():
    args = {
        "upload_id": 7,
        "edits": [
            {
                "row_number": 2,
                "fields": {"رمز اولیه": "S3cret-پسورد", "پایان قرارداد": "1406/05/01"},
            }
        ],
        "credentials": {"password": "topsecret", "nested": [{"api_key": "k-123"}]},
        "temporary_password": "tmp-9",
    }
    sanitized = tools_base.sanitize_arguments(args)

    flat = json.dumps(sanitized, ensure_ascii=False)
    assert "S3cret-پسورد" not in flat
    assert "topsecret" not in flat
    assert "k-123" not in flat
    assert "tmp-9" not in flat
    assert sanitized["edits"][0]["fields"]["رمز اولیه"] == "***"
    assert sanitized["edits"][0]["fields"]["پایان قرارداد"] == "1406/05/01"
    assert sanitized["credentials"]["password"] == "***"
    assert sanitized["credentials"]["nested"][0]["api_key"] == "***"
    assert sanitized["temporary_password"] == "***"


# ── M-10: قفلِ رهبری با کامیتِ میانه نشت نمی‌کند ────────────────────────────


def test_the_leader_lock_does_not_leak_across_mid_run_commits(db_session):
    """کامیتِ میانهٔ جاروها اتصالِ قفل‌دار را به استخر برمی‌گرداند؛ قفل باید
    روی اتصالِ اختصاصی باشد تا بعد از پایانِ اجرا آزاد شده باشد."""
    engine = create_engine(settings.database_url)
    make_session = sessionmaker(bind=engine)
    worker = make_session()
    holder = make_session()
    checker = make_session()

    def _runner(session):
        session.commit()  # اتصالِ قفل‌دار به استخر برمی‌گردد — ریشهٔ نشت
        holder.execute(text("SELECT 1"))  # اتصالِ دیگری از استخر بیرون می‌آید
        return {"noop": 0}

    try:
        from app.models.scheduler_run import SchedulerRun
        from app.services.scheduler_lock import _acquire_leader_lock, _release_leader_lock, run_sweeps_once

        before = set(
            db_session.scalars(select(SchedulerRun.id))
        )
        run = run_sweeps_once(worker, _runner, trigger="scheduler")
        assert run.status == "succeeded"

        holder.rollback()  # اتصالِ گرفته‌شده به استخر برمی‌گردد
        assert _acquire_leader_lock(checker) is True, (
            "قفل نباید روی اتصالیِ در استخر نشت کرده باشد"
        )
        _release_leader_lock(checker)

        # ردیفِ تاریخچه‌ای که این تست commit کرده پاک می‌شود — تست‌های
        # «آخرین جاروی موفق» به خالی‌بودنِ تاریخچه وابسته‌اند.
        janitor = make_session()
        try:
            janitor.query(SchedulerRun).filter(
                SchedulerRun.id.notin_(before)
            ).delete(synchronize_session=False)
            janitor.commit()
        finally:
            janitor.close()
    finally:
        holder.close()
        worker.close()
        checker.close()
        engine.dispose()
