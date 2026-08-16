from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_capability
from app.db.session import get_db
from app.models.enums import Capability, IndicatorSection
from app.models.evaluation import EvaluationScore
from app.models.indicator import Indicator
from app.schemas.auth import CurrentUser
from app.schemas.indicator import (
    FrameworkImpact,
    IndicatorCreate,
    IndicatorRead,
    IndicatorReorder,
    IndicatorReplace,
    IndicatorUpdate,
)
from app.services.audit import log_event
from app.services.indicator_framework import (
    bump,
    ensure_framework,
    impact_of_membership_change,
    rebind_untouched_open_records,
)

router = APIRouter(prefix="/api/indicators", tags=["indicators"])


def _publish(
    db: Session, *, actor_user_id: int, change_kind: str, change_note: str | None = None
) -> int:
    """نسخهٔ تازهٔ چارچوب را می‌سازد و پرونده‌های دست‌نخورده را به آن می‌برد.

    هر مسیری که *عضویت* را عوض می‌کند باید از این‌جا رد شود. یادش رفتن یعنی
    برگشتِ همان خرابی، فقط از دری که تست‌ها نگاهش نمی‌کنند.
    """
    framework = bump(
        db, actor_user_id=actor_user_id, change_kind=change_kind, change_note=change_note
    )
    return rebind_untouched_open_records(db, framework)


def _scored_count(db: Session, indicator_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(EvaluationScore)
            .where(EvaluationScore.indicator_id == indicator_id)
        )
        or 0
    )


@router.get("", response_model=list[IndicatorRead])
def list_indicators(
    section: IndicatorSection | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[IndicatorRead]:
    # شمارش استفاده با یک outer join، نه یک کوئری به‌ازای هر شاخص: این فهرست در
    # هر بار باز شدن فرم ارزیابی خوانده می‌شود، نه فقط در صفحهٔ مدیریت شاخص‌ها.
    query = (
        select(Indicator, func.count(EvaluationScore.id))
        .outerjoin(EvaluationScore, EvaluationScore.indicator_id == Indicator.id)
        .group_by(Indicator.id)
    )
    if section is not None:
        query = query.where(Indicator.section == section)
    if not include_inactive:
        query = query.where(Indicator.is_active.is_(True))
    query = query.order_by(Indicator.section, Indicator.display_order)
    return [
        IndicatorRead.model_validate(indicator).model_copy(update={"usage_count": used})
        for indicator, used in db.execute(query)
    ]


@router.post("", response_model=IndicatorRead, status_code=status.HTTP_201_CREATED)
def create_indicator(
    payload: IndicatorCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_scoring)),
) -> Indicator:
    # display_order به‌صورت خودکار به انتهای همان بخش اضافه می‌شود؛ ورودی کاربر نادیده
    # گرفته می‌شود تا HR مجبور به مدیریت دستی شماره‌ها نباشد (ترتیب با drag تغییر می‌کند).
    fields = payload.model_dump()
    max_order = db.scalar(
        select(func.max(Indicator.display_order)).where(Indicator.section == payload.section)
    )
    fields["display_order"] = (max_order or 0) + 1
    indicator = Indicator(**fields, is_active=True)
    db.add(indicator)
    db.flush()
    moved = _publish(db, actor_user_id=current_user.id, change_kind="indicator_added")
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="indicator_created",
        new_value={
            "id": indicator.id,
            "section": indicator.section.value,
            "category": indicator.category,
            "description": indicator.description,
            "rebound_open_records": moved,
        },
    )
    db.commit()
    db.refresh(indicator)
    return indicator


@router.get("/framework", response_model=FrameworkImpact)
def framework_impact(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_scoring)),
) -> FrameworkImpact:
    """نسخهٔ جاری چارچوب و اثرِ تغییر بعدی.

    فرانت‌اند این را *قبل از* ذخیره نشان می‌دهد. تا امروز منابع انسانی هیچ راهی
    نداشت بفهمد یک ویرایش ساده روی چند پروندهٔ در جریان اثر می‌گذارد — و چون
    خرابی هم بی‌صدا بود، معمولاً اولین کسی که می‌فهمید ارزیاب بود.
    """
    framework = ensure_framework(db)
    db.commit()
    return FrameworkImpact(
        version=framework.version,
        member_count=len(framework.member_ids),
        **impact_of_membership_change(db),
    )


@router.patch("/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_indicators(
    payload: IndicatorReorder,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_scoring)),
) -> None:
    """ترتیب شاخص‌های یک بخش را بر اساس ترتیب drag کاربر بازنویسی می‌کند. ordered_ids
    باید دقیقاً همان مجموعهٔ شناسه‌های آن بخش باشد (نه کم، نه زیاد، بدون تکرار)."""
    existing = list(
        db.scalars(select(Indicator).where(Indicator.section == payload.section))
    )
    existing_ids = {ind.id for ind in existing}
    submitted_ids = set(payload.ordered_ids)
    if len(payload.ordered_ids) != len(submitted_ids) or submitted_ids != existing_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="فهرست ترتیب باید دقیقاً شامل همهٔ شاخص‌های همین بخش باشد",
        )

    by_id = {ind.id: ind for ind in existing}
    for position, indicator_id in enumerate(payload.ordered_ids, start=1):
        by_id[indicator_id].display_order = position

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="indicators_reordered",
        new_value={"section": payload.section.value, "ordered_ids": payload.ordered_ids},
    )
    db.commit()


