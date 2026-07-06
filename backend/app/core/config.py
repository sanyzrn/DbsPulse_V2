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
    scheduler_interval_seconds: int = 3600
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


settings = Settings()
