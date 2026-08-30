"""ماشین حالت گردش‌کار ارزیابی — به‌صورت اعلانی (declarative).

پیش از این هر endpoint گاردهای وضعیت/نقش/شخص را جداگانه و با کپی/پیست پیاده می‌کرد
(و ناهماهنگی هم داشت). حالا هر گذار مجاز یک ردیف داده است و یک تابع واحد اعتبارسنجی،
تغییر وضعیت و ثبت audit را انجام می‌دهد. ستون stage هم حذف شده و از status مشتق
می‌شود (schemas/evaluation.py) — دو ستونِ هم‌معنا دو منبع حقیقت بودند.
"""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.metrics import workflow_transitions
from app.models.enums import EvaluationStatus, UserRole
from app.models.evaluation import EvaluationRecord, EvaluationScore
from app.schemas.auth import CurrentUser
from app.services.audit import log_event
from app.services.evaluation import compute_result, validate_evidence
from app.services.indicator_framework import indicators_for_record
from app.services.scoring_scheme import rules_for_record

OPEN_STATUSES: frozenset[EvaluationStatus] = frozenset(
    {
        EvaluationStatus.draft,
        EvaluationStatus.submitted,
        EvaluationStatus.hr_approved,
        EvaluationStatus.deputy_approved,
    }
)
"""وضعیت‌هایی که پرونده هنوز «باز» است. finalized و cancelled پایانی‌اند."""

IS_OPEN_RECORD = EvaluationRecord.status.in_(OPEN_STATUSES)
"""شرط «پروندهٔ باز» برای کوئری‌ها.

پیش از این، همه‌جا `status != finalized` نوشته می‌شد — که وقتی وضعیت پایانی دومی
(cancelled) اضافه شد، در ۸ نقطهٔ مختلف غلط می‌شد و پروندهٔ لغوشده را «در جریان»
می‌شمرد. یک منبع مشترک یعنی وضعیت پایانی بعدی فقط همین‌جا اضافه می‌شود."""


@dataclass(frozen=True)
class Transition:
    # مجموعه است نه تک‌مقدار: لغو پرونده از هر مرحلهٔ بازی ممکن است، بقیهٔ گذارها
    # فقط از یک وضعیت مشخص.
    from_statuses: frozenset[EvaluationStatus]
    to_status: EvaluationStatus
    allowed_role: UserRole
    # نام فیلدی روی رکورد که شناسه کاربر مجاز را نگه می‌دارد؛ None یعنی هر کاربری با نقش مجاز
    assignee_field: str | None
    error_status: int
    error_detail: str
    # اگر True و آن فیلد هنوز NULL باشد، هر کاربری با نقش مجاز می‌تواند اقدام کند و
    # با همان اقدام مالک می‌شود. مخصوص مرحلهٔ HR که برخلاف سه مرحلهٔ دیگر از یک صف
    # مشترک شروع می‌شود، نه از یک شخص از پیش تعیین‌شده.
    claimable_if_unassigned: bool = False
    # پیام مخصوصِ «این پرونده مالِ کاربر دیگری است» — وقتی error_detail خودش این
    # معنا را نمی‌رساند (مثل مرحلهٔ HR که پیامش دربارهٔ وضعیت است، نه مالکیت).
    owner_error_detail: str | None = None
    # شرط اضافه بر وضعیت. برای گذارهایی که *نبودنِ* یک مرحله مجازشان می‌کند:
    # مدیرعامل می‌تواند از `hr_approved` نهایی کند، ولی فقط وقتی معاونتی در
    # زنجیره نیست. بدون این شرط، همان گذار راهی می‌شد برای دورزدنِ تأیید معاونت.
    guard: "Callable[[EvaluationRecord], bool] | None" = None


def is_manager_path(record: EvaluationRecord) -> bool:
    """مسیر «مدیر»: مسئول واحد ندارد؛ معاونت خودش نمره‌دهنده اول است."""
    return record.unit_supervisor_user_id is None


