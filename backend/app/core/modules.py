"""فهرست ماژول‌های قابل روشن/خاموش کردن (نیمهٔ دوم P0-03).

فهرست معتبرها این‌جاست و نه در دیتابیس، عمداً: یک ردیف دیتابیس با کلیدِ اشتباه
یعنی ماژولی که هیچ کدی نمی‌شناسدش، و کاربری که سوییچی را می‌زند که هیچ اثری
ندارد. کد منبعِ حقیقتِ «چه چیزهایی وجود دارند» است؛ دیتابیس فقط می‌گوید هرکدام
روشن است یا خاموش.
"""
from dataclasses import dataclass


#: ماژول‌هایی که *نمی‌توانند* خاموش شوند این‌جا نیستند و نباید بیایند: زنجیرهٔ
#: ارزیابی، کاربران، و پرسنل هستهٔ محصول‌اند. سوییچی که بشود کل سامانه را با آن
#: خاموش کرد، سوییچ نیست.
@dataclass(frozen=True)
class ModuleDef:
    key: str
    label: str
    #: چه چیزی از دست می‌رود اگر خاموش شود — متن همان چیزی که در UI دیده می‌شود
    description: str
    default_enabled: bool


MODULES: tuple[ModuleDef, ...] = (
    ModuleDef(
        key="periods",
        label="دوره‌های ارزیابی",
        description="آغاز، پایش و بستن دوره‌های نام‌دار، و ساخت دسته‌ای ارزیابی برای یک کوهورت.",
        default_enabled=True,
    ),
    ModuleDef(
        key="improvement_plans",
        label="برنامه‌های بهبود",
        description="برنامهٔ مکتوب بهبود با اهداف و تاریخ بازنگری، برای نتیجهٔ «تمدید مشروط».",
        default_enabled=True,
    ),
    ModuleDef(
        key="self_assessment",
        label="خودارزیابی کارمند",
        description=(
            "فرد تا پیش از نهایی‌شدن پرونده، دیدگاه مستقل خودش را یک‌بار ثبت می‌کند؛ "
            "مقایسه فقط برای منابع انسانی است."
        ),
        default_enabled=True,
    ),
    ModuleDef(
        key="objections",
        label="اعتراض به نتیجه",
        description="نمایش مسیر رسمی اعتراض کارمند به نتیجهٔ نهایی؛ این گزینه با نمایش نتایج کارمند معنا پیدا می‌کند.",
        default_enabled=False,
    ),
    ModuleDef(
        key="employee_overview_cards",
        label="کارت‌های خلاصهٔ کارمند",
        description="کارت‌های آماری بالای کارنامهٔ کارمند، مانند کارهای در انتظار و وضعیت کلی.",
        default_enabled=False,
    ),
    ModuleDef(
        key="employee_evaluation_visibility",
        label="نتیجه و وضعیت پروندهٔ کارمند",
        description="نمایش نتایج نهایی ارزیابی و اینکه پروندهٔ در جریان اکنون در کدام مرحله است.",
        default_enabled=False,
    ),
    ModuleDef(
        key="employee_result_acknowledgement",
        label="ثبت رؤیت نتیجه توسط کارمند",
        description="نمایش دکمه و وضعیت «نتیجه را دیدم» در کارنامهٔ کارمند.",
        default_enabled=False,
    ),
    ModuleDef(
        key="role_analytics",
        label="تحلیل برای مسئولان و مدیران",
        description="«نمره‌دهی من» برای ارزیابان و «تحلیل سازمان» برای مدیران ارشد.",
        default_enabled=True,
    ),
    ModuleDef(
        key="outbound_notifications",
        label="اعلان بیرونی (ایمیل و پیامک)",
        description=(
            "ارسال اعلان‌های مهم بیرون از سامانه. تا وقتی سرویسی در تنظیمات سرور "
            "تعریف نشده باشد، این سوییچ اثری ندارد."
        ),
        default_enabled=True,
    ),
)

MODULE_KEYS = frozenset(module.key for module in MODULES)
MODULES_BY_KEY = {module.key: module for module in MODULES}
