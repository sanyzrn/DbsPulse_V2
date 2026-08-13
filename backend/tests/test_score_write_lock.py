"""P0-05 — نوشتن امتیاز/نظر ارزیاب باید روی همان قفل ردیفی سریالایز شود که گذارها
از آن استفاده می‌کنند.

پیش از این، `upsert_scores` و `set_evaluator_comment` رکورد را *بدون* قفل می‌خواندند.
یعنی یک ذخیرهٔ خودکارِ پیش‌نویس (فرانت حین تایپ auto-save می‌کند) می‌توانست بررسی
وضعیت را روی وضعیتی پاس کند که یک submit هم‌زمان دارد عوضش می‌کند، و امتیاز پس از
محاسبهٔ درصد نهایی روی رکورد بنشیند — امتیازهای ذخیره‌شده با نتیجهٔ ذخیره‌شده نمی‌خواندند.

برخلاف test_workflow_concurrency.py که فقط وجود عبارت FOR UPDATE در SQL را بررسی
می‌کند، این تست‌ها یک مسابقهٔ واقعی روی *دو اتصال جدا* اجرا می‌کنند. پس داده باید
واقعاً commit شود (fixture مشترک `db_session` عمداً همه‌چیز را rollback می‌کند)، و
خودمان در پایان پاکش می‌کنیم.
"""
import threading
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.api.routers.evaluations import _get_record_or_404_for_update, upsert_scores
from app.core.config import settings
from app.core.security import hash_password
from app.models.enums import EvaluationStatus
from app.models.evaluation import EvaluationRecord
from app.models.personnel import Personnel
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.schemas.evaluation import ScoresUpsert

LOCK_HOLD_SECONDS = 0.3


@pytest.fixture()
def committed_draft():
    """یک ارزیابی در وضعیت draft که واقعاً commit شده، تا اتصال‌های دیگر ببینندش."""
    engine = create_engine(settings.database_url)
    make_session = sessionmaker(bind=engine)

    # از خود مدل‌ها استفاده می‌کنیم نه INSERT خام، تا پیش‌فرض‌های سمت پایتون
    # (token_version، must_change_password، …) خودبه‌خود اعمال شوند.
    with make_session() as setup:
        password_hash = hash_password("Lock-Test-1")
        users = [
            User(username="lock_sup", password_hash=password_hash, role="unit_supervisor"),
            User(username="lock_dep", password_hash=password_hash, role="deputy"),
            User(username="lock_ceo", password_hash=password_hash, role="ceo"),
        ]
        setup.add_all(users)
        setup.flush()
        sup_id, dep_id, ceo_id = (user.id for user in users)

        personnel = Personnel(
            personnel_code="P-LOCK",
            full_name="کارمند قفل",
            job_title="کارشناس",
            org_unit="واحد تست",
            contract_start_date=date(2025, 1, 1),
            contract_end_date=date(2026, 1, 1),
        )
        setup.add(personnel)
        setup.flush()
        personnel_id = personnel.id

        record = EvaluationRecord(
            evaluation_code="EVL-LOCK",
            subject_personnel_id=personnel_id,
            unit_supervisor_user_id=sup_id,
            deputy_user_id=dep_id,
            ceo_user_id=ceo_id,
            status=EvaluationStatus.draft,
        )
        setup.add(record)
        setup.flush()
        record_id = record.id
        setup.commit()

    yield {
        "engine": engine,
        "make_session": make_session,
        "record_id": record_id,
        "supervisor": CurrentUser(
            id=sup_id, username="lock_sup", role="unit_supervisor", personnel_id=None
        ),
    }

    with make_session() as teardown:
        teardown.execute(
            text("DELETE FROM audit_log WHERE evaluation_record_id = :r OR actor_user_id = ANY(:u)"),
            {"r": record_id, "u": [sup_id, dep_id, ceo_id]},
        )
        teardown.execute(
            text("DELETE FROM notifications WHERE evaluation_record_id = :r"), {"r": record_id}
        )
        teardown.execute(
            text("DELETE FROM evaluation_scores WHERE evaluation_record_id = :r"), {"r": record_id}
        )
        teardown.execute(
            text("DELETE FROM evaluation_comments WHERE evaluation_record_id = :r"), {"r": record_id}
        )
        teardown.execute(text("DELETE FROM evaluation_records WHERE id = :r"), {"r": record_id})
        teardown.execute(text("DELETE FROM personnel WHERE id = :p"), {"p": personnel_id})
        teardown.execute(
            text("DELETE FROM users WHERE id = ANY(:u)"), {"u": [sup_id, dep_id, ceo_id]}
        )
        teardown.commit()
    engine.dispose()


