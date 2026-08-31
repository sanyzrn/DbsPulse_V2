from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_module, require_role_or_capability
from app.core.security import hash_password
from app.db.session import get_db
from app.models.enums import Capability, CommentStage, PersonnelStatus, UserRole
from app.models.evaluation import EvaluationComment, EvaluationRecord
from app.models.evaluation_access import EvaluationAccess
from app.models.personnel import Personnel
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.schemas.personnel import (
    ImportRowIssue,
    PersonnelCreate,
    PersonnelCreated,
    PersonnelImportPreview,
    PersonnelImportResult,
    PersonnelPage,
    PersonnelRead,
    PersonnelUpdate,
)
from app.services.audit import log_event
from app.services.excel import build_personnel_workbook
from app.services.org_unit import known_sites, units_in_site
from app.services.personnel_import import ImportPreview, build_template, commit_import, parse_workbook
from app.services.self_assessment import OPEN_STATUSES as SELF_ASSESSMENT_OPEN_STATUSES
from app.services.self_assessment import invite as invite_to_self_assessment_service
from app.services.self_assessment import state_of as self_assessment_state
from app.services.sessions import revoke_all_for_user
from app.services.workflow import IS_OPEN_RECORD, apply_transition

router = APIRouter(prefix="/api/personnel", tags=["personnel"])

# سقف حجم فایل ورودی. بدون آن، یک فایل چندصدمگابایتی کل حافظهٔ فرایند را می‌گیرد.
MAX_IMPORT_BYTES = 5 * 1024 * 1024

# ستون‌های مجاز برای مرتب‌سازی فهرست پرسنل — با نگاشت صریح تا کاربر نتواند نام
# ستون دلخواه تزریق کند.
_PERSONNEL_SORT_COLUMNS = {
    "full_name": Personnel.full_name,
    "personnel_code": Personnel.personnel_code,
    "org_unit": Personnel.org_unit,
    "job_title": Personnel.job_title,
    "contract_end_date": Personnel.contract_end_date,
    "created_at": Personnel.created_at,
}


def _apply_personnel_filters(
    query,
    *,
    db: Session,
    q: str | None,
    status_filter: PersonnelStatus | None,
    org_unit: str | None,
    site: str | None,
    is_manager: bool | None,
):
    """فیلترهای ترکیب‌پذیر فهرست/خروجی پرسنل — یک‌جا تا list و export.xlsx رفتار
    یکسان داشته باشند."""
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            Personnel.full_name.ilike(pattern)
            | Personnel.personnel_code.ilike(pattern)
            | Personnel.job_title.ilike(pattern)
            | Personnel.org_unit.ilike(pattern)
        )
    if site:
        query = query.where(
            Personnel.org_unit.in_(
                units_in_site(list(db.scalars(select(Personnel.org_unit).distinct())), site)
            )
        )
    if status_filter is not None:
        query = query.where(Personnel.status == status_filter)
    if org_unit:
        query = query.where(Personnel.org_unit == org_unit)
    if is_manager is not None:
        query = query.where(Personnel.is_manager == is_manager)
    return query


def _personnel_order_by(sort_by: str, sort_dir: str):
    column = _PERSONNEL_SORT_COLUMNS.get(sort_by, Personnel.full_name)
    return column.desc() if sort_dir == "desc" else column.asc()

_ACCESS_COLUMN_BY_ROLE = {
    UserRole.unit_supervisor: EvaluationAccess.unit_supervisor_user_id,
    UserRole.deputy: EvaluationAccess.deputy_user_id,
    UserRole.ceo: EvaluationAccess.ceo_user_id,
}


def _can_view_personnel(db: Session, personnel_id: int, current_user: CurrentUser) -> bool:
    if current_user.role == UserRole.hr:
        return True
    access = db.scalar(
        select(EvaluationAccess).where(EvaluationAccess.personnel_id == personnel_id)
    )
    if access is not None and current_user.id in {
        access.unit_supervisor_user_id,
        access.deputy_user_id,
        access.ceo_user_id,
    }:
        return True
    involved_record = db.scalar(
        select(EvaluationRecord).where(
            EvaluationRecord.subject_personnel_id == personnel_id,
            (EvaluationRecord.unit_supervisor_user_id == current_user.id)
            | (EvaluationRecord.deputy_user_id == current_user.id)
            | (EvaluationRecord.ceo_user_id == current_user.id),
        )
    )
    return involved_record is not None


