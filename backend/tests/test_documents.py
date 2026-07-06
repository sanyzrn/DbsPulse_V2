"""تست‌های آرشیو PDF نهایی و تأیید اصالت عمومی (R9)."""
from sqlalchemy import select

from app.models.evaluation_document import EvaluationDocument
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


def _finalize(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session, full_name="سند رسمی", org_unit="واحد اسناد")
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    indicators = active_indicators(db_session)
    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    )
    evaluation_id = r.json()["id"]
    code = r.json()["evaluation_code"]
    client.put(
        f"/api/evaluations/{evaluation_id}/scores",
        json={"scores": full_valid_scores(indicators)},
        headers=auth_header(sup),
    )
    client.post(f"/api/evaluations/{evaluation_id}/submit", headers=auth_header(sup))
    client.post(f"/api/evaluations/{evaluation_id}/hr-approve", headers=auth_header(hr))
    client.post(f"/api/evaluations/{evaluation_id}/deputy-approve", headers=auth_header(dep))
    r = client.post(f"/api/evaluations/{evaluation_id}/ceo-finalize", headers=auth_header(ceo))
    assert r.status_code == 200
    return hr, sup, dep, ceo, evaluation_id, code


def test_finalize_archives_pdf_with_hash(client, db_session):
    hr, sup, dep, ceo, evaluation_id, code = _finalize(client, db_session)

    doc = db_session.scalar(
        select(EvaluationDocument).where(
            EvaluationDocument.evaluation_record_id == evaluation_id
        )
    )
    assert doc is not None
    assert len(doc.sha256) == 64
    assert doc.pdf_bytes[:5] == b"%PDF-"


def test_summary_pdf_serves_stored_bytes_stably(client, db_session):
    hr, sup, dep, ceo, evaluation_id, code = _finalize(client, db_session)

    r1 = client.get(f"/api/evaluations/{evaluation_id}/summary.pdf", headers=auth_header(hr))
    assert r1.status_code == 200
    assert r1.headers["content-type"] == "application/pdf"
    assert r1.content[:5] == b"%PDF-"

    # بایت‌ها باید بین دو درخواست دقیقاً یکسان باشند (byte-stable، نه رندر مجدد)
    r2 = client.get(f"/api/evaluations/{evaluation_id}/summary.pdf", headers=auth_header(hr))
    assert r2.content == r1.content


def test_public_verify_returns_authenticity_for_finalized(client, db_session):
    hr, sup, dep, ceo, evaluation_id, code = _finalize(client, db_session)

    # بدون هدر احراز هویت — endpoint عمومی است
    r = client.get(f"/api/verify/{code}")
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["evaluation_code"] == code
    assert body["subject_full_name"] == "سند رسمی"
    assert body["org_unit"] == "واحد اسناد"
    assert body["final_weighted_pct"] is not None
    assert len(body["sha256"]) == 64


def test_verify_unknown_or_unfinalized_is_404(client, db_session):
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session)
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()

    # کد ناموجود
    assert client.get("/api/verify/EVL-NON-EXISTENT").status_code == 404

    # ارزیابی باز (نهایی‌نشده) نباید قابل تأیید باشد
    r = client.post(
        "/api/evaluations", json={"subject_personnel_id": personnel.id}, headers=auth_header(sup)
    )
    code = r.json()["evaluation_code"]
    assert client.get(f"/api/verify/{code}").status_code == 404
