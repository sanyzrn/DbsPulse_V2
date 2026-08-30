"""رگرسیونِ یافته‌های ممیزی که مستقل از قابلیت حذف‌شدهٔ AI هستند."""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.enums import Capability, EvaluationStatus, SchemeStatus
from app.models.evaluation import EvaluationRecord
from app.services.scoring_scheme import activate, next_version
from tests.helpers import auth_header, make_access, make_personnel, make_user


def test_finalizing_a_case_without_results_is_refused(client, db_session):
    """پروندهٔ بدون نتیجهٔ محاسبه‌شده هرگز نهایی نمی‌شود."""
    from app.models.evaluation import EvaluationScore

    sup = make_user(db_session, "unit_supervisor", username="af_sup")
    dep = make_user(db_session, "deputy", username="af_dep")
    ceo = make_user(db_session, "ceo", username="af_ceo")
    person = make_personnel(db_session, full_name="کارمندِ گاردِ نتیجه")
    make_access(db_session, person, sup, dep, ceo)
    db_session.commit()

    evaluation = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": person.id},
        headers=auth_header(sup),
    ).json()
    record = db_session.get(EvaluationRecord, evaluation["id"])
    record.status = EvaluationStatus.deputy_approved
    db_session.query(EvaluationScore).filter(
        EvaluationScore.evaluation_record_id == record.id
    ).delete()
    record.final_weighted_pct = None
    db_session.commit()

    response = client.post(
        f"/api/evaluations/{record.id}/ceo-finalize",
        headers=auth_header(ceo),
    )

    assert response.status_code == 400, response.text
    db_session.refresh(record)
    assert record.status is EvaluationStatus.deputy_approved


def test_scheme_creator_cannot_activate_their_own_scheme(db_session):
    """قانون سازنده ≠ فعال‌کننده در خود سرویس اعمال می‌شود."""
    creator = make_user(
        db_session,
        "hr",
        username="af_creator",
        capabilities=[Capability.manage_scoring],
    )
    scheme = __import__(
        "app.models.scoring_scheme",
        fromlist=["ScoringScheme"],
    ).ScoringScheme(
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

    other = make_user(db_session, "hr", username="af_other_hr")
    activate(db_session, scheme, actor_user_id=other.id)
    db_session.commit()
    db_session.refresh(scheme)
    assert scheme.status is SchemeStatus.active


def test_single_create_refuses_an_inactive_seat_holder(client, db_session):
    sup = make_user(db_session, "unit_supervisor", username="af_m1_sup")
    dep = make_user(db_session, "deputy", username="af_m1_dep")
    ceo = make_user(db_session, "ceo", username="af_m1_ceo")
    person = make_personnel(db_session, full_name="کارمندِ صندلیِ مرده")
    make_access(db_session, person, sup, dep, ceo)
    db_session.commit()

    sup.is_active = False
    db_session.commit()

    response = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": person.id},
        headers=auth_header(dep),
    )

    assert response.status_code == 400, response.text
    assert "مسئول واحد" in response.json()["detail"]
    assert (
        db_session.query(EvaluationRecord)
        .filter_by(subject_personnel_id=person.id)
        .count()
        == 0
    )


def test_bulk_preview_reports_an_inactive_seat_as_blocked(client, db_session):
    hr = make_user(db_session, "hr", username="af_m1_hr", capabilities=[])
    sup = make_user(db_session, "unit_supervisor", username="af_m1_sup2")
    dep = make_user(db_session, "deputy", username="af_m1_dep2")
    ceo = make_user(db_session, "ceo", username="af_m1_ceo2")
    person = make_personnel(
        db_session,
        full_name="آمادهٔ ارزیابیِ صندلی‌مرده",
        org_unit="واحد صندلی",
    )
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
    assert rows["آمادهٔ ارزیابیِ صندلی‌مرده"]["reason"]

    run = client.post(
        "/api/periods/bulk-create",
        json={"org_unit": "واحد صندلی"},
        headers=auth_header(hr),
    ).json()
    assert run["counts"].get("created", 0) == 0
    assert run["counts"].get("blocked_inactive_seat") == 1


def test_the_leader_lock_does_not_leak_across_mid_run_commits(db_session):
    engine = create_engine(settings.database_url)
    make_session = sessionmaker(bind=engine)
    worker = make_session()
    holder = make_session()
    checker = make_session()

    def _runner(session):
        session.commit()
        holder.execute(text("SELECT 1"))
        return {"noop": 0}

    try:
        from app.models.scheduler_run import SchedulerRun
        from app.services.scheduler_lock import (
            _acquire_leader_lock,
            _release_leader_lock,
            run_sweeps_once,
        )

        before = set(db_session.scalars(select(SchedulerRun.id)))
        run = run_sweeps_once(worker, _runner, trigger="scheduler")
        assert run.status == "succeeded"

        holder.rollback()
        assert _acquire_leader_lock(checker) is True
        _release_leader_lock(checker)

        janitor = make_session()
        try:
            janitor.query(SchedulerRun).filter(
                SchedulerRun.id.notin_(before)
            ).delete(synchronize_session=False)
            janitor.commit()
        finally:
            janitor.close()
    finally:
        worker.close()
        holder.close()
        checker.close()
        engine.dispose()
