"""P0-08 + P1-02 — زمان‌بندی که واقعاً اجرا می‌شود و SLA که مرحله را می‌سنجد.

دو مشکل جدا که یک ریشه دارند («یادآوری‌ها به‌درد نمی‌خورند»):

* زمان‌بند درون‌پروسه بود و با چند replica هر instance جداگانه جارو می‌زد — اعلان
  تکراری. و هیچ تاریخچه‌ای نداشت، پس «اجرا شد و چیزی نبود» از «اصلاً اجرا نشد»
  قابل تشخیص نبود.
* جاروی SLA از created_at استفاده می‌کرد، یعنی «سن کل پرونده» نه «چقدر در این مرحله
  مانده». پرونده‌ای که سه هفته در مراحل قبلی چرخیده بود، لحظهٔ رسیدن به مرحلهٔ بعد
  فوراً تأخیردار اعلام می‌شد.
"""
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.evaluation import EvaluationRecord
from app.models.scheduler_run import SchedulerRun
from app.services.scheduled import run_all_sweeps, run_sla_sweep
from app.services.scheduler_lock import recent_runs, run_sweeps_once
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


def _submitted_case(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    evaluation = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    ).json()
    client.put(
        f"/api/evaluations/{evaluation['id']}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(sup),
    )
    client.post(f"/api/evaluations/{evaluation['id']}/submit", headers=auth_header(sup))
    return {"id": evaluation["id"], "hr": hr, "sup": sup, "dep": dep, "ceo": ceo}


# ------------------------------------------------- P1-02: ساعتِ مرحله


def test_moving_to_a_new_stage_resets_the_stage_clock(client, db_session):
    case = _submitted_case(client, db_session)
    record = db_session.get(EvaluationRecord, case["id"])
    before = record.stage_entered_at

    client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(case["hr"]))
    db_session.refresh(record)

    assert record.stage_entered_at > before


def test_returning_a_case_also_resets_the_stage_clock(client, db_session):
    """برگشت هم یک گذار است: مسئولی که پرونده تازه به او برگشته نباید فوراً نهیب بخورد."""
    case = _submitted_case(client, db_session)
    record = db_session.get(EvaluationRecord, case["id"])
    record.stage_entered_at = datetime.now(UTC) - timedelta(days=365)
    db_session.commit()

    client.post(
        f"/api/evaluations/{case['id']}/return",
        json={"reason": "شواهد ناکافی"},
        headers=auth_header(case["hr"]),
    )
    db_session.refresh(record)

    assert record.stage_entered_at > datetime.now(UTC) - timedelta(minutes=1)


def test_an_old_case_that_just_changed_stage_is_not_reported_as_stalled(client, db_session):
    """قلب P1-02: پروندهٔ کهنه‌ای که تازه وارد این مرحله شده، تأخیر ندارد."""
    case = _submitted_case(client, db_session)
    record = db_session.get(EvaluationRecord, case["id"])
    # پرونده قدیمی است ...
    record.created_at = datetime.now(UTC) - timedelta(days=settings.sla_reminder_days + 30)
    db_session.commit()
    # ... ولی همین حالا وارد مرحلهٔ معاونت شد
    client.post(f"/api/evaluations/{case['id']}/hr-approve", headers=auth_header(case["hr"]))

    assert run_sla_sweep(db_session) == 0, "معیار باید زمانِ در مرحله باشد، نه سن پرونده"


def test_a_case_stuck_in_one_stage_is_reported(client, db_session):
    case = _submitted_case(client, db_session)
    record = db_session.get(EvaluationRecord, case["id"])
    record.stage_entered_at = datetime.now(UTC) - timedelta(days=settings.sla_reminder_days + 1)
    db_session.commit()

    assert run_sla_sweep(db_session) >= 1

    notifications = client.get("/api/notifications", headers=auth_header(case["hr"])).json()
    rows = notifications["items"] if isinstance(notifications, dict) else notifications
    assert any("در همین مرحله" in row["message"] for row in rows)


