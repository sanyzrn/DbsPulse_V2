from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_JWT_SECRET = "change-this-to-a-long-random-string"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://dbspulse:dbspulse_dev_password@localhost:5432/dbspulse"
    jwt_secret_key: str = _INSECURE_DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    # آدرس عمومی فرانت‌اند؛ برای ساخت لینک تأیید اصالت داخل QR سند PDF استفاده می‌شود
    public_base_url: str = "http://localhost:8080"

    # زمان‌بند درون‌پروسه برای اعلان‌های فعالانه (انقضای قرارداد، تأخیر مراحل).
    # پیش‌فرض خاموش تا در تست/توسعه thread پس‌زمینه بالا نیاید؛ در استقرار روشن کنید.
    enable_scheduler: bool = False
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
        if self.environment == "production" and self.jwt_secret_key == _INSECURE_DEFAULT_JWT_SECRET:
            raise RuntimeError(
                "JWT_SECRET_KEY هنوز مقدار پیش‌فرض دمو است. پیش از اجرا در محیط production "
                "یک مقدار تصادفی و طولانی برای JWT_SECRET_KEY در .env تنظیم کنید."
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
