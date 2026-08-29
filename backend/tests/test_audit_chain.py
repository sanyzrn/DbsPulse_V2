"""P1-09 — لاگ حسابرسی باید مدرک باشد، نه مستندات.

پیش از این، لاگ فقط «به‌عرف» append-only بود: هیچ‌چیز جلوی UPDATE/DELETE را
نمی‌گرفت و هیچ زنجیره‌ای ردیف‌ها را به هم گره نمی‌زد. یعنی این لاگ فقط برای کسی که
*از قبل* به دارندهٔ دسترسی دیتابیس اعتماد دارد چیزی را ثابت می‌کرد — و طبق P0-03
همان نقشی که لاگ قرار است پاسخ‌گو نگهش دارد، آن دسترسی را دارد.
"""
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import InternalError, ProgrammingError

from app.models.audit_log import AuditLog
from app.models.enums import Capability
from app.services.audit import GENESIS_HASH, log_event, verify_chain
from tests.helpers import auth_header, make_user


def _log_some(db_session, actor, count: int = 3):
    for i in range(count):
        log_event(
            db_session,
            actor_user_id=actor.id,
            event_type="test_event",
            new_value={"n": i},
        )
    db_session.flush()


# ───────────────────────────────────────────── زنجیره


def test_each_entry_links_to_the_previous_one(db_session):
    actor = make_user(db_session, "hr")
    db_session.flush()
    _log_some(db_session, actor, 3)

    rows = list(db_session.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(3)))
    rows.reverse()

    assert all(r.entry_hash and r.prev_hash for r in rows)
    assert rows[1].prev_hash == rows[0].entry_hash
    assert rows[2].prev_hash == rows[1].entry_hash


def test_a_clean_chain_verifies(db_session):
    actor = make_user(db_session, "hr")
    db_session.flush()
    _log_some(db_session, actor, 5)

    result = verify_chain(db_session)

    assert result["ok"] is True
    assert result["broken_at_id"] is None
    assert result["checked"] > 0


def test_the_first_entry_of_an_empty_log_anchors_to_genesis(db_session):
    """ردیف اول قبلی ندارد، پس به یک مقدار ثابت گره می‌خورد — وگرنه زنجیره سرِ آزاد دارد."""
    actor = make_user(db_session, "hr")
    db_session.flush()
    assert db_session.scalar(select(AuditLog).limit(1)) is None, "تراکنش تست باید خالی شروع شود"

    _log_some(db_session, actor, 1)

    first = db_session.scalar(select(AuditLog).order_by(AuditLog.id).limit(1))
    assert first.prev_hash == GENESIS_HASH


# ───────────────────────────────────── تشخیص دست‌کاری


def test_editing_a_row_is_detected(db_session):
    """قلب این یافته: ویرایش بی‌صدا باید قابل کشف باشد."""
    actor = make_user(db_session, "hr")
    db_session.flush()
    _log_some(db_session, actor, 3)
    target = db_session.scalar(select(AuditLog).order_by(AuditLog.id.desc()).limit(1))

    # تریگر جلوی UPDATE از مسیر معمول را می‌گیرد، پس برای شبیه‌سازی یک مهاجم که
    # مستقیم به دیتابیس دسترسی دارد، موقتاً غیرفعالش می‌کنیم.
    db_session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_log_append_only"))
    db_session.execute(
        text("UPDATE audit_log SET new_value = '{\"n\": 999}'::jsonb WHERE id = :i"),
        {"i": target.id},
    )
    db_session.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_log_append_only"))
    db_session.expire_all()

    result = verify_chain(db_session)

    assert result["ok"] is False
    assert result["broken_at_id"] == target.id
    assert "ویرایش" in result["reason"]


def test_deleting_a_row_is_detected(db_session):
    actor = make_user(db_session, "hr")
    db_session.flush()
    _log_some(db_session, actor, 4)
    rows = list(db_session.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(3)))
    middle = rows[1]
    survivor = rows[0]

    db_session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_log_append_only"))
    db_session.execute(text("DELETE FROM audit_log WHERE id = :i"), {"i": middle.id})
    db_session.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_log_append_only"))
    db_session.expire_all()

    result = verify_chain(db_session)

    assert result["ok"] is False
    # ردیف بعدی حالا حلقه‌اش را گم کرده است
    assert result["broken_at_id"] == survivor.id
    assert "حذف" in result["reason"]


# ─────────────────────────────────── گاردِ دیتابیس


def test_the_database_refuses_to_update_an_audit_row(db_session):
    actor = make_user(db_session, "hr")
    db_session.flush()
    _log_some(db_session, actor, 1)
    target = db_session.scalar(select(AuditLog).order_by(AuditLog.id.desc()).limit(1))

    with pytest.raises((InternalError, ProgrammingError), match="append-only"):
        db_session.execute(
            text("UPDATE audit_log SET event_type = 'rewritten' WHERE id = :i"), {"i": target.id}
        )