# `is_manager_path` عمداً پیش از این جدول تعریف شده: چند گذار مستقیماً به آن
# ارجاع می‌دهند (نه از راه lambda)، و پایین‌تر بودنش یعنی NameError در import.
TRANSITIONS: dict[str, Transition] = {
    "submit": Transition(
        from_statuses=frozenset({EvaluationStatus.draft}),
        to_status=EvaluationStatus.submitted,
        allowed_role=UserRole.unit_supervisor,
        assignee_field="unit_supervisor_user_id",
        guard=lambda record: not is_manager_path(record),
        error_status=http_status.HTTP_403_FORBIDDEN,
        error_detail="این ارزیابی در مرحله ثبت توسط شما نیست",
    ),
    # مسیر «مدیر»: همان گذار، ولی نمره‌دهنده‌اش معاونت است. تا امروز این مسیر
    # اصلاً به `submitted` نمی‌رسید — یعنی *مرحلهٔ بررسی منابع انسانی را نداشت*
    # — و پروندهٔ مدیران، پرامدترین ارزیابی‌های سازمان، با دو چشم بسته می‌شد در
    # حالی که پروندهٔ یک کارشناس با چهار چشم.
    "manager_submit": Transition(
        from_statuses=frozenset({EvaluationStatus.draft}),
        to_status=EvaluationStatus.submitted,
        allowed_role=UserRole.deputy,
        assignee_field="deputy_user_id",
        guard=is_manager_path,
        error_status=http_status.HTTP_403_FORBIDDEN,
        error_detail="این ارزیابی در مرحله ثبت توسط شما نیست",
    ),
    "hr_approve": Transition(
        from_statuses=frozenset({EvaluationStatus.submitted}),
        to_status=EvaluationStatus.hr_approved,
        allowed_role=UserRole.hr,
        assignee_field="hr_user_id",
        claimable_if_unassigned=True,
        guard=lambda record: not is_manager_path(record),
        error_status=http_status.HTTP_400_BAD_REQUEST,
        error_detail="این ارزیابی در انتظار بررسی منابع انسانی نیست",
        owner_error_detail="این پرونده در اختیار کاربر دیگری از منابع انسانی است",
    ),
    # در مسیر «مدیر» معاونت نمره را از قبل داده و ثبت کرده، پس تأیید منابع انسانی
    # مستقیماً پرونده را روی میز مدیرعامل می‌گذارد. مرحلهٔ معاونت پریده می‌شود چون
    # *انجام شده*، نه چون وجود ندارد.
    "hr_approve_manager": Transition(
        from_statuses=frozenset({EvaluationStatus.submitted}),
        to_status=EvaluationStatus.deputy_approved,
        allowed_role=UserRole.hr,
        assignee_field="hr_user_id",
        claimable_if_unassigned=True,
        guard=is_manager_path,
        error_status=http_status.HTTP_400_BAD_REQUEST,
        error_detail="این ارزیابی در انتظار بررسی منابع انسانی نیست",
        owner_error_detail="این پرونده در اختیار کاربر دیگری از منابع انسانی است",
    ),
    "deputy_approve": Transition(
        from_statuses=frozenset({EvaluationStatus.hr_approved}),
        to_status=EvaluationStatus.deputy_approved,
        allowed_role=UserRole.deputy,
        assignee_field="deputy_user_id",
        error_status=http_status.HTTP_403_FORBIDDEN,
        error_detail="این ارزیابی در مرحله تأیید معاونت توسط شما نیست",
    ),
    "ceo_finalize": Transition(
        from_statuses=frozenset(
            {EvaluationStatus.deputy_approved, EvaluationStatus.hr_approved}
        ),
        guard=lambda record: (
            record.status is not EvaluationStatus.hr_approved
            or record.deputy_user_id is None
        ),
        to_status=EvaluationStatus.finalized,
        allowed_role=UserRole.ceo,
        assignee_field="ceo_user_id",
        error_status=http_status.HTTP_403_FORBIDDEN,
        error_detail="این ارزیابی در مرحله تأیید نهایی توسط شما نیست",
    ),
    # گذارهای «برگشت پرونده»: هر تأییدکننده می‌تواند پرونده را با ذکر دلیل یک مرحله
    # عقب بفرستد. امتیازهای قبلی حفظ می‌شوند تا نمره‌دهنده فقط موارد لازم را اصلاح کند.
    "hr_return": Transition(
        from_statuses=frozenset({EvaluationStatus.submitted}),
        to_status=EvaluationStatus.draft,
        allowed_role=UserRole.hr,
        assignee_field="hr_user_id",
        claimable_if_unassigned=True,
        error_status=http_status.HTTP_400_BAD_REQUEST,
        error_detail="این ارزیابی در انتظار بررسی منابع انسانی نیست",
        owner_error_detail="این پرونده در اختیار کاربر دیگری از منابع انسانی است",
    ),
    "deputy_return": Transition(
        from_statuses=frozenset({EvaluationStatus.hr_approved}),
        to_status=EvaluationStatus.submitted,
        allowed_role=UserRole.deputy,
        assignee_field="deputy_user_id",
        error_status=http_status.HTTP_403_FORBIDDEN,
        error_detail="این ارزیابی در مرحله بررسی معاونت توسط شما نیست",
    ),
    "ceo_return": Transition(
        from_statuses=frozenset({EvaluationStatus.deputy_approved}),
        to_status=EvaluationStatus.hr_approved,
        allowed_role=UserRole.ceo,
        assignee_field="ceo_user_id",
        guard=lambda record: not is_manager_path(record),
        error_status=http_status.HTTP_403_FORBIDDEN,
        error_detail="این ارزیابی در مرحله تأیید نهایی توسط شما نیست",
    ),
    # برگشت مدیرعامل در مسیر «مدیر» به منابع انسانی می‌رود، نه به مرحلهٔ معاونت:
    # آن مرحله در این مسیر مصرف شده (معاونت نمره داده و ثبت کرده). بی این گذار،
    # پرونده به `hr_approved` برمی‌گشت و معاونت باید یک تأییدِ توخالی می‌زد.
    "ceo_return_manager": Transition(
        from_statuses=frozenset({EvaluationStatus.deputy_approved}),
        to_status=EvaluationStatus.submitted,
        allowed_role=UserRole.ceo,
        assignee_field="ceo_user_id",
        guard=is_manager_path,
        error_status=http_status.HTTP_403_FORBIDDEN,
        error_detail="این ارزیابی در مرحله تأیید نهایی توسط شما نیست",
    ),
    # راه خروج از پروندهٔ گیرکرده. تا پیش از این هیچ گذار پایانی جز نهایی‌سازی وجود
    # نداشت: اگر تأییدکننده‌ای استعفا می‌داد، مرحله‌اش هرگز کامل نمی‌شد و ایندکس یکتای
    # جزئی هم اجازهٔ ساخت پروندهٔ جایگزین نمی‌داد — آن پرسنل برای همیشه غیرقابل‌ارزیابی
    # می‌شد. تنها درمان، SQL دستی روی پروداکشن بود.
    "cancel": Transition(
        from_statuses=OPEN_STATUSES,
        to_status=EvaluationStatus.cancelled,
        allowed_role=UserRole.hr,
        assignee_field=None,
        error_status=http_status.HTTP_400_BAD_REQUEST,
        error_detail="فقط پروندهٔ باز (نهایی‌نشده و لغونشده) قابل لغو است",
    ),
}