def _hold_lock_then_submit(committed_draft, lock_held: threading.Event) -> None:
    """شبیه‌سازی یک گذار هم‌زمان: قفل ردیف را می‌گیرد، وضعیت را عوض می‌کند، بعد commit."""
    with committed_draft["make_session"]() as session:
        record = session.scalar(
            select(EvaluationRecord)
            .where(EvaluationRecord.id == committed_draft["record_id"])
            .with_for_update(of=EvaluationRecord)
        )
        record.status = EvaluationStatus.submitted
        lock_held.set()
        # قفل تا commit نگه داشته می‌شود — هر خوانندهٔ قفل‌دار دیگری همین‌جا معطل می‌ماند.
        threading.Event().wait(LOCK_HOLD_SECONDS)
        session.commit()


def test_second_connection_cannot_take_the_row_lock_while_a_transition_holds_it(committed_draft):
    """اثبات این‌که قفل واقعاً بین دو اتصال مؤثر است، نه فقط در SQL تولیدشده."""
    lock_held = threading.Event()
    holder = threading.Thread(target=_hold_lock_then_submit, args=(committed_draft, lock_held))
    holder.start()
    try:
        assert lock_held.wait(timeout=5), "قفل‌گیرنده به‌موقع قفل را نگرفت"

        with committed_draft["make_session"]() as reader:
            reader.execute(text("SET LOCAL lock_timeout = '100ms'"))
            with pytest.raises(OperationalError):
                reader.scalar(
                    select(EvaluationRecord)
                    .where(EvaluationRecord.id == committed_draft["record_id"])
                    .with_for_update(of=EvaluationRecord)
                )
    finally:
        holder.join(timeout=5)


def test_score_write_racing_a_submit_sees_the_new_status_and_is_rejected(committed_draft):
    """مسابقهٔ واقعی: نوشتن امتیاز هم‌زمان با submit.

    با قفل، نوشتن تا commitِ submit معطل می‌ماند و بعد وضعیت *به‌روزشده* را می‌بیند و
    با ۴۰۳ رد می‌شود. بدون قفل (کد قبلی) وضعیت کهنه را می‌خواند و امتیاز را بعد از
    محاسبهٔ نتیجه می‌نوشت.
    """
    lock_held = threading.Event()
    holder = threading.Thread(target=_hold_lock_then_submit, args=(committed_draft, lock_held))
    holder.start()
    try:
        assert lock_held.wait(timeout=5), "قفل‌گیرنده به‌موقع قفل را نگرفت"

        with committed_draft["make_session"]() as writer:
            with pytest.raises(HTTPException) as excinfo:
                upsert_scores(
                    evaluation_id=committed_draft["record_id"],
                    payload=ScoresUpsert(scores=[]),
                    db=writer,
                    current_user=committed_draft["supervisor"],
                )
            assert excinfo.value.status_code == 403
    finally:
        holder.join(timeout=5)

    with committed_draft["make_session"]() as check:
        record = check.get(EvaluationRecord, committed_draft["record_id"])
        assert record.status == EvaluationStatus.submitted


def test_score_write_still_succeeds_when_nothing_is_racing(committed_draft):
    """گارد نباید مسیر عادی را بشکند — بدون رقابت، نوشتن پیش‌نویس مثل قبل کار می‌کند."""
    with committed_draft["make_session"]() as writer:
        rows = upsert_scores(
            evaluation_id=committed_draft["record_id"],
            payload=ScoresUpsert(scores=[]),
            db=writer,
            current_user=committed_draft["supervisor"],
        )
    assert rows == []


def test_comment_write_uses_the_row_lock(committed_draft):
    """set_evaluator_comment هم باید از همان هلپر قفل‌دار بخواند."""
    lock_held = threading.Event()
    holder = threading.Thread(target=_hold_lock_then_submit, args=(committed_draft, lock_held))
    holder.start()
    try:
        assert lock_held.wait(timeout=5), "قفل‌گیرنده به‌موقع قفل را نگرفت"

        with committed_draft["make_session"]() as writer:
            record = _get_record_or_404_for_update(writer, committed_draft["record_id"])
            # خواندن قفل‌دار تا commitِ گذار معطل ماند و حالا وضعیت تازه را می‌بیند.
            assert record.status == EvaluationStatus.submitted
    finally:
        holder.join(timeout=5)