@router.delete("/{indicator_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_indicator(
    indicator_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_scoring)),
) -> None:
    """حذف کامل یک شاخص — فقط وقتی مجاز است که در هیچ ارزیابی‌ای امتیاز نخورده باشد؛
    در غیر این صورت داده‌های تاریخی می‌شکنند و باید به‌جای حذف، «غیرفعال» شود (۴۰۹)."""
    indicator = db.get(Indicator, indicator_id)
    if indicator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="شاخص یافت نشد")

    if _scored_count(db, indicator_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "این شاخص در ارزیابی‌های ثبت‌شده استفاده شده و قابل حذف نیست؛ "
                "برای کنار گذاشتن آن از فرم‌های جدید، «غیرفعال»‌اش کنید."
            ),
        )

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="indicator_deleted",
        old_value={
            "id": indicator.id,
            "section": indicator.section.value,
            "category": indicator.category,
            "description": indicator.description,
        },
    )
    db.delete(indicator)
    db.flush()
    _publish(db, actor_user_id=current_user.id, change_kind="indicator_deleted")
    db.commit()


@router.patch("/{indicator_id}", response_model=IndicatorRead)
def update_indicator(
    indicator_id: int,
    payload: IndicatorUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_scoring)),
) -> IndicatorRead:
    indicator = db.get(Indicator, indicator_id)
    if indicator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="شاخص یافت نشد")

    old_value = {
        "category": indicator.category,
        "description": indicator.description,
        "display_order": indicator.display_order,
        "is_active": indicator.is_active,
    }
    updates = payload.model_dump(exclude_unset=True)
    reason = updates.pop("wording_fix_reason", None)

    # بازنویسی متنِ شاخصی که قبلاً نمره خورده، معنای گذشته را عوض می‌کند.
    #
    # سامانه نمی‌تواند «غلط املایی را درست کردم» را از «سؤال را عوض کردم» جدا
    # کند — ولی کسی که تایپ می‌کند می‌تواند، و تنها اوست که می‌داند. پس این‌جا
    # حدس نمی‌زنیم: یا اعلام می‌کند که اصلاح نگارشی است و دلیلش ثبت می‌شود، یا
    # باید مسیر جایگزینی را برود که شناسهٔ تازه می‌سازد و تاریخ را دست نمی‌زند.
    rewrites_meaning = any(
        field in updates and updates[field] != old_value[field]
        for field in ("category", "description")
    )
    if rewrites_meaning and reason is None and _scored_count(db, indicator_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "به این شاخص قبلاً در ارزیابی‌هایی نمره داده شده است. اگر فقط نگارش را "
                "اصلاح می‌کنید، دلیلش را بنویسید تا ثبت شود؛ اگر معنای سؤال عوض می‌شود، "
                "به‌جای ویرایش، آن را با شاخص تازه «جایگزین» کنید تا مقایسه‌های گذشته "
                "معتبر بمانند."
            ),
        )

    for field, value in updates.items():
        setattr(indicator, field, value)
    db.flush()

    # فقط فعال/غیرفعال شدن، عضویت را عوض می‌کند. ویرایش متن و ترتیب نه — و
    # نسخه‌ای که بی‌دلیل جلو برود، تاریخچه را پر از ردیف‌های بی‌معنا می‌کند.
    moved = None
    if "is_active" in updates and updates["is_active"] != old_value["is_active"]:
        moved = _publish(
            db,
            actor_user_id=current_user.id,
            change_kind="indicator_activated" if updates["is_active"] else "indicator_deactivated",
        )

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="indicator_updated",
        old_value=old_value,
        new_value={
            **updates,
            **({"wording_fix_reason": reason} if reason else {}),
            **({"rebound_open_records": moved} if moved is not None else {}),
        },
    )
    db.commit()
    db.refresh(indicator)
    return IndicatorRead.model_validate(indicator).model_copy(
        update={"usage_count": _scored_count(db, indicator_id)}
    )


@router.post("/{indicator_id}/replace", response_model=IndicatorRead, status_code=status.HTTP_201_CREATED)
def replace_indicator(
    indicator_id: int,
    payload: IndicatorReplace,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_capability(Capability.manage_scoring)),
) -> Indicator:
    """شاخص را با نسخهٔ تازه‌اش عوض می‌کند: قدیمی غیرفعال، تازه با شناسهٔ خودش.

    این همان کاری است که ویرایشِ درجا *وانمود* می‌کرد انجام می‌دهد، ولی نمی‌داد.
    وقتی معنای یک شناسه هرگز عوض نشود، نموداری که «شاخص ۷» را در دو سال کنار هم
    می‌گذارد یا واقعاً یک سؤال را مقایسه می‌کند، یا اصلاً دو نقطه ندارد — و هر
    دو از مقایسهٔ خاموشِ دو سؤالِ متفاوت بهترند.

    جای شاخص قدیمی را می‌گیرد تا ترتیب فرم عوض نشود؛ HR که «همکاری» را با
    «همکاری و کار تیمی» عوض می‌کند انتظار ندارد سؤال به ته فهرست بپرد.
    """
    old = db.get(Indicator, indicator_id)
    if old is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="شاخص یافت نشد")
    if not old.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="این شاخص از قبل غیرفعال است؛ برای افزودن سؤال تازه از «شاخص جدید» استفاده کنید",
        )

    replacement = Indicator(
        section=old.section,
        category=payload.category,
        description=payload.description,
        display_order=old.display_order,
        is_active=True,
    )
    old.is_active = False
    db.add(replacement)
    db.flush()

    moved = _publish(
        db,
        actor_user_id=current_user.id,
        change_kind="indicator_replaced",
        change_note=payload.reason,
    )
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="indicator_replaced",
        old_value={"id": old.id, "category": old.category, "description": old.description},
        new_value={
            "id": replacement.id,
            "category": replacement.category,
            "description": replacement.description,
            "reason": payload.reason,
            "rebound_open_records": moved,
        },
    )
    db.commit()
    db.refresh(replacement)
    return replacement