def ensure_transition_allowed(
    record: EvaluationRecord, action: str, current_user: CurrentUser
) -> Transition:
    spec = TRANSITIONS[action]
    denied = HTTPException(status_code=spec.error_status, detail=spec.error_detail)
    if record.status not in spec.from_statuses or not may_act_at(
        current_user.role, spec.allowed_role
    ):
        raise denied
    if spec.guard is not None and not spec.guard(record):
        raise denied
    if spec.assignee_field is not None:
        assignee = getattr(record, spec.assignee_field)
        # صف مشترک: تا وقتی کسی مالک نشده، هر کاربری با نقش مجاز می‌تواند برش دارد.
        if not (assignee is None and spec.claimable_if_unassigned) and current_user.id != assignee:
            # «مال تو نیست» با «هنوز نوبتش نشده» فرق دارد. برای مسئول واحد/معاونت/
            # مدیرعامل همان error_detail خودش این را می‌گوید؛ مرحلهٔ HR چون از یک صف
            # مشترک شروع می‌شود پیام جداگانه لازم دارد.
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail=spec.owner_error_detail or spec.error_detail,
            )
    return spec


def apply_transition(
    db: Session,
    record: EvaluationRecord,
    action: str,
    current_user: CurrentUser,
    before: Callable[[], None] | None = None,
) -> None:
    """اعتبارسنجی گذار، اجرای منطق اختصاصی (مثل نهایی‌سازی امتیازها)، تغییر وضعیت و audit."""
    spec = ensure_transition_allowed(record, action, current_user)
    # نهایی‌سازی بدون نتیجه ممنوع — گاردِ دومِ اصلاحِ C-1. پرونده‌ای که مسیر
    # سالمش رفته باشد در `submit` نتیجه‌اش محاسبه شده؛ `final_weighted_pct`
    # خالی یعنی این پرونده از مسیری آمده که نمره‌دهی نداشته (مثل باگِ قدیمیِ
    # ساختِ دسته‌ایِ مدیران). این گارد در apply_transition است تا هم رابط و
    # هم دستیار — که هر دو از همین تابع می‌گذرند — نتوانند پروندهٔ بی‌نمره
    # را با امضای «نهایی‌شده» ببندند.
    if spec.to_status is EvaluationStatus.finalized:
        has_scores = (
            db.scalar(
                select(func.count())
                .select_from(EvaluationScore)
                .where(EvaluationScore.evaluation_record_id == record.id)
            )
            or 0
        )
        if record.final_weighted_pct is None or has_scores == 0:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=(
                    "این پرونده نتیجهٔ محاسبه‌شده ندارد (امتیازی ثبت نشده است)؛ "
                    "نهایی‌سازی بدون نتیجهٔ معتبر ممکن نیست"
                ),
            )
    # اقدام روی پروندهٔ بی‌مالک، همان اقدام را به مالک‌شدن تبدیل می‌کند — تا بعداً
    # معلوم باشد «مسئولش که بود»، نه فقط «کی کلیک کرد».
    if (
        spec.claimable_if_unassigned
        and spec.assignee_field is not None
        and getattr(record, spec.assignee_field) is None
    ):
        setattr(record, spec.assignee_field, current_user.id)
        log_event(
            db,
            actor_user_id=current_user.id,
            event_type="hr_case_claimed",
            evaluation_record_id=record.id,
            new_value={spec.assignee_field: current_user.id, "implicit": True},
        )
    if before is not None:
        before()
    old_status = record.status
    record.status = spec.to_status
    # ساعتِ مرحله با هر گذار صفر می‌شود — «چقدر در این مرحله مانده» تنها چیزی است که
    # یادآوری تأخیر باید بسنجد. برگشت پرونده هم یک گذار است، پس درست هندل می‌شود.
    record.stage_entered_at = datetime.now(UTC)
    if spec.to_status == EvaluationStatus.finalized and record.finalized_at is None:
        record.finalized_at = datetime.now(UTC)
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="status_changed",
        evaluation_record_id=record.id,
        old_value={"status": old_status.value},
        new_value={"status": record.status.value},
    )
    # «چند پرونده امروز به هر مرحله رفت» — افت ناگهانی یعنی جایی گیر کرده است
    workflow_transitions.labels(to_status=record.status.value).inc()
    # نفر بعدی زنجیره در همان تراکنش اعلان می‌گیرد (import محلی برای پرهیز از حلقه import)
    from app.services.notifications import notify_for_workflow_action

    notify_for_workflow_action(db, record, action)


