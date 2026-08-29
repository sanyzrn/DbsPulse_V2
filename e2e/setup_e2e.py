"""آماده‌سازیِ محیطِ آزمونِ سرتسری:

* سازمانِ نمونه را می‌سازد (seed_demo_scenarios)
* حسابِ HRِ همکار‌دار (ai_hr / Ai-Hr-Pass-1234) با دسترسیِ همکار می‌سازد
* تنظیماتِ همکار را به سرویسِ قلابی (127.0.0.1:8100/v1) وصل می‌کند
* یک اکسلِ پرسنلِ *عمداً ناقص* کنارِ همین اسکریپت می‌گذارد تا بارگذاری شود

قبل از اجرا، DATABASE_URL (و در صورت لزوم JWT_SECRET_KEY) مثل بک‌اند export شده باشد.
"""
import sys
from io import BytesIO
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from openpyxl import Workbook

from app.core.crypto import encrypt
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.ai import AiSettings, AiUserAccess
from app.models.enums import Capability, UserRole
from app.models.user import User
from app.services.authorization import DEFAULT_HR_CAPABILITIES

HEADERS = [
    "کد پرسنلی", "نام و نام خانوادگی", "عنوان شغلی", "محل", "واحد سازمانی",
    "مدیر", "وضعیت", "شروع قرارداد", "پایان قرارداد", "نام کاربری",
    "رمز اولیه", "مسئول مستقیم", "معاونت مربوطه", "مدیرعامل",
]


def make_defective_workbook() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "پرسنل"
    ws.append(HEADERS)
    ws.append([
        "E2E-1", "نریمان صالحی", "کارشناس فروش", "دفتر مرکزی", "فروش",
        "خیر", "فعال", "۱۴۰۴/۰۴/۰۱", "", "nariman", "", "", "",
    ])
    ws.append([
        "E2E-2", "شبنم قادر", "کارشناس فروش", "دفتر مرکزی", "فروش",
        "خیر", "فعال", "۱۴۰۴/۰۵/۰۱", "۱۴۰۷/۰۵/۰۱", "shabnam", "", "", "",
    ])
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def main() -> None:
    import subprocess

    subprocess.run(
        [sys.executable, "-m", "scripts.seed_demo_scenarios"],
        cwd=BACKEND_DIR,
        check=True,
    )

    db = SessionLocal()
    try:
        from sqlalchemy import select

        user = db.scalar(select(User).where(User.username == "ai_hr"))
        if user is None:
            user = User(
                username="ai_hr",
                password_hash=hash_password("Ai-Hr-Pass-1234"),
                role=UserRole.hr,
                full_name="همکارِ آزمون",
                is_active=True,
            )
            db.add(user)
            db.flush()
            for cap in DEFAULT_HR_CAPABILITIES | {Capability.manage_personnel, Capability.view_audit_log}:
                from app.models.capability import UserCapability

                db.add(UserCapability(user_id=user.id, capability=cap, granted_by_user_id=user.id))
        else:
            user.is_active = True
            from app.models.capability import UserCapability

            have = {c.capability for c in db.scalars(select(UserCapability).where(UserCapability.user_id == user.id))}
            for cap in {Capability.manage_personnel, Capability.view_audit_log} - have:
                db.add(UserCapability(user_id=user.id, capability=cap, granted_by_user_id=user.id))

        config = db.get(AiSettings, 1)
        if config is None:
            config = AiSettings(id=1)
            db.add(config)
        config.enabled = True
        config.base_url = "http://127.0.0.1:8100/v1"
        config.model = "mock-1"
        config.api_key_encrypted = encrypt("mock-key")
        config.allow_write_actions = True
        config.allow_uploads = True
        config.max_upload_mb = 5
        config.max_tool_iterations = 8

        access = db.query(AiUserAccess).filter(AiUserAccess.user_id == user.id).one_or_none()
        if access is None:
            access = AiUserAccess(user_id=user.id, enabled=True)
            db.add(access)
        access.enabled = True
        access.allow_write_actions = True

        db.commit()
        print("ai_hr ready:", user.id)

        out = Path(__file__).resolve().parent / "e2e-personnel.xlsx"
        out.write_bytes(make_defective_workbook())
        print("defective workbook written:", out)
    finally:
        db.close()


if __name__ == "__main__":
    main()
