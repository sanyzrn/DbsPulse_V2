"""سامانه‌ای که بالا بیاید و هیچ‌کس نتواند واردش شود، بالا نیامده.

تا امروز ساختِ اولین حساب یک اسکریپت دستی بود. یعنی نصبِ تازه بدون آن اسکریپت
هیچ راهِ ورودی نداشت، و اگر تنها حساب مدیر غیرفعال می‌شد، تنها راهِ برگشت SQL
دستی روی دیتابیس بود.

این تست‌ها دو چیز را می‌سنجند: اینکه در نبودِ مدیر یکی ساخته می‌شود، و — مهم‌تر —
اینکه در حضورِ مدیر **هیچ کاری نمی‌کند**. تابعی که در هر ری‌استارت حساب بسازد،
خودش یک مشکل تازه است.
"""
import pytest

from app.models.capability import UserCapability
from app.models.enums import Capability, UserRole
from app.models.user import User
from app.services.bootstrap_admin import PASSWORD_ENV, ensure_bootstrap_admin, has_active_admin
from tests.helpers import make_user


def test_an_empty_database_gets_an_admin(db_session, monkeypatch):
    monkeypatch.delenv(PASSWORD_ENV, raising=False)
    assert has_active_admin(db_session) is False

    username = ensure_bootstrap_admin(db_session)
    assert username is not None

    admin = db_session.query(User).filter(User.username == username).one()
    # نقش `support` و نه `hr`: این حساب در زنجیرهٔ ارزیابی جایی ندارد (P0-03).
    assert admin.role is UserRole.support
    assert admin.is_active is True
    # رمزِ راه‌اندازی نباید رمزِ همیشگیِ حساب بماند.
    assert admin.must_change_password is True

    held = {
        row.capability
        for row in db_session.query(UserCapability).filter(UserCapability.user_id == admin.id)
    }
    assert held == set(Capability)


def test_it_does_nothing_when_an_admin_already_exists(db_session, monkeypatch):
    monkeypatch.delenv(PASSWORD_ENV, raising=False)
    make_user(db_session, "support", capabilities=[Capability.manage_capabilities])
    db_session.commit()

    before = db_session.query(User).count()
    assert ensure_bootstrap_admin(db_session) is None
    assert db_session.query(User).count() == before


def test_a_deactivated_admin_does_not_count(db_session, monkeypatch):
    """همان حالتِ قفل‌شدن که این کار برایش نوشته شد.

    حسابِ خاموش مجوزهایش را نگه می‌دارد ولی نمی‌تواند وارد شود — پس «مدیر دارد»
    بر پایهٔ ردیفِ مجوز، یک دروغِ آرام بود.
    """
    monkeypatch.delenv(PASSWORD_ENV, raising=False)
    locked_out = make_user(db_session, "support", capabilities=list(Capability))
    locked_out.is_active = False
    db_session.commit()

    assert has_active_admin(db_session) is False
    assert ensure_bootstrap_admin(db_session) is not None


def test_the_password_comes_from_the_environment_when_set(db_session, monkeypatch):
    from app.core.security import verify_password

    monkeypatch.setenv(PASSWORD_ENV, "Bootstrap!Pass#2026")
    username = ensure_bootstrap_admin(db_session)
    admin = db_session.query(User).filter(User.username == username).one()
    assert verify_password("Bootstrap!Pass#2026", admin.password_hash)


def test_a_taken_username_does_not_stop_it(db_session, monkeypatch):
    """حسابِ `admin`ی که از قبل هست ممکن است دقیقاً همان حسابِ خاموشی باشد که
    باعث قفل شدن شده. دست‌زدن به آن کارِ این تابع نیست."""
    monkeypatch.delenv(PASSWORD_ENV, raising=False)
    existing = make_user(db_session, "support", username="admin", capabilities=[])
    existing.is_active = False
    db_session.commit()

    username = ensure_bootstrap_admin(db_session)
    assert username == "admin2"
    # حسابِ قبلی دست‌نخورده مانده است.
    db_session.refresh(existing)
    assert existing.is_active is False


@pytest.mark.parametrize("length", [12, 24])
def test_generated_passwords_are_random(length):
    from app.services.bootstrap_admin import _generate_password

    assert _generate_password(length) != _generate_password(length)
    assert len(_generate_password(length)) == length