#: جایگاه هر نقش در سلسله‌مراتب زنجیرهٔ ارزیابی. منابع انسانی عمداً این‌جا نیست:
#: نقشِ HR یک *پله* در سلسله‌مراتب نیست، یک وظیفهٔ جداست، و هیچ‌کس نباید با
#: بالاتربودن بتواند جای آن بنشیند.
_CHAIN_RANK: dict[UserRole, int] = {
    UserRole.unit_supervisor: 1,
    UserRole.deputy: 2,
    UserRole.ceo: 3,
}


def may_act_at(user_role: UserRole, stage_role: UserRole) -> bool:
    """آیا این نقش می‌تواند کارِ این مرحله را انجام دهد؟

    مافوق می‌تواند کارِ مرحلهٔ پایین‌تر را بکند. این از ساختار واقعی یک سازمان
    آمد: مدیرعاملی که برای چهار نفر خودش مسئول مستقیم هم هست، و معاونتی که برای
    چند نفر نمره‌دهندهٔ اول است. تا پیش از این هر حساب یک نقش داشت و گارد همان
    را می‌سنجید، پس چنین آدمی *اصلاً قابل تنظیم نبود* — نه اینکه سخت بود.
    نمی‌شد.

    این گارد را شل نمی‌کند: تنها راه اقدام روی یک پرونده همچنان این است که
    شناسهٔ همان شخص در آن مرحله از زنجیره نشسته باشد (`assignee_field`). این
    تابع فقط می‌گوید چه کسی *می‌تواند* در آن مرحله نشانده شود.
    """
    if stage_role is UserRole.hr:
        return user_role is UserRole.hr
    user_rank = _CHAIN_RANK.get(user_role)
    stage_rank = _CHAIN_RANK.get(stage_role)
    if user_rank is None or stage_rank is None:
        return False
    return user_rank >= stage_rank


