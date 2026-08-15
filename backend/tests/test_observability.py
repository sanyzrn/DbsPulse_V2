"""P1-12 — سنجه‌ها و بررسی آمادگی.

خرابی‌های واقعی این سامانه ساکت‌اند: sweepی که دیگر اجرا نمی‌شود، رندر PDF که چون
کتابخانهٔ سیستمی نصب نیست بی‌صدا رد می‌شود، جهش ۴۰۱ها، و کانتینری که بالا آمده
ولی مایگریشن‌هایش اجرا نشده. هیچ‌کدام تا امروز از بیرون دیده نمی‌شد.
"""
import pytest
from sqlalchemy import text

from app.core.config import settings
from app.core.metrics import REGISTRY
from app.core.readiness import expected_head, last_successful_sweep, migration_state
from tests.helpers import auth_header, make_user


@pytest.fixture()
def metrics_token(monkeypatch):
    monkeypatch.setattr(settings, "metrics_token", "test-scrape-token")
    return "test-scrape-token"


def _scrape(client, token: str | None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get("/metrics", headers=headers)


# ───────────────────────────────── دسترسی /metrics


def test_metrics_does_not_exist_until_a_token_is_configured(client, monkeypatch):
    """پیش‌فرضِ «باز» غلط بود: سنجه‌ها نام مسیرها، حجم ترافیک و نرخ خطا را لو می‌دهند."""
    monkeypatch.setattr(settings, "metrics_token", "")

    assert client.get("/metrics").status_code == 404


def test_metrics_requires_the_token(client, metrics_token):
    assert _scrape(client, None).status_code == 401
    assert _scrape(client, "wrong-token").status_code == 401
    assert _scrape(client, metrics_token).status_code == 200


def test_metrics_are_served_in_prometheus_format(client, metrics_token):
    body = _scrape(client, metrics_token).text

    assert "# TYPE dbspulse_http_requests_total counter" in body
    assert "dbspulse_http_request_duration_seconds" in body


# ───────────────────────────────── کاردینالیتی


def test_paths_are_recorded_as_templates_not_values(client, db_session, metrics_token):
    """متداول‌ترین اشتباه ابزارگذاری HTTP: ثبت مقدارِ مسیر.

    اگر `/api/evaluations/42` ثبت شود، هر پرونده یک سری زمانی تازه می‌سازد و
    Prometheus بعد از چند هزار ردیف از پا درمی‌آید.
    """
    hr = make_user(db_session, "hr")
    db_session.commit()
    client.get("/api/personnel/999999", headers=auth_header(hr))

    body = _scrape(client, metrics_token).text

    assert "/api/personnel/{personnel_id}" in body
    assert "/api/personnel/999999" not in body


def test_unmatched_paths_collapse_into_one_label(client, metrics_token):
    """اسکن ۴۰۴ نباید بتواند کاردینالیتی را منفجر کند."""
    for i in range(3):
        client.get(f"/api/no-such-route-{i}")

    body = _scrape(client, metrics_token).text

    assert "<unmatched>" in body
    assert "no-such-route-1" not in body


# ───────────────────────────────── شمارنده‌های خاص


def test_a_failed_login_is_counted(client, db_session, metrics_token):
    """جهش ناگهانی این عدد یعنی حملهٔ حدس رمز."""
    before = _scrape(client, metrics_token).text

    client.post("/api/auth/login", json={"username": "ghost-user", "password": "wrong"})

    after = _scrape(client, metrics_token).text
    assert 'dbspulse_auth_failures_total{reason="bad_credentials"}' in after
    assert after != before


def test_workflow_transitions_are_counted_by_destination(client, db_session, metrics_token):
    from tests.helpers import active_indicators, full_valid_scores, make_access, make_personnel

    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    ev = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    ).json()
    client.put(
        f"/api/evaluations/{ev['id']}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(sup),
    )
    client.post(f"/api/evaluations/{ev['id']}/submit", headers=auth_header(sup))

    body = _scrape(client, metrics_token).text
    assert 'dbspulse_workflow_transitions_total{to_status="submitted"}' in body


def test_the_registry_carries_the_named_failure_modes():
    """هر سنجه یک حالتِ خرابیِ ساکت را پوشش می‌دهد؛ حذف هرکدام یعنی آن حالت دوباره نامرئی شود."""
    names = {m.name for m in REGISTRY.collect()}

    assert {
        "dbspulse_http_requests",
        "dbspulse_auth_failures",
        "dbspulse_rate_limit_rejections",
        "dbspulse_workflow_transitions",
        "dbspulse_pdf_renders",
        "dbspulse_scheduler_sweep_runs",
    } <= names


# ───────────────────────────────── آمادگی


def test_ready_reports_the_migration_head_and_stays_ready_when_it_matches(client):
    r = client.get("/api/health/ready")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    heads = body["checks"]["migration_head"]
    assert heads["expected"] is not None
    assert heads["applied"] == heads["expected"]


def test_a_migration_mismatch_makes_the_service_not_ready(client, db_session):
    """کانتینری که بالا آمده ولی مایگریشن نخورده، از بیرون سالم به‌نظر می‌رسد و روی
    اولین درخواستِ جدی خطا می‌دهد. این حالت واقعاً «آماده» نیست."""
    db_session.execute(text("UPDATE alembic_version SET version_num = 'not-the-head'"))
    db_session.flush()

    r = client.get("/api/health/ready")

    assert r.status_code == 503
    assert r.json()["status"] == "not-ready"


def test_expected_head_is_read_from_the_migration_files(db_session):
    head = expected_head()
    assert head
    expected, applied = migration_state(db_session)
    assert expected == head


def test_last_successful_sweep_ignores_runs_that_were_skipped(db_session):
    """«skipped_locked» یعنی instance دیگری قفل رهبری را داشت — نه موفقیت است نه
    شکست. اگر موفقیت حساب می‌شد، خوشه‌ای که همهٔ اعضایش رد می‌کنند برای همیشه
    «تازه» به‌نظر می‌رسید."""
    from datetime import UTC, datetime

    from app.models.scheduler_run import SchedulerRun

    assert last_successful_sweep(db_session) is None

    db_session.add(
        SchedulerRun(status="skipped_locked", trigger="scheduler", finished_at=datetime.now(UTC))
    )
    db_session.flush()
    assert last_successful_sweep(db_session) is None

    done = datetime.now(UTC)
    db_session.add(SchedulerRun(status="succeeded", trigger="scheduler", finished_at=done))
    db_session.flush()
    assert last_successful_sweep(db_session) is not None


def test_a_stale_sweep_is_reported_but_does_not_break_readiness(client):
    """برنامه با sweep کهنه هم درست سرویس می‌دهد؛ بیرون‌کشیدنش از load balancer
    اوضاع را بدتر می‌کند. گزارش می‌شود تا هشداردهنده تصمیم بگیرد."""
    r = client.get("/api/health/ready")

    assert r.status_code == 200
    assert "last_successful_sweep" in r.json()["checks"]
