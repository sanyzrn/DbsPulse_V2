"""دادهٔ نمونهٔ «سناریومحور» برای توسعه — پرسنلی در همهٔ مراحل گردش‌کار.

سید پایه فقط سه پرسنل و یک پروندهٔ خالی می‌دهد، که برای دیدن رفتار واقعی سامانه کم
است: نه صف بررسی پر می‌شود، نه یادآوری تأخیر فعال می‌شود، نه آمارها عدد نشان می‌دهند
(میانگین‌ها زیر آستانهٔ کوهورت سرکوب می‌شوند).

این اسکریپت یک سازمان کوچکِ باورپذیر می‌سازد:

* واحد «فناوری اطلاعات» با ۶ ارزیابی نهایی‌شده — عمداً بیشتر از MIN_COHORT_SIZE،
  تا نمودارها و میانگین‌ها واقعاً عدد نشان بدهند.
* واحد «فروش» با ۲ نهایی‌شده — عمداً کمتر از آستانه، تا رفتار سرکوب هم دیده شود.
* یک پرونده در هر مرحلهٔ باز (پیش‌نویس، در صف HR، نزد معاونت، نزد مدیرعامل).
* یک پروندهٔ برگشت‌خورده، یک لغوشده، و یکی که ساعتِ مرحله‌اش عقب برده شده تا
  یادآوری SLA رویش فعال شود.
* یک پرسنل «مدیر» روی مسیر ویژه (بدون مسئول واحد).
* یک قرارداد رو به انقضا، تا هشدار تمدید فعال شود.
* حساب کاربری «کارمند» برای چند نفر، تا صفحهٔ «کارنامهٔ من» قابل تست باشد.

اجرا (از پوشهٔ backend، با venv فعال):

    python -m scripts.seed_demo_scenarios

بی‌خطر برای اجرای دوباره: هر بار پرسنل با کد جدید می‌سازد و چیزی را پاک نمی‌کند.
"""
import sys
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.enums import EvaluationStatus, PersonnelStatus, UserRole
from app.models.evaluation import EvaluationComment, EvaluationRecord, EvaluationScore
from app.models.evaluation_access import EvaluationAccess
from app.models.indicator import Indicator
from app.models.personnel import Personnel
from app.models.user import User
from app.services.evaluation import compute_result, next_evaluation_code

DEMO_ACCOUNT_PASSWORD = "Employee-Demo-1234"


def _require_non_production() -> None:
    if settings.environment == "production":
        sys.exit("این اسکریپت دادهٔ ساختگی می‌سازد و هرگز نباید روی production اجرا شود.")


