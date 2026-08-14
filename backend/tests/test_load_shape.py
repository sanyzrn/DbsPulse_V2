"""P2-05 — دو لبهٔ مقیاس‌پذیری که تا امروز حدس بودند، نه تصمیم.

**استخر اتصال.** پیش‌فرض SQLAlchemy (۵ + ۱۰) هرگز انتخاب نشده بود؛ فقط اتفاق
افتاده بود. این تست‌ها می‌سنجند که اعداد صریح‌اند، به موتور رسیده‌اند، و از سقفِ
واقعیِ Postgres عبور نمی‌کنند.

**رندر PDF.** تا امروز WeasyPrint *داخل* درخواستِ نهایی‌سازی مدیرعامل اجرا
می‌شد: یعنی کندشدن یک کتابخانهٔ بومیِ CPU-محور مستقیماً به «نهایی‌سازی ناموفق»
ترجمه می‌شد. حالا نهایی‌سازی اول commit می‌شود و سند بعد از ارسال پاسخ ساخته
می‌شود. دو چیز باید هم‌زمان درست باشد و این‌جا هر دو سنجیده می‌شوند: پرونده بدون
منتظر ماندن برای PDF نهایی شود، و سند بالاخره — با جارو — ساخته شود.
"""
import pytest

from app.core.config import settings
from app.db.session import engine, pool_stats
from app.models.enums import EvaluationStatus
from app.models.evaluation import EvaluationRecord
from app.models.evaluation_document import EvaluationDocument
from app.services.pdf import weasyprint_available
from app.services.scheduled import run_document_backfill_sweep
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)

# سقف پیش‌فرض max_connections در Postgres. با چند کارگر uvicorn، مجموع
# (pool_size + max_overflow) × تعداد کارگر باید زیر این بماند و برای psql و
# مایگریشن هم جا بگذارد.
POSTGRES_DEFAULT_MAX_CONNECTIONS = 100
ASSUMED_WORKERS = 4


def test_the_pool_size_is_chosen_not_inherited():
    """اگر کسی روزی تنظیمات را برداشت، این تست می‌افتد — و باید بیفتد."""
    assert engine.pool.size() == settings.db_pool_size
    assert engine.pool._max_overflow == settings.db_max_overflow


def test_the_pool_cannot_exhaust_postgres():
    """عدد استخر باید نسبت به سقف سرور معنا داشته باشد، نه فقط «بزرگ‌تر از قبل»."""
    per_worker = settings.db_pool_size + settings.db_max_overflow
    assert per_worker * ASSUMED_WORKERS < POSTGRES_DEFAULT_MAX_CONNECTIONS


def test_waiting_for_a_connection_has_a_deadline():
    """بدون timeout، زیر فشار درخواست‌ها به‌جای شکستِ سریع تلنبار می‌شوند و کاربر
    یک صفحهٔ یخ‌زده می‌بیند به‌جای یک خطای قابل‌فهم."""
    assert 0 < settings.db_pool_timeout_seconds <= 30


def test_pool_stats_are_reportable():
    stats = pool_stats()
    assert stats["capacity"] == settings.db_pool_size + settings.db_max_overflow
    assert set(stats) == {"checked_out", "available", "overflow", "capacity"}


def test_readiness_reports_pool_saturation(client):
    """اشباع استخر از بیرون شبیه «دیتابیس کند شده» است. بدون این عدد، تشخیص این
    دو از هم ممکن نیست و وقت عیب‌یابی صرف دیتابیسِ سالم می‌شود."""
    body = client.get("/api/health/ready").json()
    assert body["checks"]["db_pool"]["capacity"] > 0


@pytest.fixture()
def finalized_case(client, db_session):
    """یک پرونده که تا نهایی‌شدن پیش رفته است."""
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session, full_name="موضوع سند")
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    record_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": personnel.id},
        headers=auth_header(sup),
    ).json()["id"]
    client.put(
        f"/api/evaluations/{record_id}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(sup),
    )
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(sup))
    client.post(f"/api/evaluations/{record_id}/hr-approve", headers=auth_header(hr))
    client.post(f"/api/evaluations/{record_id}/deputy-approve", headers=auth_header(dep))
    return {"record_id": record_id, "hr": hr, "ceo": ceo}


