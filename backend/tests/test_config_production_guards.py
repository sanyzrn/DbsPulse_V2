"""تست‌های گارد production روی تنظیمات: مثل JWT_SECRET_KEY، یک .env توسعه‌ای که
مستقیم در production کپی شود نباید بی‌صدا اجرا شود — باید در همان لحظهٔ
راه‌اندازی با خطای واضح متوقف شود."""
import pytest

from app.core.config import Settings

_VALID_SECRET = "a" * 40


def _settings(**overrides) -> Settings:
    """یک پیکربندی production که *همهٔ* گاردها را پاس می‌کند.

    هر تست فقط یک مقدار را خراب می‌کند تا معلوم شود کدام گارد شلیک کرد؛ اگر پایه
    خودش ناقص بماند، تست‌ها به‌طور تصادفی روی گارد دیگری پاس می‌شوند.
    """
    defaults = dict(
        environment="production",
        jwt_secret_key=_VALID_SECRET,
        cors_origins="https://app.example.com",
        public_base_url="https://app.example.com",
        forwarded_allow_ips="10.0.0.0/8",
    )
    defaults.update(overrides)
    return Settings(**defaults)


def test_production_with_real_https_domain_is_accepted():
    settings = _settings()
    assert settings.cors_origins_list == ["https://app.example.com"]


def test_production_rejects_a_short_jwt_secret():
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        _settings(jwt_secret_key="too-short")


def test_development_environment_allows_localhost_defaults():
    settings = Settings(environment="development")
    assert "localhost" in settings.cors_origins


@pytest.mark.parametrize(
    "cors_origins",
    [
        "http://localhost:5173",
        "http://127.0.0.1:8080",
        "https://app.example.com,http://localhost:5173",
    ],
)
def test_production_rejects_localhost_cors_origin(cors_origins):
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        _settings(cors_origins=cors_origins)


def test_production_rejects_non_https_cors_origin():
    with pytest.raises(RuntimeError, match="https"):
        _settings(cors_origins="http://app.example.com")


def test_production_rejects_localhost_public_base_url():
    with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL"):
        _settings(public_base_url="http://localhost:8080")


def test_production_rejects_non_https_public_base_url():
    with pytest.raises(RuntimeError, match="https"):
        _settings(public_base_url="http://app.example.com")


def test_production_rejects_demo_seed_flag():
    with pytest.raises(RuntimeError, match="SEED_DEMO_DATA"):
        _settings(seed_demo_data=True)


def test_demo_seed_flag_is_off_by_default():
    # پیش‌فرض باید خاموش باشد: یک محیط تازه که فقط مایگریشن خورده نباید
    # اعتبارنامهٔ منتشرشده داشته باشد.
    assert Settings(environment="development").seed_demo_data is False


def test_development_allows_demo_seed_flag():
    assert Settings(environment="development", seed_demo_data=True).seed_demo_data is True


def test_production_rejects_wildcard_trusted_proxy():
    # با «*» بک‌اند هر X-Forwarded-For ی را باور می‌کند، پس آدرسی که محدودیت نرخ
    # روی آن کلید می‌خورد توسط خود مهاجم قابل کنترل است.
    with pytest.raises(RuntimeError, match="FORWARDED_ALLOW_IPS"):
        _settings(forwarded_allow_ips="*")


def test_production_accepts_a_concrete_proxy_network():
    assert _settings(forwarded_allow_ips="172.18.0.0/16").forwarded_allow_ips == "172.18.0.0/16"


def test_development_still_allows_the_wildcard():
    # در توسعه بک‌اند مستقیم صدا زده می‌شود و پروکسی‌ای در کار نیست.
    assert Settings(environment="development").forwarded_allow_ips == "*"