def _with_accounts(db: Session, rows: list[Personnel]) -> list[PersonnelRead]:
    """نام کاربری و وضعیت خودارزیابیِ هر پرسنل، با کوئری‌های ثابت (نه N+1).

    بدون نام کاربری، «آیا این فرد حساب دارد؟» فقط با رفتن به صفحهٔ کاربران و
    گشتن جواب داشت. بدون وضعیت خودارزیابی، دکمهٔ دعوت نمی‌دانست باید فعال باشد
    یا نه — و تنها راهش یک درخواست به‌ازای هر ردیف بود.
    """
    if not rows:
        return []
    ids = [r.id for r in rows]
    accounts = {
        personnel_id: (username, role)
        for personnel_id, username, role in db.execute(
            select(User.personnel_id, User.username, User.role).where(
                User.personnel_id.in_(ids), User.is_active.is_(True)
            )
        ).all()
    }
    open_records = {
        record.subject_personnel_id: record
        for record in db.scalars(
            select(EvaluationRecord)
            .where(
                EvaluationRecord.subject_personnel_id.in_(ids),
                EvaluationRecord.status.in_(SELF_ASSESSMENT_OPEN_STATUSES),
            )
            .order_by(EvaluationRecord.created_at)
        )
    }
    items = []
    for row in rows:
        item = PersonnelRead.model_validate(row)
        account = accounts.get(row.id)
        item.account_username = account[0] if account else None
        record = open_records.get(row.id)
        item.open_evaluation_id = record.id if record else None
        item.self_assessment_state = self_assessment_state(
            db, record, account[1] if account else None
        )
        items.append(item)
    return items


@router.get("", response_model=PersonnelPage)
def list_personnel(
    accessible_to_me: bool = False,
    q: str | None = None,
    status_filter: PersonnelStatus | None = Query(default=None, alias="status"),
    org_unit: str | None = None,
    site: str | None = None,
    is_manager: bool | None = None,
    sort_by: str = Query(default="full_name"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PersonnelPage:
    query = select(Personnel)
    # نقش‌های غیر از HR فقط پرسنلی را می‌بینند که برایشان دسترسی ارزیابی تعریف شده؛
    # HR به کل فهرست پرسنل دسترسی دارد (طبق بخش ۴ سند مشخصات).
    if current_user.role != UserRole.hr or accessible_to_me:
        column = _ACCESS_COLUMN_BY_ROLE.get(current_user.role)
        if column is None:
            return PersonnelPage(total=0, items=[])
        query = query.join(EvaluationAccess, EvaluationAccess.personnel_id == Personnel.id).where(
            column == current_user.id
        )
    query = _apply_personnel_filters(
        query,
        db=db,
        q=q,
        status_filter=status_filter,
        org_unit=org_unit,
        site=site,
        is_manager=is_manager,
    )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(
        db.scalars(
            query.order_by(_personnel_order_by(sort_by, sort_dir)).limit(limit).offset(offset)
        )
    )
    return PersonnelPage(total=total, items=_with_accounts(db, items))


# توجه: این دو مسیر ثابت باید پیش از "/{personnel_id}" تعریف شوند وگرنه FastAPI
# رشتهٔ "org-units" یا "export.xlsx" را به‌عنوان شناسهٔ عددی تفسیر می‌کند (۴۲۲).
@router.get("/org-units", response_model=list[str])
def list_org_units(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role_or_capability(UserRole.hr, Capability.manage_personnel)),
) -> list[str]:
    """واحدهای سازمانی متمایز — منبع گزینه‌های فیلتر «واحد» در فهرست‌های HR."""
    return list(
        db.scalars(select(Personnel.org_unit).distinct().order_by(Personnel.org_unit))
    )


@router.post("/{personnel_id}/invite-self-assessment", response_model=PersonnelRead)
def invite_to_self_assessment(
    personnel_id: int,
    db: Session = Depends(get_db),
    _module: None = Depends(require_module("self_assessment")),
    current_user: CurrentUser = Depends(
        require_role_or_capability(UserRole.hr, Capability.manage_personnel)
    ),
) -> PersonnelRead:
    """از کارمند بخواه خودارزیابی‌اش را انجام دهد.

    اعلان داخلی می‌سازد؛ همان اعلان — اگر ایمیل یا پیامک تنظیم شده باشد و کاربر
    آن کانال را روشن کرده باشد — از آن راه هم می‌رود. صفِ ارسال بیرونی همان صفی
    است که بقیهٔ اعلان‌های گردش‌کار از آن رد می‌شوند.

    دعوت نخست هنگام بازشدن پرونده خودکار است؛ این مسیر برای یادآوری دوباره است.
    """
    personnel = db.get(Personnel, personnel_id)
    if personnel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")

    invite_to_self_assessment_service(db, personnel, current_user.id)
    db.commit()
    db.refresh(personnel)
    return _with_accounts(db, [personnel])[0]


@router.get("/sites", response_model=list[str])
def list_sites(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role_or_capability(UserRole.hr, Capability.manage_personnel)),
) -> list[str]:
    """محل‌ها برای فیلترها و فرم ثبت پرسنل.

    تا امروز فرانت‌اند این فهرست را خودش از روی `org_unit`ها می‌ساخت — یعنی محلی
    که هنوز کسی در آن ثبت نشده بود، اصلاً وجود نداشت. حالا از یک منبع می‌آید و
    سه محلِ رسمی همیشه در آن هستند.
    """
    org_units = list(db.scalars(select(Personnel.org_unit).distinct()))
    return known_sites(org_units)