def skips_deputy(record: EvaluationRecord) -> bool:
    """این پرونده مرحلهٔ معاونت ندارد؛ پس از منابع انسانی مستقیم به مدیرعامل می‌رود.

    قرینهٔ `is_manager_path` برای آن سرِ زنجیره. هر دو یک چیز می‌گویند: مرحله‌ای
    که کسی در آن نایستاده، نباید پرونده را نگه دارد.
    """
    return record.deputy_user_id is None


# `active_indicators_by_id` عمداً حذف شد (P1-05). هر جا که پرسیده می‌شود «این
# پرونده به چه شاخص‌هایی نمره می‌دهد»، باید از `indicators_for_record` بپرسد.
# گذاشتنِ نسخهٔ «فعالِ امروز» کنارش، یعنی همان اشتباه یک import دورتر است.


def scores_as_dicts(db: Session, record: EvaluationRecord) -> list[dict]:
    scores = db.scalars(
        select(EvaluationScore).where(EvaluationScore.evaluation_record_id == record.id)
    )
    return [
        {"indicator_id": s.indicator_id, "score": s.score, "evidence_text": s.evidence_text}
        for s in scores
    ]


def finalize_scoring(db: Session, record: EvaluationRecord, current_user: CurrentUser) -> None:
    """اعتبارسنجی شواهد + کامل بودن شاخص‌ها + محاسبه درصدها؛ مشترک بین submit (مسئول واحد) و
    deputy-approve مسیر «مدیر» که در آن معاونت خودش نمره‌دهنده اول است."""
    # شاخص‌های *این پرونده*، نه مجموعهٔ فعالِ امروز (P1-05). تفاوتشان همان چیزی
    # بود که پیش‌نویس‌های در جریان را قفل می‌کرد: ارزیاب فرم را کامل پر می‌کرد،
    # منابع انسانی سؤالی اضافه یا کم می‌کرد، و «ثبت» فردا کار نمی‌کرد.
    indicators_by_id = indicators_for_record(db, record)
    scores = scores_as_dicts(db, record)

    scored_ids = {row["indicator_id"] for row in scores}
    if scored_ids != set(indicators_by_id.keys()):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="باید به تمام شاخص‌های این ارزیابی (عمومی و تخصصی) امتیاز داده شود",
        )

    # قواعد از طرحِ *این پرونده* می‌آیند، نه از طرح فعال (P1-04). اگر HR وسط
    # چرخه وزن‌ها را عوض کند، پرونده‌های باز با همان قواعدی بسته می‌شوند که زیر
    # آن‌ها باز شده‌اند — وگرنه ارزیابی که نیمه‌کاره رها شده بود، با قواعدی
    # نهایی می‌شد که ارزیاب هرگز ندیده است.
    rules = rules_for_record(db, record)

    try:
        validate_evidence(scores, indicators_by_id, rules)
    except ValueError as exc:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # امتیاز ویژه از خود پرونده می‌آید (ارزیاب پیش از ثبت واردش کرده). محاسبه
    # همیشه این‌جا از نو انجام می‌شود، پس پرونده‌ای که برگشت خورده و دوباره ثبت
    # می‌شود هم با همان امتیاز ویژهٔ ثبت‌شده حساب می‌شود، نه با نتیجهٔ کهنه.
    result = compute_result(
        scores, indicators_by_id, rules, bonus_points=float(record.bonus_points or 0)
    )
    record.base_weighted_pct = result["base_weighted_pct"]
    record.general_score_pct = result["general_score_pct"]
    record.specialized_score_pct = result["specialized_score_pct"]
    record.final_weighted_pct = result["final_weighted_pct"]
    record.recommendation = result["recommendation"]

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="score_submitted",
        evaluation_record_id=record.id,
        new_value=result,
    )