def test_finalisation_does_not_wait_for_the_pdf(client, db_session, finalized_case, monkeypatch):
    """اگر رندر منفجر شود، نهایی‌سازی همچنان باید موفق باشد.

    این دقیقاً همان حالتی است که قبلاً بد بود: رندر روی مسیرِ درخواست بود، پس
    خرابیِ یک کتابخانهٔ جانبی، مهم‌ترین اقدام سامانه را می‌شکست.
    """

    def _explode(*args, **kwargs):
        raise RuntimeError("رندر عمداً شکست داده شد")

    monkeypatch.setattr("app.services.documents.render_evaluation_summary_pdf", _explode)

    response = client.post(
        f"/api/evaluations/{finalized_case['record_id']}/ceo-finalize",
        headers=auth_header(finalized_case["ceo"]),
    )

    assert response.status_code == 200
    record = db_session.get(EvaluationRecord, finalized_case["record_id"])
    db_session.refresh(record)
    assert record.status == EvaluationStatus.finalized
    assert record.final_snapshot is not None


@pytest.mark.skipif(not weasyprint_available(), reason="کتابخانه‌های بومی WeasyPrint نصب نیستند")
def test_the_sweep_picks_up_a_document_the_background_task_missed(
    client, db_session, finalized_case, monkeypatch
):
    """تضمینِ «بالاخره ساخته می‌شود».

    کار پس‌زمینه ممکن است اصلاً اجرا نشود — ری‌استارت پروسه، نبودِ کتابخانه، خطای
    گذرا. اگر جارو این‌ها را برنداشت، پرونده‌ای که ظاهراً نهایی شده تا ابد بدون
    سند رسمی می‌ماند و کسی خبردار نمی‌شود.
    """
    record_id = finalized_case["record_id"]

    # نهایی‌سازی با رندرِ شکسته: پرونده نهایی می‌شود، سند ساخته نمی‌شود
    monkeypatch.setattr(
        "app.services.documents.render_evaluation_summary_pdf",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("خطای گذرا")),
    )
    client.post(
        f"/api/evaluations/{record_id}/ceo-finalize",
        headers=auth_header(finalized_case["ceo"]),
    )
    db_session.expire_all()
    assert (
        db_session.query(EvaluationDocument)
        .filter_by(evaluation_record_id=record_id)
        .one_or_none()
        is None
    )

    # حالا رندر سالم است و جارو باید جامانده را بردارد
    monkeypatch.undo()
    created = run_document_backfill_sweep(db_session)

    assert created >= 1
    document = (
        db_session.query(EvaluationDocument).filter_by(evaluation_record_id=record_id).one()
    )
    assert len(document.sha256) == 64


@pytest.mark.skipif(not weasyprint_available(), reason="کتابخانه‌های بومی WeasyPrint نصب نیستند")
def test_the_backfill_sweep_is_idempotent(client, db_session, finalized_case):
    """جارو هر پنج دقیقه اجرا می‌شود؛ اگر سند موجود را دوباره بسازد، بایت‌های
    «سند حقوقیِ پایدار» هر بار عوض می‌شوند."""
    client.post(
        f"/api/evaluations/{finalized_case['record_id']}/ceo-finalize",
        headers=auth_header(finalized_case["ceo"]),
    )
    db_session.expire_all()

    built = run_document_backfill_sweep(db_session)
    first = run_document_backfill_sweep(db_session)
    second = run_document_backfill_sweep(db_session)

    assert built >= 1, "دور اول باید سند جامانده را بسازد"
    # پس از اولین ساخت، هیچ دور بعدی نباید کاری پیدا کند
    assert first == 0
    assert second == 0


def test_the_background_helper_swallows_a_missing_record():
    """کار پس‌زمینه پس از ارسال پاسخ اجرا می‌شود؛ هیچ‌کس آن‌جا نیست که خطایش را
    بگیرد. اگر پرونده در این فاصله حذف شده باشد (یا — مثل همین تست — اصلاً commit
    نشده باشد) باید بی‌صدا برگردد، نه اینکه در لاگ کارگر ردِ خطای بی‌معنا بگذارد."""
    from app.services.documents import archive_final_pdf_detached

    archive_final_pdf_detached(10**9)  # شناسه‌ای که وجود ندارد


def test_the_background_helper_swallows_a_render_failure(monkeypatch):
    """و اگر رندر بترکد هم همین‌طور — پروندهٔ نهایی‌شده نباید اثری از آن ببیند.
    جارو بعداً دوباره تلاش می‌کند."""
    from app.services import documents

    monkeypatch.setattr(
        documents,
        "render_evaluation_summary_pdf",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    documents.archive_final_pdf_detached(10**9)