@router.get("/export.xlsx")
def export_personnel_excel(
    q: str | None = None,
    status_filter: PersonnelStatus | None = Query(default=None, alias="status"),
    org_unit: str | None = None,
    site: str | None = None,
    is_manager: bool | None = None,
    sort_by: str = Query(default="full_name"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role_or_capability(UserRole.hr, Capability.manage_personnel)),
) -> FastAPIResponse:
    """خروجی Excel از فهرست پرسنل (فقط HR) با همان فیلترها/مرتب‌سازی فهرست، تا HR
    دقیقاً همان چیزی را که روی صفحه فیلتر کرده دریافت کند."""
    query = _apply_personnel_filters(
        select(Personnel),
        db=db,
        q=q,
        status_filter=status_filter,
        org_unit=org_unit,
        site=site,
        is_manager=is_manager,
    )
    rows = list(db.scalars(query.order_by(_personnel_order_by(sort_by, sort_dir))))
    log_event(db, actor_user_id=current_user.id, event_type="personnel_excel_exported")
    db.commit()
    return FastAPIResponse(
        content=build_personnel_workbook(rows),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="personnel.xlsx"'},
    )


@router.post("", response_model=PersonnelCreated, status_code=status.HTTP_201_CREATED)
def create_personnel(
    payload: PersonnelCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role_or_capability(UserRole.hr, Capability.manage_personnel)),
) -> PersonnelCreated:
    """ساخت پرسنل، و در صورت درخواست، حساب کاربری‌اش در همان تراکنش.

    پیش از این، دسترسی دادن به یک کارمند سه کار جدا بود: ساخت پرسنل، ساخت کاربر،
    و لینک‌کردن این دو. مرحلهٔ دوم و سوم به‌سادگی فراموش می‌شد و نتیجه‌اش کارمندی
    بود که هیچ راهی برای دیدن کارنامهٔ خودش نداشت.
    """
    existing = db.scalar(select(Personnel).where(Personnel.personnel_code == payload.personnel_code))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="کد پرسنلی تکراری است"
        )

    account = payload.account
    # نام کاربری تکراری *پیش از* ساخت پرسنل بررسی می‌شود: هر دو در یک تراکنش‌اند، پس
    # خطا هیچ‌کدام را نمی‌سازد — ولی پیام خطای زودهنگام برای HR روشن‌تر است.
    if account is not None:
        duplicate = db.scalar(select(User).where(User.username == account.username))
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="نام کاربری تکراری است"
            )

    personnel = Personnel(
        **payload.model_dump(exclude={"account"}), created_by_user_id=current_user.id
    )
    db.add(personnel)
    db.flush()
    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="personnel_created",
        new_value={
            "id": personnel.id,
            "personnel_code": personnel.personnel_code,
            "full_name": personnel.full_name,
        },
    )

    account_username: str | None = None
    if account is not None:
        user = User(
            username=account.username,
            password_hash=hash_password(account.password),
            role=UserRole.employee,
            personnel_id=personnel.id,
            is_active=True,
            # رمزی که HR تعیین کرده موقتی است و باید در اولین ورود عوض شود. از فاز ۰
            # این فلگ در خود بک‌اند اعمال می‌شود، نه فقط با ریدایرکت فرانت.
            must_change_password=True,
        )
        db.add(user)
        db.flush()
        account_username = user.username
        log_event(
            db,
            actor_user_id=current_user.id,
            event_type="user_created",
            new_value={
                "id": user.id,
                "username": user.username,
                "role": user.role.value,
                "personnel_id": personnel.id,
                "created_with_personnel": True,
            },
        )

    db.commit()
    db.refresh(personnel)
    return PersonnelCreated.model_validate(personnel).model_copy(
        update={"account_username": account_username}
    )


