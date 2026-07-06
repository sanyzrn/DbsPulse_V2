"""تست‌های گارد production روی تنظیمات: مثل JWT_SECRET_KEY، یک .env توسعه‌ای که
مستقیم در production کپی شود نباید بی‌صدا اجرا شود — باید در همان لحظهٔ
راه‌اندازی با خطای واضح متوقف شود."""
import pytest

from app.core.config import Settings

_VALID_SECRET = "a" * 40


def _settings(**overrides) -> Settings:
    defaults = dict(
        environment="production",
        jwt_secret_key=_VALID_SECRET,
        cors_origins="https://app.example.com",
        public_base_url="https://app.example.com",
    )
    defaults.update(overrides)
    return Settings(**defaults)


def test_production_with_real_https_domain_is_accepted():
    settings = _settings()
    assert settings.cors_origins_list == ["https://app.example.com"]


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
