"""یک نفر، دو صندلی در یک زنجیره.

ممیزی HR ایراد گرفت که «سه نفر متفاوت» هیچ‌جا سنجیده نمی‌شود، و درست بود: از
وقتی مافوق می‌تواند در مرحلهٔ پایین‌تر بنشیند، یک نفر می‌تواند دو صندلی بگیرد و
لاگ ممیزی *دو تأیید* نشان بدهد — دو رویداد، دو مُهر، یک آدم.

ولی «هر سه باید متفاوت باشند» پاسخ درستی نبود. این فایل مرزِ درست را می‌سنجد:

* صندلیِ تکراری که بیان دیگری دارد ⇒ رد می‌شود، با پیامی که آن بیان را می‌گوید.
* صندلیِ تکراری که بیان دیگری ندارد (کسی که مستقیم زیر نظر مدیرعامل است)
  ⇒ مجاز، ولی در سند نهایی افشا می‌شود.

نیمهٔ دوم مهم‌تر است: اگر آن حالت را هم ممنوع می‌کردیم، آن افراد قابل ثبت نبودند
— همان اشتباهی که یک بار با NOT NULL بودنِ ستون معاونت مرتکب شدیم.
"""
import pytest

from app.models.evaluation import EvaluationRecord
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_personnel,
    make_user,
)


@pytest.fixture()
def people(db_session):
    return {
        "hr": make_user(db_session, "hr"),
        "sup": make_user(db_session, "unit_supervisor"),
        "dep": make_user(db_session, "deputy"),
        "ceo": make_user(db_session, "ceo", capabilities=[]),
        "person": make_personnel(db_session, full_name="موضوع صندلی"),
    }


def _set_access(client, people, **seats):
    body = {
        "unit_supervisor_user_id": None,
        "deputy_user_id": None,
        "ceo_user_id": people["ceo"].id,
        **seats,
    }
    return client.put(
        f"/api/personnel/{people['person'].id}/access",
        json=body,
        headers=auth_header(people["hr"]),
    )


# ── صندلی‌هایی که بیان درست‌تری دارند ───────────────────────────────────────

def test_supervisor_and_deputy_cannot_be_the_same_person(client, db_session, people):
    dep = people["dep"]
    response = _set_access(
        client, people, unit_supervisor_user_id=dep.id, deputy_user_id=dep.id
    )
    assert response.status_code == 400, response.text
    # پیام باید راه‌حل را بگوید، نه فقط «نمی‌شود».
    assert "خالی بگذارید" in response.json()["detail"]


def test_deputy_and_ceo_cannot_be_the_same_person(client, db_session, people):
    ceo = people["ceo"]
    response = _set_access(
        client, people, unit_supervisor_user_id=people["sup"].id, deputy_user_id=ceo.id
    )
    assert response.status_code == 400, response.text
    assert "خالی بگذارید" in response.json()["detail"]


# ── صندلی‌ای که بیان دیگری ندارد ───────────────────────────────────────────

def test_the_ceo_may_be_the_direct_supervisor(client, db_session, people):
    """کسی که مستقیم زیر نظر مدیرعامل است، هیچ راه ثبت دیگری ندارد."""
    ceo = people["ceo"]
    response = _set_access(client, people, unit_supervisor_user_id=ceo.id)
    assert response.status_code == 200, response.text


def test_that_case_is_disclosed_on_the_record_and_in_the_document(client, db_session, people):
    """مجاز بودن یعنی «قابل ثبت»، نه «قابل کتمان».

    بدون این افشا، لاگ دو تأیید نشان می‌داد و خواننده‌اش دو بررسی مستقل می‌فهمید.
    """
    from app.services.snapshot import build_final_snapshot

    ceo, hr = people["ceo"], people["hr"]
    _set_access(client, people, unit_supervisor_user_id=ceo.id)

    record_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": people["person"].id},
        headers=auth_header(ceo),
    ).json()["id"]
    client.put(
        f"/api/evaluations/{record_id}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(ceo),
    )
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(ceo))
    client.post(f"/api/evaluations/{record_id}/hr-approve", headers=auth_header(hr))
    result = client.post(
        f"/api/evaluations/{record_id}/ceo-finalize", headers=auth_header(ceo)
    )
    assert result.status_code == 200, result.text
    assert result.json()["single_decider"] is True

    record = db_session.get(EvaluationRecord, record_id)
    db_session.refresh(record)
    assert build_final_snapshot(db_session, record)["single_decider"] is True


def test_an_ordinary_chain_is_not_flagged(client, db_session, people):
    """پرچمی که همیشه روشن باشد هیچ‌چیز نمی‌گوید."""
    _set_access(
        client,
        people,
        unit_supervisor_user_id=people["sup"].id,
        deputy_user_id=people["dep"].id,
    )
    record = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": people["person"].id},
        headers=auth_header(people["sup"]),
    ).json()
    assert record["single_decider"] is False


# ── مسیر جابه‌جایی مسئول مرحله ─────────────────────────────────────────────

def test_reassignment_cannot_smuggle_a_redundant_seat_in(client, db_session, people):
    """زنجیره درست ساخته می‌شود، بعد یک جابه‌جایی دو صندلی را به یک نفر می‌دهد.

    بدون گارد روی این مسیر، قید بالا فقط یک سرعت‌گیر بود.
    """
    sup, dep, hr = people["sup"], people["dep"], people["hr"]
    _set_access(client, people, unit_supervisor_user_id=sup.id, deputy_user_id=dep.id)
    record_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": people["person"].id},
        headers=auth_header(sup),
    ).json()["id"]

    response = client.post(
        f"/api/evaluations/{record_id}/reassign",
        json={
            "stage_field": "deputy_user_id",
            "new_user_id": sup.id,
            "reason": "تلاش برای دادن دو صندلی به یک نفر",
        },
        headers=auth_header(hr),
    )
    assert response.status_code == 400, response.text


# ── و همان قاعده در مسیر ایمپورت ───────────────────────────────────────────

def test_the_importer_rejects_a_redundant_seat(db_session):
    """در فایل واقعی، تکرارِ یک نام در دو ستون تقریباً همیشه یعنی «مسئول واحد ندارد»."""
    from app.services.personnel_import import parse_workbook
    from tests.test_import_chain import _row, _workbook

    dep = make_user(db_session, "deputy", username="dep_seat", capabilities=[])
    dep.full_name = "معاون تکراری"
    db_session.commit()

    preview = parse_workbook(
        _workbook(
            [
                _row(
                    "SEAT-1",
                    "کارمند صندلی",
                    **{"مسئول مستقیم": "معاون تکراری", "معاونت مربوطه": "معاون تکراری"},
                )
            ]
        ),
        db_session,
    )
    row = preview.rows[0]
    assert any("یک نفرند" in error for error in row.errors), row.errors