# ───────────────────────────── ورود دسته‌ای از Excel


def _to_preview(preview: ImportPreview) -> PersonnelImportPreview:
    return PersonnelImportPreview(
        total_rows=len(preview.rows),
        valid_count=len(preview.valid),
        invalid_count=len(preview.invalid),
        accounts_to_create=sum(1 for r in preview.valid if r.username),
        rows=[
            ImportRowIssue(
                row_number=r.row_number,
                personnel_code=r.personnel_code,
                full_name=r.full_name,
                username=r.username,
                errors=r.errors,
            )
            for r in preview.rows
        ],
        file_errors=preview.file_errors,
    )


async def _read_upload(file: UploadFile) -> bytes:
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="فقط فایل Excel با پسوند .xlsx پذیرفته می‌شود",
        )
    content = await file.read()
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="حجم فایل بیش از حد مجاز است (حداکثر ۵ مگابایت)",
        )
    return content


@router.get("/import-template.xlsx")
def download_import_template(
    current_user: CurrentUser = Depends(require_role_or_capability(UserRole.hr, Capability.manage_personnel)),
) -> FastAPIResponse:
    """فایل نمونهٔ خالی — تا کاربر مجبور نباشد نام ستون‌ها را حدس بزند."""
    return FastAPIResponse(
        content=build_template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="personnel-import-template.xlsx"'},
    )


@router.post("/import/preview", response_model=PersonnelImportPreview)
async def preview_personnel_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role_or_capability(UserRole.hr, Capability.manage_personnel)),
) -> PersonnelImportPreview:
    """فقط اعتبارسنجی — هیچ چیزی نوشته نمی‌شود.

    «۲۰۰ ردیف وارد شد و ۳تایش اشتباه بود» را نمی‌شود به‌سادگی برگرداند، پس
    کاربر اول می‌بیند چه اتفاقی *قرار است* بیفتد و بعد تصمیم می‌گیرد.
    """
    return _to_preview(parse_workbook(await _read_upload(file), db))


@router.post("/import", response_model=PersonnelImportResult)
async def commit_personnel_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role_or_capability(UserRole.hr, Capability.manage_personnel)),
) -> PersonnelImportResult:
    """درج ردیف‌های معتبر، همه در یک تراکنش.

    فایل دوباره از صفر اعتبارسنجی می‌شود و نتیجهٔ همین اعتبارسنجی ملاک است، نه
    آن‌چه در پیش‌نمایش دیده شد: بین دو درخواست ممکن است کد پرسنلی یا نام کاربری
    را کس دیگری ثبت کرده باشد.

    منطقِ درج در `services/personnel_import.commit_import` است تا دو نسخه از
    «ساخت پرسنل + زنجیره + حساب» روزی از یکدیگر جدا نشوند.
    """
    preview = parse_workbook(await _read_upload(file), db)
    if preview.file_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=preview.file_errors[0]
        )

    result = commit_import(db, preview, current_user.id)

    return PersonnelImportResult(
        created_personnel=result.created_personnel,
        created_chains=result.created_chains,
        created_accounts=len(result.accounts),
        skipped_rows=result.skipped_rows,
        accounts=result.accounts,
    )


