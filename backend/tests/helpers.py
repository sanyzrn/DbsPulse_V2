from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.services.authorization import DEFAULT_HR_CAPABILITIES
from app.models.capability import UserCapability
from app.models.enums import Capability
from app.models.evaluation_access import EvaluationAccess
from app.models.indicator import Indicator
from app.models.personnel import Personnel
from app.models.user import User

_counter = {"n": 0}


def _unique(prefix: str) -> str:
    _counter["n"] += 1
    return f"{prefix}{_counter['n']}"


def make_user(
    db: Session,
    role: str,
    username: str | None = None,
    personnel_id: int | None = None,
    capabilities: "list | None" = None,
) -> User:
    """کاربر آزمایشی.

    کاربر `hr` به‌طور پیش‌فرض همهٔ مجوزهای اداری را می‌گیرد — دقیقاً همان کاری که
    مایگریشن با حساب‌های موجود می‌کند. بدون این، هر تستی که HR داشت با گاردهای
    تازهٔ P0-03 می‌شکست و تفکیک وظایف شبیه یک رگرسیون به‌نظر می‌رسید.

    برای آزمودنِ خودِ تفکیک، `capabilities=[]` بدهید تا حساب بدون مجوز بماند.
    """
    user = User(
        username=username or _unique(f"{role}_"),
        password_hash=hash_password("Test1234!"),
        role=role,
        personnel_id=personnel_id,
        is_active=True,
    )
    db.add(user)
    db.flush()

    granted = (
        list(DEFAULT_HR_CAPABILITIES)
        if (capabilities is None and role == "hr")
        else (capabilities or [])
    )
    for capability in granted:
        db.add(UserCapability(user_id=user.id, capability=capability))
    db.flush()
    return user


def auth_header(user: User) -> dict:
    token = create_access_token(
        user.id, user.role.value if hasattr(user.role, "value") else user.role, user.token_version
    )
    return {"Authorization": f"Bearer {token}"}


def make_personnel(db: Session, job_title: str = "کارشناس", **overrides) -> Personnel:
    defaults = dict(
        # پیشوند «PT-» عمداً از «P-» جداست. شمارندهٔ _unique بین همهٔ helperها
        # مشترک است، پس با بزرگ‌شدن مجموعهٔ تست بالاخره به P-1001 می‌رسید — که
        # کد یکی از پرسنل دموی seed است — و تست‌ها بسته به ترتیب اجرا با
        # UniqueViolation می‌شکستند. با پیشوند جدا، این برخورد ممکن نیست.
        personnel_code=_unique("PT-"),
        full_name="کارمند تست",
        job_title=job_title,
        org_unit="واحد تست",
        contract_start_date=date(2025, 1, 1),
        contract_end_date=date(2026, 1, 1),
    )
    defaults.update(overrides)
    personnel = Personnel(**defaults)
    db.add(personnel)
    db.flush()
    return personnel


def make_access(
    db: Session,
    personnel: Personnel,
    supervisor: User | None,
    deputy: User,
    ceo: User,
) -> EvaluationAccess:
    access = EvaluationAccess(
        personnel_id=personnel.id,
        unit_supervisor_user_id=supervisor.id if supervisor else None,
        deputy_user_id=deputy.id,
        ceo_user_id=ceo.id,
    )
    db.add(access)
    db.flush()
    return access


def active_indicators(db: Session) -> list[Indicator]:
    return list(db.scalars(select(Indicator).where(Indicator.is_active.is_(True))))


def full_valid_scores(indicators: list[Indicator]) -> list[dict]:
    """امتیاز ۳ برای همه (بدون نیاز به شواهد) — برای عبور سریع از قانون اعتبارسنجی."""
    return [{"indicator_id": ind.id, "score": 3} for ind in indicators]
