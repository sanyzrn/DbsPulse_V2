"""مجوز «پرسنل و زنجیرهٔ ارزیابی»

تا امروز ثبت و ویرایش پرسنل فقط به نقش `hr` بسته بود. نتیجه‌اش این بود که مدیر
سامانه — همان حسابی که معاونت و مدیرعامل و مسئول واحد را می‌سازد — نمی‌توانست
پرسنلی ثبت کند تا آن حساب‌ها را به کسی وصل کند. یعنی «راه‌اندازی سازمان» نصفه
بود: حساب ساخته می‌شد و هیچ‌کس برای ارزیابی وجود نداشت.

گاردِ این صفحه‌ها حالا «یا نقش hr، یا این مجوز» است — نه فقط مجوز. اگر فقط مجوز
می‌شد، برای اینکه کارِ امروزِ منابع انسانی نشکند باید همین‌جا به همهٔ کاربران
`hr` مجوز داده می‌شد، و آن یعنی یک ردیف تازه در جدول برای هر کاربر که هیچ‌وقت
خوانده نمی‌شود. نقش، خودش پاسخ است.

پس این مایگریشن فقط مقدارِ enum را اضافه می‌کند و مجوز را به حساب‌هایی می‌دهد که
همین حالا هم «مدیر سامانه»اند — یعنی `manage_capabilities` دارند. هر حساب دیگری
که لازم داشته باشد، از صفحهٔ «مدیریت سامانه» می‌گیردش.

Revision ID: b3e7d19c4f60
Revises: a7f3c9b52d18
Create Date: 2026-08-25
"""
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "b3e7d19c4f60"
down_revision: str | None = "a7f3c9b52d18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("ALTER TYPE capability ADD VALUE IF NOT EXISTS 'manage_personnel'"))
    # مقدارِ تازهٔ enum تا پایان همین تراکنش قابل *استفاده* نیست — پس پیش از
    # اولین کوئری‌ای که به آن اشاره می‌کند، تراکنش بسته می‌شود.
    conn.execute(text("COMMIT"))

    conn.execute(
        text(
            """
            INSERT INTO user_capabilities (user_id, capability)
            SELECT DISTINCT uc.user_id, 'manage_personnel'::capability
            FROM user_capabilities uc
            WHERE uc.capability = 'manage_capabilities'
            ON CONFLICT (user_id, capability) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    # مقدارِ enum برداشته نمی‌شود: PostgreSQL راهی برای حذف یک مقدار از enum
    # ندارد جز بازساختن کل نوع، که یعنی قفل‌کردن هر جدولی که از آن استفاده
    # می‌کند. ردیف‌ها پاک می‌شوند، که همان چیزی است که رفتار را برمی‌گرداند.
    op.get_bind().execute(
        text("DELETE FROM user_capabilities WHERE capability = 'manage_personnel'")
    )