@router.get("/{personnel_id}", response_model=PersonnelRead)
def get_personnel(
    personnel_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Personnel:
    personnel = db.get(Personnel, personnel_id)
    if personnel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    if not _can_view_personnel(db, personnel_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="شما به این پرسنل دسترسی ندارید"
        )
    return personnel


def _close_out_departure(db: Session, personnel: Personnel, actor: CurrentUser) -> None:
    """کارهایی که با رفتنِ یک نفر باید انجام شوند، و تا امروز نمی‌شدند.

    **پروندهٔ باز.** تا دیروز همان‌جا می‌ماند: در صف بررسی کسی معلق، و
    یادآوری‌های SLA رویش فعال — برای کسی که دیگر در سازمان نیست. لغو می‌شود، نه
    پاک: `cancelled` یک وضعیت پایانی است و همهٔ امتیازها و کامنت‌ها سر جایشان
    می‌مانند. علتش هم به‌صورت کامنت در خودِ پرونده ثبت می‌شود تا شش ماه بعد
    معلوم باشد چرا نیمه‌کاره ماند.

    **حساب کاربری.** کسی که رفته نباید فردا بتواند وارد شود. `token_version`
    بالا می‌رود و نشست‌ها باطل می‌شوند، وگرنه توکنِ زنده‌اش تا انقضا کار می‌کرد
    — یعنی «غیرفعال کردم» تا ساعت‌ها بعد واقعاً معنایی نداشت.

    این‌جا عمداً *مسدود* نمی‌کند (برخلاف تغییر `is_manager`، که پرونده‌اش
    می‌تواند ادامه پیدا کند و فقط مسیرش عوض می‌شود). پروندهٔ کسی که رفته
    ادامه‌پذیر نیست؛ مجبورکردن HR به لغو دستی پیش از غیرفعال‌کردن، فقط دو کلیک
    اضافه برای رسیدن به همان نتیجه است.
    """
    open_evaluation = db.scalar(
        select(EvaluationRecord).where(
            EvaluationRecord.subject_personnel_id == personnel.id,
            IS_OPEN_RECORD,
        )
    )
    if open_evaluation is not None:
        reason = personnel.separation_reason.value if personnel.separation_reason else "—"
        db.add(
            EvaluationComment(
                evaluation_record_id=open_evaluation.id,
                commenter_user_id=actor.id,
                stage=CommentStage.hr_review,
                comment_text=f"لغو خودکار — پرسنل از سازمان خارج شد (علت: {reason})",
            )
        )
        log_event(
            db,
            actor_user_id=actor.id,
            event_type="evaluation_cancelled_on_separation",
            evaluation_record_id=open_evaluation.id,
            old_value={"status": open_evaluation.status.value},
            new_value={"separation_reason": reason},
        )
        apply_transition(db, open_evaluation, "cancel", actor)

    account = db.scalar(select(User).where(User.personnel_id == personnel.id))
    if account is not None and account.is_active:
        account.is_active = False
        account.token_version += 1
        revoke_all_for_user(db, account.id)
        log_event(
            db,
            actor_user_id=actor.id,
            event_type="user_deactivated_on_separation",
            old_value={"username": account.username, "is_active": True},
            new_value={"username": account.username, "is_active": False},
        )


@router.patch("/{personnel_id}", response_model=PersonnelRead)
def update_personnel(
    personnel_id: int,
    payload: PersonnelUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role_or_capability(UserRole.hr, Capability.manage_personnel)),
) -> Personnel:
    personnel = db.get(Personnel, personnel_id)
    if personnel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")

    updates = payload.model_dump(exclude_unset=True)
    if "personnel_code" in updates and updates["personnel_code"] != personnel.personnel_code:
        existing = db.scalar(
            select(Personnel).where(Personnel.personnel_code == updates["personnel_code"])
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="کد پرسنلی تکراری است"
            )

    # تغییر is_manager یک متغیر ساختاری گردش‌کار است (وجود/عدم‌وجود مرحلهٔ مسئول
    # واحد). اگر ارزیابی بازی (نهایی‌نشده) روی همین فرد در جریان باشد، آن رکورد
    # دیگر با انتظارات مسیر جدید هماهنگ نیست؛ به‌جای رفتار نامشخص، تغییر را مسدود
    # می‌کنیم تا HR اول تکلیف ارزیابی باز را روشن کند.
    if "is_manager" in updates and updates["is_manager"] != personnel.is_manager:
        open_evaluation = db.scalar(
            select(EvaluationRecord).where(
                EvaluationRecord.subject_personnel_id == personnel.id,
                IS_OPEN_RECORD,
            )
        )
        if open_evaluation is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "این پرسنل ارزیابی باز (نهایی‌نشده) دارد؛ ابتدا آن را نهایی یا "
                    "لغو کنید و سپس وضعیت «مدیر» را تغییر دهید"
                ),
            )

    # --- خروج از سازمان ---------------------------------------------------
    # سه کار که تا امروز هیچ‌کدام انجام نمی‌شد و هر سه بی‌سروصدا هزینه داشتند.
    leaving = (
        "status" in updates
        and updates["status"] is PersonnelStatus.inactive
        and personnel.status is not PersonnelStatus.inactive
    )
    if leaving and updates.get("separation_reason") is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای غیرفعال‌کردن پرسنل باید علت خروج مشخص شود",
        )
    if leaving and updates.get("separation_date") is None:
        updates["separation_date"] = date.today()
    # برگشتن به «فعال» یعنی آن خروج اتفاق نیفتاده یا برگشت خورده؛ ماندنِ علتِ
    # قدیمی روی پروندهٔ یک نفرِ شاغل، بدترین نوع دادهٔ کهنه است.
    if "status" in updates and updates["status"] is PersonnelStatus.active:
        updates["separation_date"] = None
        updates["separation_reason"] = None

    def _jsonable(value: object) -> object:
        return value.value if hasattr(value, "value") else str(value)

    old_value = {field: _jsonable(getattr(personnel, field)) for field in updates}
    for field, value in updates.items():
        setattr(personnel, field, value)

    # بررسی ترتیب تاریخ‌ها بعد از اعمال تغییرات، تا آپدیت جزئی (فقط یک تاریخ) هم پوشش داده شود
    if personnel.contract_end_date <= personnel.contract_start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ پایان قرارداد باید بعد از تاریخ شروع قرارداد باشد",
        )

    log_event(
        db,
        actor_user_id=current_user.id,
        event_type="personnel_updated",
        old_value=old_value,
        new_value={"id": personnel.id, **payload.model_dump(exclude_unset=True, mode="json")},
    )

    if leaving:
        _close_out_departure(db, personnel, current_user)

    # اگر فرد به «مدیر» تبدیل شود، دسترسی مسئول واحد قبلی (در صورت وجود) دیگر معتبر
    # نیست؛ طبق همان قانونی که در ثبت/ویرایش دسترسی اعمال می‌شود، باید خودکار پاک شود.
    if personnel.is_manager:
        access = db.scalar(
            select(EvaluationAccess).where(EvaluationAccess.personnel_id == personnel.id)
        )
        if access is not None and access.unit_supervisor_user_id is not None:
            old_supervisor_id = access.unit_supervisor_user_id
            access.unit_supervisor_user_id = None
            access.updated_by_user_id = current_user.id
            log_event(
                db,
                actor_user_id=current_user.id,
                event_type="access_supervisor_cleared_on_manager_title",
                old_value={"unit_supervisor_user_id": old_supervisor_id},
                new_value={"unit_supervisor_user_id": None, "personnel_id": personnel.id},
            )

    db.commit()
    db.refresh(personnel)
    return personnel