def _actor(db, role: UserRole, username: str) -> User:
    """کاربر نقش‌دار را برمی‌گرداند و اگر نبود می‌سازد — تا اسکریپت به سید دمو وابسته نباشد."""
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(
            username=username,
            password_hash=hash_password(DEMO_ACCOUNT_PASSWORD),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.flush()
    return user


def _next_code(db, org_unit: str) -> str:
    base = "".join(ch for ch in org_unit if ch.isalnum())[:4] or "P"
    n = db.scalar(select(Personnel).order_by(Personnel.id.desc()))
    return f"{base}-{(n.id if n else 0) + 1:04d}"


def _make_personnel(
    db,
    *,
    full_name: str,
    org_unit: str,
    job_title: str = "کارشناس",
    is_manager: bool = False,
    contract_end: date | None = None,
    hr: User,
) -> Personnel:
    personnel = Personnel(
        personnel_code=_next_code(db, org_unit),
        full_name=full_name,
        job_title=job_title,
        is_manager=is_manager,
        org_unit=org_unit,
        contract_start_date=date.today() - timedelta(days=400),
        contract_end_date=contract_end or (date.today() + timedelta(days=200)),
        status=PersonnelStatus.active,
        created_by_user_id=hr.id,
    )
    db.add(personnel)
    db.flush()
    return personnel


def _give_account(db, personnel: Personnel, username: str) -> User:
    user = User(
        username=username,
        password_hash=hash_password(DEMO_ACCOUNT_PASSWORD),
        role=UserRole.employee,
        personnel_id=personnel.id,
        is_active=True,
        # عمداً False: این حساب‌ها برای تست فوریِ «کارنامهٔ من» ساخته می‌شوند و
        # اجبار به تغییر رمز فقط سر راه است. مسیر واقعیِ ساخت کاربر (فرم پرسنل)
        # همیشه True می‌گذارد.
        must_change_password=False,
    )
    db.add(user)
    db.flush()
    return user


def _scores_for(db, record: EvaluationRecord, value: int) -> None:
    indicators = list(db.scalars(select(Indicator).where(Indicator.is_active.is_(True))))
    for indicator in indicators:
        db.add(
            EvaluationScore(
                evaluation_record_id=record.id,
                indicator_id=indicator.id,
                score=value,
                # امتیاز ۱ و ۵ شواهد اجباری دارند (حداقل ۳ کلمه)
                evidence_text=(
                    "بر اساس گزارش مستند واحد در بازه ارزیابی" if value in (1, 5) else None
                ),
            )
        )
    db.flush()

    indicators_by_id = {i.id: i for i in indicators}
    rows = [
        {"indicator_id": i.id, "score": value, "evidence_text": None} for i in indicators
    ]
    result = compute_result(rows, indicators_by_id)
    record.general_score_pct = result["general_score_pct"]
    record.specialized_score_pct = result["specialized_score_pct"]
    record.final_weighted_pct = result["final_weighted_pct"]
    record.recommendation = result["recommendation"]


def _make_evaluation(
    db,
    *,
    personnel: Personnel,
    sup: User | None,
    dep: User,
    ceo: User,
    hr: User | None,
    status: EvaluationStatus,
    score: int = 4,
    stage_age_days: int = 0,
) -> EvaluationRecord:
    db.add(
        EvaluationAccess(
            personnel_id=personnel.id,
            unit_supervisor_user_id=sup.id if sup else None,
            deputy_user_id=dep.id,
            ceo_user_id=ceo.id,
            updated_by_user_id=dep.id,
        )
    )
    record = EvaluationRecord(
        evaluation_code=next_evaluation_code(db),
        subject_personnel_id=personnel.id,
        unit_supervisor_user_id=sup.id if sup else None,
        deputy_user_id=dep.id,
        ceo_user_id=ceo.id,
        hr_user_id=hr.id if hr else None,
        status=status,
        stage_entered_at=datetime.now(UTC) - timedelta(days=stage_age_days),
    )
    db.add(record)
    db.flush()

    # پیش‌نویس هنوز نمره‌ای ندارد؛ بقیهٔ مراحل امتیازِ محاسبه‌شده دارند
    if status != EvaluationStatus.draft:
        _scores_for(db, record, score)
    if status == EvaluationStatus.finalized:
        record.finalized_at = datetime.now(UTC) - timedelta(days=stage_age_days)
    db.flush()
    return record


def main() -> None:
    _require_non_production()
    db = SessionLocal()
    try:
        hr = _actor(db, UserRole.hr, "hr1")
        sup_it = _actor(db, UserRole.unit_supervisor, "sup_it")
        sup_sales = _actor(db, UserRole.unit_supervisor, "sup_sales")
        dep = _actor(db, UserRole.deputy, "dep1")
        ceo = _actor(db, UserRole.ceo, "ceo1")

        created: list[str] = []

        # ── واحد فناوری اطلاعات: ۶ نهایی‌شده، بالاتر از آستانهٔ کوهورت ──────────
        it_names = ["نیما شریفی", "الهام رستمی", "بهرام کاظمی", "شیوا نوری", "کامران عبدی", "لیلا موسوی"]
        for index, name in enumerate(it_names):
            person = _make_personnel(db, full_name=name, org_unit="فناوری اطلاعات", hr=hr)
            _make_evaluation(
                db,
                personnel=person,
                sup=sup_it,
                dep=dep,
                ceo=ceo,
                hr=hr,
                status=EvaluationStatus.finalized,
                # پراکندگی امتیاز تا نمودارها تخت نباشند
                score=[5, 4, 4, 3, 3, 2][index],
                stage_age_days=30 - index * 3,
            )
        created.append(f"فناوری اطلاعات: {len(it_names)} ارزیابی نهایی‌شده (بالای آستانهٔ کوهورت)")

        # ── واحد فروش: فقط ۲ نهایی‌شده، زیر آستانه → میانگینش سرکوب می‌شود ───────
        for name, score in (("رضا فتحی", 4), ("مینا اکبری", 3)):
            person = _make_personnel(db, full_name=name, org_unit="فروش", hr=hr)
            _make_evaluation(
                db, personnel=person, sup=sup_sales, dep=dep, ceo=ceo, hr=hr,
                status=EvaluationStatus.finalized, score=score, stage_age_days=20,
            )
        created.append("فروش: ۲ نهایی‌شده (زیر آستانه — میانگینش «محرمانه» می‌ماند)")

        # ── یکی در هر مرحلهٔ باز ────────────────────────────────────────────────
        open_stages = [
            ("سعید مرادی", EvaluationStatus.draft, "نزد مسئول واحد", None),
            ("فاطمه زارع", EvaluationStatus.submitted, "در صف بررسی منابع انسانی", None),
            ("حامد یوسفی", EvaluationStatus.hr_approved, "در انتظار معاونت", hr),
            ("پریسا صادقی", EvaluationStatus.deputy_approved, "در انتظار مدیرعامل", hr),
        ]
        for name, status, label, owner in open_stages:
            person = _make_personnel(db, full_name=name, org_unit="فناوری اطلاعات", hr=hr)
            _make_evaluation(
                db, personnel=person, sup=sup_it, dep=dep, ceo=ceo, hr=owner, status=status
            )
            created.append(f"{name}: {label}")

        # ── پرونده‌ای که ساعتِ مرحله‌اش عقب رفته → یادآوری SLA فعال می‌شود ───────
        stalled = _make_personnel(db, full_name="آرش دهقان", org_unit="فروش", hr=hr)
        _make_evaluation(
            db, personnel=stalled, sup=sup_sales, dep=dep, ceo=ceo, hr=None,
            status=EvaluationStatus.submitted, stage_age_days=settings.sla_reminder_days + 4,
        )
        created.append("آرش دهقان: گیرکرده در صف HR — جاروی SLA رویش فعال می‌شود")

        # ── پروندهٔ برگشت‌خورده (نشان «برگشتی» را نشان می‌دهد) ───────────────────
        returned_person = _make_personnel(db, full_name="سمیرا قاسمی", org_unit="فناوری اطلاعات", hr=hr)
        returned = _make_evaluation(
            db, personnel=returned_person, sup=sup_it, dep=dep, ceo=ceo, hr=hr,
            status=EvaluationStatus.draft,
        )
        db.add(
            EvaluationComment(
                evaluation_record_id=returned.id,
                commenter_user_id=hr.id,
                stage="hr_review",
                comment_text="برگشت پرونده — دلیل: شواهد شاخص «تعهد سازمانی» کافی نیست",
            )
        )
        from app.services.audit import log_event

        log_event(
            db, actor_user_id=hr.id, event_type="evaluation_returned",
            evaluation_record_id=returned.id, new_value={"reason": "شواهد ناکافی"},
        )
        created.append("سمیرا قاسمی: برگشت‌خورده (نشان «برگشتی» دارد)")

        # ── پروندهٔ لغوشده ──────────────────────────────────────────────────────
        cancelled_person = _make_personnel(db, full_name="جواد نیکو", org_unit="فروش", hr=hr)
        cancelled = _make_evaluation(
            db, personnel=cancelled_person, sup=sup_sales, dep=dep, ceo=ceo, hr=hr,
            status=EvaluationStatus.cancelled,
        )
        db.add(
            EvaluationComment(
                evaluation_record_id=cancelled.id,
                commenter_user_id=hr.id,
                stage="hr_review",
                comment_text="لغو پرونده — دلیل: پرسنل پیش از پایان ارزیابی از سازمان خارج شد",
            )
        )
        created.append("جواد نیکو: لغوشده (می‌شود برایش پروندهٔ جایگزین باز کرد)")

        # ── مسیر ویژهٔ «مدیر»: بدون مسئول واحد ──────────────────────────────────
        manager = _make_personnel(
            db, full_name="محسن رحیمی", org_unit="فناوری اطلاعات",
            job_title="مدیر فناوری اطلاعات", is_manager=True, hr=hr,
        )
        _make_evaluation(
            db, personnel=manager, sup=None, dep=dep, ceo=ceo, hr=hr,
            status=EvaluationStatus.hr_approved,
        )
        created.append("محسن رحیمی: مسیر «مدیر» — معاونت خودش نمره‌دهندهٔ اول است")

        # ── قرارداد رو به انقضا، بدون ارزیابی باز → هشدار تمدید ─────────────────
        expiring = _make_personnel(
            db, full_name="نسرین بیات", org_unit="فروش", hr=hr,
            contract_end=date.today() + timedelta(days=12),
        )
        db.add(
            EvaluationAccess(
                personnel_id=expiring.id,
                unit_supervisor_user_id=sup_sales.id,
                deputy_user_id=dep.id,
                ceo_user_id=ceo.id,
                updated_by_user_id=hr.id,
            )
        )
        created.append("نسرین بیات: قرارداد ۱۲ روز دیگر تمام می‌شود، بدون ارزیابی باز")

        # ── حساب «کارمند» برای چند نفر، تا «کارنامهٔ من» قابل تست باشد ──────────
        accounts = []
        for username, person in (("emp.nima", it_names[0]), ("emp.reza", "رضا فتحی")):
            target = db.scalar(select(Personnel).where(Personnel.full_name == person))
            if target and not db.scalar(select(User).where(User.personnel_id == target.id)):
                _give_account(db, target, username)
                accounts.append(f"{username} → {person}")

        db.commit()

        print("دادهٔ سناریویی ساخته شد:\n")
        for line in created:
            print(f"  • {line}")
        if accounts:
            print("\nحساب‌های کارمند (رمز همه: " + DEMO_ACCOUNT_PASSWORD + "):")
            for line in accounts:
                print(f"  • {line}")
        print("\nارزیاب‌ها: sup_it / sup_sales / dep1 / ceo1 / hr1")
        print(f"رمز کاربران تازه‌ساخته: {DEMO_ACCOUNT_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
