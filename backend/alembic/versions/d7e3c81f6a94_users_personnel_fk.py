"""کلید خارجی گم‌شدهٔ users.personnel_id

Revision ID: d7e3c81f6a94
Revises: c4a1f0e93b57
Create Date: 2026-08-15

مدل `User` از ابتدا این کلید خارجی را اعلام کرده بود:

    ForeignKey("personnel.id", use_alter=True, name="fk_users_personnel_id")

ولی در دیتابیس هرگز ساخته نشد — جدول users با مایگریشن ساخته شد نه با
`create_all`، و مایگریشن این قید را نداشت. یعنی تا امروز مدل تضمینی می‌داد که
دیتابیس اعمالش نمی‌کرد: یک ردیف users می‌توانست به پرسنلی اشاره کند که وجود
ندارد، و تنها چیزی که جلویش را می‌گرفت بررسی‌های سطح کد در users.py بود.

این‌جا همان چیزی ساخته می‌شود که مدل از اول ادعایش را داشت. بی‌خطر است چون:

* دادهٔ یتیمی وجود ندارد (پیش از نوشتن این مایگریشن بررسی شد)؛
* هیچ مسیری پرسنل را حذف نمی‌کند — پرسنل «غیرفعال» می‌شود، پس قید هیچ جریان
  موجودی را نمی‌شکند.

use_alter در مدل یعنی SQLAlchemy این قید را جدا از CREATE TABLE می‌سازد (چرخهٔ
users ↔ personnel)، و همان دلیلی است که این‌جا هم جدا ساخته می‌شود.
"""
from alembic import op

revision = "d7e3c81f6a94"
down_revision = "c4a1f0e93b57"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_users_personnel_id",
        "users",
        "personnel",
        ["personnel_id"],
        ["id"],
        use_alter=True,
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_personnel_id", "users", type_="foreignkey")
