from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_JWT_SECRET = "change-this-to-a-long-random-string"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    environment: str = "development"
    # پیش‌فرضِ توسعه، عمداً برگشت. نبودنش یعنی هیچ ابزاری بدونِ متغیرِ محیطی بالا
    # نمی‌آید — نه `alembic`، نه راه‌انداز، نه یک اجرای ساده برای دیدنِ خطا. گاردِ
    # واقعی پایین‌تر است: در `production` هم کلیدِ پیش‌فرض و هم کلیدِ کوتاه رد
    # می‌شوند، که همان چیزی را می‌گیرد که این تغییر می‌خواست بگیرد.
    database_url: str = "postgresql+psycopg://dbspulse:dbspulse_dev_password@localhost:5432/dbspulse"
    jwt_secret_key: str = _INSECURE_DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    # آدرس عمومی فرانت‌اند؛ برای ساخت لینک تأیید اصالت داخل QR سند PDF استفاده می‌شود
    public_base_url: str = "http://localhost:8080"

    # --- اندازهٔ استخر اتصال دیتابیس (P2-05) ----------------------------------
    # پیش‌فرض SQLAlchemy (۵ + ۱۰ سرریز) یک حدس بود، نه یک تصمیم. لحظهٔ سختِ این
    # سامانه «باز شدن یک دوره» است: ده‌ها ارزیاب هم‌زمان وارد می‌شوند و فرم
    # نمره‌دهی هر چند ثانیه پیش‌نویس ذخیره می‌کند.
    #
    # سقف واقعی از سمت Postgres می‌آید: max_connections پیش‌فرض ۱۰۰ است و باید
    # بین همهٔ کارگرها تقسیم شود. با ۴ کارگر uvicorn، (pool_size + max_overflow)
    # نباید از ۲۵ بگذرد. ۱۰+۱۰ یعنی حالت عادی ۴۰ اتصال و اوج ۸۰ — با فضای تنفس
    # برای psql و مایگریشن.
    db_pool_size: int = 10
    db_max_overflow: int = 10
    # چند ثانیه یک درخواست منتظر اتصالِ آزاد بماند. بی‌نهایت (پیش‌فرض ۳۰ ثانیه هم
    # زیاد است) یعنی زیر فشار، درخواست‌ها به‌جای شکستِ سریع تلنبار می‌شوند و
    # کاربر یک صفحهٔ یخ‌زده می‌بیند.
    db_pool_timeout_seconds: int = 10
    # اتصال‌ها پیش از آنکه firewall/pgbouncer وسطِ راه ببنددشان، خودشان بازیافت
    # می‌شوند. pool_pre_ping اتصال مرده را می‌گیرد، ولی به بهای یک رفت‌وبرگشت.
    db_pool_recycle_seconds: int = 1800

    # چند روز پس از «رؤیت» نتیجه، کارمند می‌تواند اعتراض رسمی ثبت کند. پنجرهٔ بسته
    # لازم است تا پرونده بالاخره قطعی شود، ولی باید به‌قدر کافی باز باشد که فرد
    # فرصت خواندن و فکر کردن داشته باشد.
    objection_window_days: int = 7

    # کمترین تعداد ارزیابی که یک میانگینِ تجمیعی باید داشته باشد تا نمایش داده شود.
    # «میانگین واحد» روی دو نفر، آمار گروه نیست؛ عملاً امتیاز همان دو نفر است.
    # ۱ یعنی سرکوب خاموش (فقط برای محیط‌های کوچک آزمایشی).
    min_cohort_size: int = 5

    # --- قفل حساب پس از تلاش ناموفق ورود (P0-04) -------------------------------
    # محدودیت per-IP یک حملهٔ توزیع‌شده روی یک حساب مشخص را نمی‌گیرد؛ این شمارش
    # per-username است و در دیتابیس می‌ماند (مشترک بین replica ها، مقاوم به ری‌استارت).
    login_max_failed_attempts: int = 5
    login_lockout_minutes: int = 15
    # شکست‌های قدیمی‌تر از این پنجره در قفل امروز نقشی ندارند
    login_attempt_window_minutes: int = 15

    # محل نگهداری شمارندهٔ محدودیت نرخِ per-IP. خالی = حافظهٔ درون‌پروسه، که یعنی با
    # N کارگر هر محدودیت عملاً N برابر می‌شود و با ری‌استارت صفر می‌شود. برای استقرار
    # چندنسخه‌ای یک backend مشترک بدهید (مثلاً redis://redis:6379). قفلِ حساب بالا
    # به این وابسته نیست و همیشه در دیتابیس مشترک است.
    rate_limit_storage_uri: str = ""

    # IP/شبکهٔ پروکسی‌ای که X-Forwarded-For اش قابل اعتماد است. «*» یعنی هر کلاینتی
    # می‌تواند هدر جعلی بفرستد و محدودیت نرخِ per-IP را دور بزند.
    # توکن اسکرپ سنجه‌ها (P1-12). تا وقتی تنظیم نشده، /metrics اصلاً وجود ندارد —
    # سنجه‌ها نام مسیرها، حجم ترافیک و نرخ خطا را لو می‌دهند و پیش‌فرضِ «باز» غلط است.
    metrics_token: str = ""
    forwarded_allow_ips: str = "*"

    # کاربران/پرسنل نمونهٔ دمو (hr1، sup1، … با یک رمز مشترک و منتشرشده) فقط وقتی
    # seed می‌شوند که این فلگ صراحتاً روشن باشد. پیش‌فرض خاموش است تا هیچ محیطی
    # که تازه مایگریشن خورده — از جمله production — اعتبارنامهٔ عمومی نداشته باشد.
    seed_demo_data: bool = False

    # زمان‌بند درون‌پروسه برای اعلان‌های فعالانه (انقضای قرارداد، تأخیر مراحل).
    # پیش‌فرض روشن است: با قفل رهبریِ Postgres (services/scheduler_lock.py) اجرای
    # چندنسخه‌ای امن شد، و «خاموش به‌طور پیش‌فرض» در عمل یعنی یادآوری‌ها هرگز اجرا
    # نمی‌شوند — که کل ارزش آن‌ها را از بین می‌برد. تست‌ها صراحتاً خاموشش می‌کنند.
    enable_scheduler: bool = True
    #: ساختِ خودکار حساب مدیر در بالا آمدنِ سرویس، وقتی هیچ مدیری نیست.
    #:
    #: در تست‌ها خاموش است: تست‌ها یک دیتابیس مشترک دارند و حسابی که lifespan
    #: می‌سازد و commit می‌کند، بین تست‌ها می‌ماند و فرضِ «هیچ مدیری وجود ندارد»
    #: را در تست‌های دیگر می‌شکند. خودِ این قابلیت مستقیماً تست می‌شود
    #: (`tests/test_bootstrap_admin.py`)، نه از راه بالا آمدنِ اپ.
    bootstrap_admin: bool = True
    # فاصلهٔ جاروی زمان‌بند برای اعلان‌های زمان‌محور (انقضای قرارداد، تأخیر SLA).
    # ۵ دقیقه: تعادل بین تازگی اعلان‌ها و بار سرور. اعلان‌های رویدادمحور (ثبت/تأیید/
    # برگشت/کامنت) هم‌زمان و درون همان تراکنش ساخته می‌شوند، نه با این جارو.
    scheduler_interval_seconds: int = 300
    contract_expiry_alert_days: int = 30
    sla_reminder_days: int = 3
    # چند روز مانده به تاریخ بازنگری برنامه بهبود، به HR و مسئول پیگیری یادآوری شود
    improvement_review_alert_days: int = 7
    # پنجره‌ای که در آن یک اعلانِ تکراری (همان کلید) دوباره ساخته نمی‌شود
    notification_dedup_days: int = 7

    # --- تحویل بیرونی اعلان‌ها (P1-03) ----------------------------------------
    # همه‌چیز پیش‌فرض خاموش است و باید بماند: اولین باری که کانالی روشن شود، کل
    # سازمان پیام می‌گیرد. این باید یک تصمیم آگاهانه باشد، نه اثر جانبی استقرار.
    #
    # ایمیل — SMTP استاندارد، پس با میل‌سرور داخلی و هر سرویس تراکنشی کار می‌کند.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_starttls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: int = 15

    # پیامک — شکل درخواست از همین‌جا می‌آید، پس وصل‌کردن یک سرویس تازه بدون
    # تغییر کد ممکن است. راهنمای کامل در services/channels/http_sms.py.
    sms_url: str = ""
    sms_method: str = "POST"
    sms_headers: str = ""
    sms_body: str = ""
    sms_api_key: str = ""
    #: اگر سرویس روی خطا هم ۲۰۰ می‌دهد، این رشته باید در بدنهٔ پاسخِ موفق باشد
    sms_success_contains: str = ""
    sms_timeout_seconds: int = 15

    # حالت توسعه: به‌جای ارسال واقعی، پیام‌ها در لاگ نوشته می‌شوند. کل زنجیره
    # (صف، تلاش مجدد، ارجحیت کاربر) بدون هیچ سرویس بیرونی قابل آزمودن می‌شود.
    notification_channel_console: bool = False

    delivery_batch_size: int = 50
    delivery_max_attempts: int = 5
    #: پایهٔ عقب‌نشینی نمایی؛ تلاش دوم پس از این، سومی دو برابر، و همین‌طور
    delivery_retry_base_minutes: int = 5

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _normalize_database_url_driver(self) -> "Settings":
        # سرویس‌های Postgres مدیریت‌شده (Railway/Render/Neon/...) معمولاً
        # postgres:// یا postgresql:// می‌دهند؛ درایور psycopg3 را که نصب کرده‌ایم صریح می‌کنیم.
        if self.database_url.startswith("postgres://"):
            self.database_url = "postgresql+psycopg://" + self.database_url[len("postgres://") :]
        elif self.database_url.startswith("postgresql://"):
            self.database_url = "postgresql+psycopg://" + self.database_url[len("postgresql://") :]
        return self

    @model_validator(mode="after")
    def _forbid_insecure_secret_in_production(self) -> "Settings":
        if self.environment == "production" and (
            self.jwt_secret_key == _INSECURE_DEFAULT_JWT_SECRET
            or len(self.jwt_secret_key.strip()) < 32
        ):
            raise RuntimeError(
                "JWT_SECRET_KEY برای محیط production امن نیست (مقدار پیش‌فرض یا کوتاه‌تر از "
                "۳۲ نویسه). یک مقدار تصادفی و طولانی در متغیر محیطی تنظیم کنید."
            )
        return self

    @model_validator(mode="after")
    def _forbid_demo_seed_in_production(self) -> "Settings":
        # دادهٔ دمو با رمز منتشرشده هرگز نباید در production ساخته شود. گارد دوم
        # (که حساب‌های از قبل ساخته‌شده را هم می‌گیرد) در core/startup_checks.py است.
        if self.environment == "production" and self.seed_demo_data:
            raise RuntimeError(
                "SEED_DEMO_DATA در محیط production روشن است. کاربران نمونه رمز مشترکِ "
                "منتشرشده دارند و نباید در محیط واقعی ساخته شوند؛ این مقدار را false کنید."
            )
        return self

    @model_validator(mode="after")
    def _forbid_wildcard_trusted_proxy_in_production(self) -> "Settings":
        # با «*»، uvicorn هر X-Forwarded-For ی را باور می‌کند؛ چون nginx جلویی هم
        # هدر کلاینت را به زنجیره اضافه می‌کرد، آدرسی که محدودیت نرخ روی آن کلید
        # می‌خورد عملاً توسط خود درخواست کنترل می‌شد — یعنی محدودیت با چرخاندن یک
        # هدر دور می‌خورد.
        if self.environment == "production" and self.forwarded_allow_ips.strip() == "*":
            raise RuntimeError(
                "FORWARDED_ALLOW_IPS در production نباید «*» باشد؛ آن را به IP یا شبکهٔ "
                "reverse proxy محدود کنید، وگرنه محدودیت نرخ ورود با هدر جعلی "
                "X-Forwarded-For دور زده می‌شود."
            )
        return self

    @model_validator(mode="after")
    def _forbid_insecure_cors_and_public_url_in_production(self) -> "Settings":
        # مثل گارد بالا برای JWT_SECRET_KEY: یک توسعه‌دهنده که .env.example را در
        # production کپی می‌کند ممکن است CORS_ORIGINS/PUBLIC_BASE_URL را فراموش کند
        # به‌روزرسانی کند — کوکی‌ها در production با پرچم Secure ست می‌شوند (فقط روی
        # HTTPS ارسال می‌شوند)، پس origin غیر-https یا localhost عملاً کار نمی‌کند یا
        # نشان‌دهندهٔ یک مقدار جامانده از تنظیمات توسعه است.
        if self.environment != "production":
            return self
        insecure_markers = ("localhost", "127.0.0.1", "0.0.0.0")
        for origin in self.cors_origins_list:
            lowered = origin.lower()
            if any(marker in lowered for marker in insecure_markers):
                raise RuntimeError(
                    f"CORS_ORIGINS شامل «{origin}» است که مقدار توسعه/دمو به‌نظر می‌رسد. "
                    "پیش از اجرا در محیط production آن را به دامنهٔ واقعی frontend محدود کنید."
                )
            if not lowered.startswith("https://"):
                raise RuntimeError(
                    f"CORS_ORIGINS شامل «{origin}» بدون https است؛ چون کوکی‌ها در production "
                    "با پرچم Secure ست می‌شوند (فقط روی HTTPS ارسال می‌شوند)، origin غیر-https "
                    "عملاً کار نخواهد کرد."
                )
        public_url_lower = self.public_base_url.lower()
        if any(marker in public_url_lower for marker in insecure_markers):
            raise RuntimeError(
                "PUBLIC_BASE_URL هنوز مقدار توسعه/دمو (localhost/127.0.0.1) است. پیش از اجرا "
                "در محیط production آن را به آدرس عمومی واقعی frontend تغییر دهید."
            )
        if not public_url_lower.startswith("https://"):
            raise RuntimeError(
                "PUBLIC_BASE_URL در محیط production باید https باشد (برای لینک تأیید اصالت "
                "داخل QR سند که باید از هر جا در دسترس و امن باشد)."
            )
        return self


settings = Settings()
