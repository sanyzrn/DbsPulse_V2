"""P1-13 — زنجیرهٔ اجبار، یک‌بار به‌صورت کامل.

تست‌های موجود هر گارد را جدا می‌سنجند: نقش‌ها این‌جا، گذارها آن‌جا، قفل ردیفی در
فایل دیگر، زنجیرهٔ لاگ در فایل چهارم. هیچ‌کدام نمی‌گوید *همه با هم* درست کار
می‌کنند — و ایرادهای واقعیِ این‌طور سامانه‌ها معمولاً در فاصلهٔ بین دو گاردِ
سالم‌اند، نه داخل خودشان.

این فایل یک پروندهٔ واحد را از ساخت تا نهایی‌شدن می‌برد و در *هر* مرحله می‌سنجد:

  ۱. صاحب مرحله می‌تواند اقدام کند؛
  ۲. هیچ‌کس دیگر — نه نقش‌های دیگر، نه ارزیابِ مرحلهٔ قبل، نه مرحلهٔ بعد — نمی‌تواند؛
  ۳. رد آن اقدام در لاگ ممیزی می‌نشیند؛
  ۴. و در پایان، زنجیرهٔ هش لاگ هنوز سالم است.

نکتهٔ مهم بند ۴: هر گذار log_event صدا می‌زند و هر log_event حلقه‌ای به زنجیره
اضافه می‌کند. اگر ترتیب یا تراکنش‌ها جایی به‌هم بریزد، این‌جا لو می‌رود — جایی که
یک تست تک‌گارد اصلاً نگاهش نمی‌کند.
"""
import pytest

from app.models.enums import Capability, EvaluationStatus
from app.models.evaluation import EvaluationRecord
from app.services.audit import verify_chain
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


@pytest.fixture()
def cast(db_session):
    """همهٔ بازیگرهای زنجیره، به‌علاوهٔ یک «غریبه» از هر نقش برای سنجش منفی."""
    people = {
        "hr": make_user(db_session, "hr", capabilities=[Capability.view_audit_log]),
        "sup": make_user(db_session, "unit_supervisor"),
        "dep": make_user(db_session, "deputy"),
        "ceo": make_user(db_session, "ceo"),
        # هم‌نقش ولی بی‌ربط به این پرونده — «نقش درست» نباید کافی باشد
        "other_sup": make_user(db_session, "unit_supervisor"),
        "other_dep": make_user(db_session, "deputy"),
    }
    personnel = make_personnel(db_session, full_name="موضوع زنجیره")
    people["employee"] = make_user(db_session, "employee", personnel_id=personnel.id)
    make_access(db_session, personnel, people["sup"], people["dep"], people["ceo"])
    db_session.commit()
    return {**people, "personnel": personnel}


def _events(client, hr) -> list[str]:
    return [
        row["event_type"]
        for row in client.get(
            "/api/audit-log", params={"limit": 200}, headers=auth_header(hr)
        ).json()["items"]
    ]


def test_the_whole_chain_holds_from_creation_to_finalisation(client, db_session, cast):
    hr, sup, dep, ceo = cast["hr"], cast["sup"], cast["dep"], cast["ceo"]
    other_sup, other_dep = cast["other_sup"], cast["other_dep"]
    employee = cast["employee"]

    # ── ۱. ساخت: فقط ارزیابِ همین فرد
    assert (
        client.post(
            "/api/evaluations",
            json={"subject_personnel_id": cast["personnel"].id},
            headers=auth_header(other_sup),
        ).status_code
        == 403
    ), "مسئول واحدِ دیگری نباید بتواند برای این فرد پرونده باز کند"

    created = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": cast["personnel"].id},
        headers=auth_header(sup),
    )
    assert created.status_code == 201, created.text
    evaluation_id = created.json()["id"]

    # ── ۲. امتیازدهی: فقط مسئول واحدِ صاحبِ پرونده، و فقط در وضعیت draft
    scores = {"scores": full_valid_scores(active_indicators(db_session))}
    assert (
        client.put(
            f"/api/evaluations/{evaluation_id}/scores", json=scores, headers=auth_header(other_sup)
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/evaluations/{evaluation_id}/scores", json=scores, headers=auth_header(hr)
        ).status_code
        == 403
    ), "HR مالک پرونده است ولی نمره‌دهنده نیست"
    assert (
        client.put(
            f"/api/evaluations/{evaluation_id}/scores", json=scores, headers=auth_header(sup)
        ).status_code
        == 200
    )

    # ── ۳. هر مرحله: فقط صاحبِ همان مرحله، و ترتیب قابل پرش نیست
    #
    # دو لایه پشت سر هم رد می‌کنند و ترتیبشان مهم است: اول گاردِ نقش در خود روتر
    # (۴۰۳ «این بخش مال تو نیست»)، بعد گاردِ گذار در workflow (۴۰۰ «نوبتش نشده»).
    # پس نقش اشتباه همیشه ۴۰۳ می‌گیرد، حتی روی مرحلهٔ HR که کد وضعیتش ۴۰۰ است؛
    # آن ۴۰۰ فقط وقتی دیده می‌شود که کاربر واقعاً HR باشد ولی پرونده در وضعیت
    # دیگری باشد — که تست بعدی همان را می‌سنجد.
    stages = [
        ("submit", sup, [hr, dep, ceo, other_sup], 403),
        ("hr-approve", hr, [sup, dep, ceo], 403),
        ("deputy-approve", dep, [sup, hr, ceo, other_dep], 403),
        ("ceo-finalize", ceo, [sup, hr, dep], 403),
    ]
    for action, owner, outsiders, refusal in stages:
        for outsider in outsiders:
            status_code = client.post(
                f"/api/evaluations/{evaluation_id}/{action}", headers=auth_header(outsider)
            ).status_code
            assert status_code == refusal, (
                f"{outsider.role} نباید بتواند «{action}» را انجام دهد (کد {status_code})"
            )
        assert (
            client.post(
                f"/api/evaluations/{evaluation_id}/{action}", headers=auth_header(owner)
            ).status_code
            == 200
        ), f"صاحب مرحله باید بتواند «{action}» را انجام دهد"

    record = db_session.get(EvaluationRecord, evaluation_id)
    db_session.refresh(record)
    assert record.status == EvaluationStatus.finalized
    assert record.final_weighted_pct is not None
    assert record.recommendation, "نتیجهٔ نهایی باید یک توصیهٔ قراردادی داشته باشد"

    # ── ۴. پس از نهایی‌شدن، هیچ‌کس نمی‌تواند امتیاز را دست بزند
    assert (
        client.put(
            f"/api/evaluations/{evaluation_id}/scores", json=scores, headers=auth_header(sup)
        ).status_code
        == 403
    )

    # ── ۵. رد همهٔ مراحل در لاگ ممیزی هست
    logged = _events(client, hr)
    assert logged.count("status_changed") >= 4, "هر چهار گذار باید ثبت شده باشد"

    # ── ۶. و زنجیرهٔ هش هنوز سالم است
    result = verify_chain(db_session)
    assert result["ok"] is True, result
    assert result["checked"] > 0

    # ── ۷. خودِ فرد نتیجه‌اش را می‌بیند (P0-06) ولی پروندهٔ دیگران را نه
    mine = client.get("/api/me/evaluations", headers=auth_header(employee))
    assert mine.status_code == 200
    assert any(item["id"] == evaluation_id for item in mine.json()["items"])

    stranger = make_user(db_session, "employee", personnel_id=make_personnel(db_session).id)
    db_session.commit()
    theirs = client.get("/api/me/evaluations", headers=auth_header(stranger))
    assert all(item["id"] != evaluation_id for item in theirs.json()["items"]), (
        "کارمند دیگری نباید پروندهٔ این فرد را در کارنامهٔ خودش ببیند"
    )