# ------------------------------------------- P0-08: رهبری و تاریخچه


def test_a_run_is_recorded_with_its_summary(client, db_session):
    run = run_sweeps_once(db_session, run_all_sweeps, trigger="manual")

    assert run.status == "succeeded"
    assert run.trigger == "manual"
    assert run.finished_at is not None
    assert isinstance(run.summary, dict)


def test_the_history_endpoint_shows_recent_runs(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()
    run_sweeps_once(db_session, run_all_sweeps, trigger="scheduler")

    r = client.get("/api/admin/scheduler-runs", headers=auth_header(hr))

    assert r.status_code == 200
    assert r.json(), "تاریخچه نباید خالی باشد — بدون آن، «اجرا نشد» از «چیزی نبود» جدا نیست"
    assert r.json()[0]["status"] in {"succeeded", "skipped_locked"}


def test_a_second_instance_skips_instead_of_duplicating_work(db_session):
    """اثبات رهبری روی دو اتصال واقعی: instance دوم کار را دوباره انجام نمی‌دهد."""
    engine = create_engine(settings.database_url)
    make_session = sessionmaker(bind=engine)

    calls: list[str] = []

    def _runner(session):
        calls.append("ran")
        return {"noop": 0}

    leader = make_session()
    follower = make_session()
    try:
        # رهبر قفل را می‌گیرد و نگه می‌دارد
        from app.services.scheduler_lock import _acquire_leader_lock, _release_leader_lock

        assert _acquire_leader_lock(leader) is True

        run = run_sweeps_once(follower, _runner, trigger="scheduler")

        assert run.status == "skipped_locked"
        assert calls == [], "instance غیر-رهبر نباید جاروها را اجرا کند"

        _release_leader_lock(leader)
        leader.commit()
    finally:
        leader.close()
        follower.close()
        engine.dispose()


def test_the_manual_endpoint_refuses_to_race_the_scheduler(client, db_session):
    hr = make_user(db_session, "hr")
    db_session.commit()

    engine = create_engine(settings.database_url)
    holder = sessionmaker(bind=engine)()
    try:
        from app.services.scheduler_lock import _acquire_leader_lock, _release_leader_lock

        assert _acquire_leader_lock(holder) is True

        r = client.post("/api/admin/run-scheduled-jobs", headers=auth_header(hr))

        assert r.status_code == 409
        assert "در حال اجرا" in r.json()["detail"]

        _release_leader_lock(holder)
        holder.commit()
    finally:
        holder.close()
        engine.dispose()


def test_a_failing_sweep_is_recorded_not_swallowed(db_session):
    def _boom(session):
        raise RuntimeError("sweep exploded")

    try:
        run_sweeps_once(db_session, _boom, trigger="scheduler")
    except RuntimeError:
        pass
    else:
        raise AssertionError("خطا باید بالا برود تا حلقهٔ زمان‌بند لاگش کند")

    failures = [r for r in recent_runs(db_session) if r.status == "failed"]
    assert failures, "شکست باید در تاریخچه بماند، وگرنه بی‌صدا گم می‌شود"
    assert "sweep exploded" in failures[0].error


def test_the_lock_is_released_so_the_next_run_can_proceed(db_session):
    first = run_sweeps_once(db_session, run_all_sweeps, trigger="scheduler")
    second = run_sweeps_once(db_session, run_all_sweeps, trigger="scheduler")

    assert first.status == "succeeded"
    assert second.status == "succeeded", "قفل باید بعد از هر اجرا آزاد شود"


def test_scheduler_runs_survive_as_history(db_session):
    before = len(recent_runs(db_session, limit=100))
    run_sweeps_once(db_session, run_all_sweeps, trigger="manual")

    assert len(recent_runs(db_session, limit=100)) == before + 1
    assert isinstance(recent_runs(db_session)[0], SchedulerRun)