def test_the_database_refuses_to_delete_an_audit_row(db_session):
    actor = make_user(db_session, "hr")
    db_session.flush()
    _log_some(db_session, actor, 1)
    target = db_session.scalar(select(AuditLog).order_by(AuditLog.id.desc()).limit(1))

    with pytest.raises((InternalError, ProgrammingError), match="append-only"):
        db_session.execute(text("DELETE FROM audit_log WHERE id = :i"), {"i": target.id})


# ──────────────────────────────────── endpoint HR


def test_hr_can_check_integrity(client, db_session):
    hr = make_user(db_session, "hr", capabilities=[Capability.view_audit_log])
    db_session.commit()
    # یک مسیر واقعیِ برنامه که لاگ می‌نویسد، تا چیزی برای راستی‌آزمایی وجود داشته باشد
    client.get("/api/personnel/export.xlsx", headers=auth_header(hr))

    r = client.get("/api/audit-log/integrity", headers=auth_header(hr))

    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["checked"] > 0


def test_non_hr_cannot_check_integrity(client, db_session):
    supervisor = make_user(db_session, "unit_supervisor")
    db_session.commit()

    assert client.get("/api/audit-log/integrity", headers=auth_header(supervisor)).status_code == 403


# ────────────────────────────── پوشش رویدادهای جاافتاده


def test_improvement_goal_changes_are_logged(client, db_session):
    """محتوای یک برنامهٔ اصلاحیِ گره‌خورده به تصمیم قرارداد، تا امروز بی‌رد عوض می‌شد."""
    from tests.helpers import active_indicators, full_valid_scores, make_access, make_personnel

    hr = make_user(db_session, "hr", capabilities=[Capability.view_audit_log])
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    ev = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    ).json()
    client.put(
        f"/api/evaluations/{ev['id']}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(sup),
    )
    client.post(f"/api/evaluations/{ev['id']}/submit", headers=auth_header(sup))
    client.post(f"/api/evaluations/{ev['id']}/hr-approve", headers=auth_header(hr))
    client.post(f"/api/evaluations/{ev['id']}/deputy-approve", headers=auth_header(dep))
    client.post(f"/api/evaluations/{ev['id']}/ceo-finalize", headers=auth_header(ceo))

    plan = client.post(
        "/api/improvement-plans",
        json={"evaluation_record_id": ev["id"], "title": "برنامهٔ بهبود تست", "review_date": "2026-12-01"},
        headers=auth_header(hr),
    ).json()
    goal = client.post(
        f"/api/improvement-plans/{plan['id']}/goals",
        json={"description": "هدف اول"},
        headers=auth_header(hr),
    ).json()
    client.patch(
        f"/api/improvement-plans/{plan['id']}/goals/{goal['id']}",
        json={"description": "هدف بازنویسی‌شده"},
        headers=auth_header(hr),
    )
    client.delete(
        f"/api/improvement-plans/{plan['id']}/goals/{goal['id']}", headers=auth_header(hr)
    )

    logged = {
        row["event_type"]
        for row in client.get(
            "/api/audit-log", params={"limit": 100}, headers=auth_header(hr)
        ).json()["items"]
    }
    assert {"improvement_goal_added", "improvement_goal_updated", "improvement_goal_deleted"} <= logged


def test_the_report_export_is_logged_with_what_was_extracted(client, db_session):
    """تنها مسیر خروج داده که هیچ ردی نمی‌گذاشت."""
    hr = make_user(db_session, "hr", capabilities=[Capability.view_audit_log])
    db_session.commit()

    assert client.get(
        "/api/dashboard/report/export.xlsx",
        params={"org_unit": "واحد تست"},
        headers=auth_header(hr),
    ).status_code == 200

    rows = client.get(
        "/api/audit-log",
        params={"event_type": "report_excel_exported"},
        headers=auth_header(hr),
    ).json()["items"]
    assert rows
    assert "org_unit" in rows[0]["new_value"]["filters"]
    assert "row_count" in rows[0]["new_value"]


def test_logging_keeps_the_chain_intact(client, db_session):
    """کل مسیرهای واقعی برنامه هم باید زنجیره را سالم نگه دارند، نه فقط log_event مستقیم."""
    hr = make_user(db_session, "hr")
    db_session.commit()
    client.get("/api/personnel/export.xlsx", headers=auth_header(hr))
    client.get("/api/users/export.xlsx", headers=auth_header(hr))

    assert verify_chain(db_session)["ok"] is True
