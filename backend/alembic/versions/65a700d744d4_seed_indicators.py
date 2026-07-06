"""seed indicators

Revision ID: 65a700d744d4
Revises: 0e25894e177a
Create Date: 2026-07-01 03:36:20.660882

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65a700d744d4'
down_revision: Union[str, None] = '0e25894e177a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


indicator_section_enum = sa.Enum(
    "general", "specialized", name="indicator_section", create_type=False
)

indicators_table = sa.table(
    "indicators",
    sa.column("section", indicator_section_enum),
    sa.column("category", sa.String),
    sa.column("description", sa.String),
    sa.column("display_order", sa.Integer),
    sa.column("is_active", sa.Boolean),
)

# بخش ۷.۱ سند پرامپت — شاخص‌های عمومی (section='general', وزن کل بخش ۶۰٪)
GENERAL_INDICATORS = [
    ("تعهد سازمانی", "رعایت ساعات کاری مصوب طبق سامانه حضور و غیاب در بازه ارزیابی"),
    ("تعهد سازمانی", "تعداد دفعات حضور/همراهی در شرایط اضطراری یا فوق‌العاده طبق درخواست ثبت‌شده واحد"),
    ("تعهد سازمانی", "تعداد موارد مستند تعامل مؤثر با سایر واحدها بر اساس گزارش یا ایمیل تأییدشده"),
    ("مسئولیت‌پذیری", "تعداد مواردی که اشتباه شناسایی و بدون انتساب به دیگران اصلاح شده طبق گزارش"),
    ("مسئولیت‌پذیری", "درصد انجام تعهدات و وظایف محوله در سررسید تعیین‌شده طبق چک‌لیست/سیستم وظایف"),
    ("انعطاف‌پذیری و یادگیری", "تعداد مواردی که بازخورد دریافتی منجر به اصلاح رفتار/خروجی شده طبق سابقه مستند"),
    ("انعطاف‌پذیری و یادگیری", "تعداد دوره/فعالیت آموزشی گذرانده‌شده مرتبط با شغل در بازه ارزیابی"),
    ("انضباط فردی", "تعداد تذکرات کتبی/شفاهی ثبت‌شده بابت عدم رعایت مقررات عمومی در بازه ارزیابی"),
    ("انضباط فردی", "تعداد موارد مستند نقض اصول اخلاق حرفه‌ای یا تعامل نامناسب با همکاران"),
    ("بهبود مستمر", "تعداد پیشنهادهای بهبود فرآیند ثبت‌شده در سامانه/مستندات واحد"),
    ("بهبود مستمر", "تعداد پیشنهادهای اجراشده یا منجر به بهینه‌سازی روش کاری با تأیید مسئول واحد"),
    ("محرمانگی", "تعداد موارد مستند نقض رازداری در مکاتبات/اسناد محرمانه طبق گزارش رسمی"),
]

# بخش ۷.۲ سند پرامپت — شاخص‌های تخصصی (section='specialized', وزن کل بخش ۴۰٪)
SPECIALIZED_INDICATORS = [
    ("کیفیت خروجی کار", "میزان انطباق خروجی با استاندارد/چک‌لیست شغلی تعریف‌شده طبق ممیزی یا بازبینی"),
    ("کیفیت خروجی کار", "تعداد موارد خطا، اصلاح یا بازگشت کار توسط واحد دریافت‌کننده در بازه ارزیابی"),
    ("دانش و مهارت تخصصی", "نتیجه ارزیابی/آزمون دانش فنی مرتبط با شغل یا نظر سرپرست مستقیم"),
    ("دانش و مهارت تخصصی", "تعداد دفعات نیاز به راهنمایی مکرر برای انجام صحیح وظایف در بازه ارزیابی"),
    ("تشخیص و حل مسئله", "تعداد مواردی که علت ریشه‌ای مشکل به‌درستی و مستند شناسایی شده"),
    ("تشخیص و حل مسئله", "تعداد راه‌حل‌های عملی ارائه‌شده که اجرا یا تأیید شده‌اند"),
    ("رعایت الزامات واحد و سازمان", "تعداد موارد مستند عدم انطباق با روش‌های اجرایی/فرآیندهای مصوب واحد"),
    ("رعایت الزامات واحد و سازمان", "تعداد موارد مستند عدم رعایت الزامات GMP/HSE یا استانداردهای کیفی مرتبط با شغل"),
]


def upgrade() -> None:
    rows = []
    for order, (category, description) in enumerate(GENERAL_INDICATORS, start=1):
        rows.append(
            {
                "section": "general",
                "category": category,
                "description": description,
                "display_order": order,
                "is_active": True,
            }
        )
    for order, (category, description) in enumerate(SPECIALIZED_INDICATORS, start=1):
        rows.append(
            {
                "section": "specialized",
                "category": category,
                "description": description,
                "display_order": order,
                "is_active": True,
            }
        )
    op.bulk_insert(indicators_table, rows)


def downgrade() -> None:
    op.execute(
        sa.delete(indicators_table).where(
            indicators_table.c.section.in_(["general", "specialized"])
        )
    )