def test_a_returned_file_re_enters_the_chain_at_the_right_stage(client, db_session, cast):
    """برگشت پرونده هم یک گذار است — نه یک در پشتی که گاردها را دور بزند."""
    hr, sup, dep, ceo = cast["hr"], cast["sup"], cast["dep"], cast["ceo"]
    scores = {"scores": full_valid_scores(active_indicators(db_session))}

    evaluation_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": cast["personnel"].id},
        headers=auth_header(sup),
    ).json()["id"]
    client.put(f"/api/evaluations/{evaluation_id}/scores", json=scores, headers=auth_header(sup))
    client.post(f"/api/evaluations/{evaluation_id}/submit", headers=auth_header(sup))

    returned = client.post(
        f"/api/evaluations/{evaluation_id}/return",
        json={"reason": "شواهد شاخص سوم کافی نیست و باید بازنویسی شود"},
        headers=auth_header(hr),
    )
    assert returned.status_code == 200

    record = db_session.get(EvaluationRecord, evaluation_id)
    db_session.refresh(record)
    assert record.status == EvaluationStatus.draft, "پرونده باید به مرحلهٔ نمره‌دهی برگردد"

    # و از این‌جا زنجیره دوباره از همان اول اجرا می‌شود — نه اینکه HR بتواند مستقیم
    # تأیید کند. کد ۴۰۰ است نه ۴۰۳: خودِ HR صاحب آن مرحله هست، ولی پرونده به draft
    # برگشته و «نوبتش نشده».
    assert (
        client.post(
            f"/api/evaluations/{evaluation_id}/hr-approve", headers=auth_header(hr)
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"/api/evaluations/{evaluation_id}/submit", headers=auth_header(sup)
        ).status_code
        == 200
    )
    client.post(f"/api/evaluations/{evaluation_id}/hr-approve", headers=auth_header(hr))
    client.post(f"/api/evaluations/{evaluation_id}/deputy-approve", headers=auth_header(dep))
    assert (
        client.post(
            f"/api/evaluations/{evaluation_id}/ceo-finalize", headers=auth_header(ceo)
        ).status_code
        == 200
    )
    assert verify_chain(db_session)["ok"] is True


def test_an_inactive_evaluator_cannot_act_even_at_their_own_stage(client, db_session, cast):
    """غیرفعال‌شدن کاربر باید بلافاصله در زنجیره اثر کند، نه فقط جلوی ورود تازه را بگیرد."""
    sup = cast["sup"]
    scores = {"scores": full_valid_scores(active_indicators(db_session))}

    evaluation_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": cast["personnel"].id},
        headers=auth_header(sup),
    ).json()["id"]
    client.put(f"/api/evaluations/{evaluation_id}/scores", json=scores, headers=auth_header(sup))

    header = auth_header(sup)
    sup.is_active = False
    db_session.commit()

    assert (
        client.post(f"/api/evaluations/{evaluation_id}/submit", headers=header).status_code == 401
    ), "توکنِ کاربر غیرفعال نباید هنوز کار کند"
    assert verify_chain(db_session)["ok"] is True
