"""وضعیت پرونده‌ها در هر مرحله.

جانشین «قیف گردش‌کار» که فقط یک عدد در هر مرحله می‌داد. آن عدد می‌گفت کجا شلوغ
است ولی نه چرا — و مهم‌ترین چیزی که این‌جا سنجیده می‌شود همان تفاوت است: تعداد،
زمان توقف، و اینکه پرونده‌ها دستِ چه کسی‌اند.
"""
import pytest

from app.models.enums import EvaluationStatus
from app.services.stage_stats import STAGE_ORDER, stage_stats
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)


@pytest.fixture()
def chain(client, db_session):
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo", capabilities=[])
    sup.full_name = "مهدی روحی"
    db_session.commit()
    return {"hr": hr, "sup": sup, "dep": dep, "ceo": ceo}


def _case(client, db_session, chain, name):
    person = make_personnel(db_session, full_name=name)
    make_access(db_session, person, chain["sup"], chain["dep"], chain["ceo"])
    db_session.commit()
    record_id = client.post(
        "/api/evaluations",
        json={"subject_personnel_id": person.id},
        headers=auth_header(chain["sup"]),
    ).json()["id"]
    client.put(
        f"/api/evaluations/{record_id}/scores",
        json={"scores": full_valid_scores(active_indicators(db_session))},
        headers=auth_header(chain["sup"]),
    )
    return record_id


def _by_status(rows: list[dict]) -> dict[str, dict]:
    return {row["status"]: row for row in rows}


def test_every_stage_is_present_even_with_no_data(db_session):
    """مرحله‌ای که صفر پرونده دارد باید دیده شود.

    ردیفِ غایب و ردیفِ صفر دو معنی متفاوت دارند: اولی یعنی «نمی‌دانم»، دومی یعنی
    «هیچ‌کس آن‌جا گیر نکرده» — و دومی خبر خوبی است که باید دیده شود.
    """
    rows = stage_stats(db_session)
    assert [row["status"] for row in rows] == [status.value for status in STAGE_ORDER]
    assert all(row["active"] == 0 for row in rows)


def test_active_counts_agree_with_the_records_own_status(client, db_session, chain):
    """مرجعِ «الان کجاست» ستون `status` است، نه لاگ.

    اگر فقط از لاگ خوانده می‌شد، پرونده‌ای که مستقیم در دیتابیس ساخته شده (سید،
    مایگریشن، اصلاح دستی) هیچ ردیف گذاری ندارد و برای همیشه «پیش‌نویس» شمرده
    می‌شد — عددی که با خودِ فهرست پرونده‌ها نمی‌خواند.
    """
    a = _case(client, db_session, chain, "الف")
    _case(client, db_session, chain, "ب")
    client.post(f"/api/evaluations/{a}/submit", headers=auth_header(chain["sup"]))

    rows = _by_status(stage_stats(db_session))
    assert rows[EvaluationStatus.draft.value]["active"] == 1
    assert rows[EvaluationStatus.submitted.value]["active"] == 1


def test_a_stage_that_was_passed_counts_as_closed_not_active(client, db_session, chain):
    record_id = _case(client, db_session, chain, "ج")
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(chain["sup"]))

    draft = _by_status(stage_stats(db_session))[EvaluationStatus.draft.value]
    assert draft["total"] == 1
    assert draft["active"] == 0
    assert draft["closed"] == 1
    # میانگین توقف روی همان یک ماندنِ تمام‌شده حساب می‌شود.
    assert draft["avg_dwell_days"] is not None


def test_a_returned_case_is_counted_as_a_second_pass(client, db_session, chain):
    """پروندهٔ برگشت‌خورده دو بار در یک مرحله می‌نشیند.

    `passes` بیشتر از `total` یعنی کار به این‌جا برمی‌گردد — همان چیزی که یک عددِ
    تنها هرگز نشان نمی‌داد.
    """
    record_id = _case(client, db_session, chain, "د")
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(chain["sup"]))
    client.post(
        f"/api/evaluations/{record_id}/return",
        json={"reason": "شواهد کافی نیست"},
        headers=auth_header(chain["hr"]),
    )

    draft = _by_status(stage_stats(db_session))[EvaluationStatus.draft.value]
    assert draft["total"] == 1
    assert draft["passes"] == 2
    assert draft["active"] == 1


def test_the_breakdown_names_the_person_holding_each_case(client, db_session, chain):
    """«معاونت کند است» وقتی سه معاون داری جملهٔ بی‌مصرفی است."""
    _case(client, db_session, chain, "ه")
    draft = _by_status(stage_stats(db_session))[EvaluationStatus.draft.value]
    owners = {owner["name"]: owner for owner in draft["by_owner"]}
    assert "مهدی روحی" in owners
    assert owners["مهدی روحی"]["active"] == 1


def test_a_cancelled_case_is_not_a_stage(client, db_session, chain):
    """لغو، پایان است نه مرحله — و در آمارِ «کجا گیر کرده» جایی ندارد."""
    record_id = _case(client, db_session, chain, "و")
    client.post(
        f"/api/evaluations/{record_id}/cancel",
        json={"reason": "این پرونده لازم نبود"},
        headers=auth_header(chain["hr"]),
    )
    rows = stage_stats(db_session)
    assert all(row["status"] != "cancelled" for row in rows)
    assert sum(row["active"] for row in rows) == 0


def test_the_terminal_stage_has_no_dwell_time(client, db_session, chain):
    """«نهایی‌شده» مقصد است، نه صف. «چقدر آن‌جا مانده» پرسشِ دیگری است."""
    record_id = _case(client, db_session, chain, "ز")
    for step, actor in [
        ("submit", chain["sup"]),
        ("hr-approve", chain["hr"]),
        ("deputy-approve", chain["dep"]),
        ("ceo-finalize", chain["ceo"]),
    ]:
        assert (
            client.post(
                f"/api/evaluations/{record_id}/{step}", headers=auth_header(actor)
            ).status_code
            == 200
        ), step

    final = _by_status(stage_stats(db_session))[EvaluationStatus.finalized.value]
    assert final["active"] == 1
    assert final["avg_dwell_days"] is None
    assert final["longest_active_days"] is None


def test_the_endpoint_is_closed_to_everyone_but_hr(client, db_session, chain):
    """مدیر سامانه نمرهٔ کسی را نمی‌بیند؛ این نما هم دربارهٔ پرونده‌هاست."""
    assert (
        client.get("/api/dashboard/stage-stats", headers=auth_header(chain["sup"])).status_code
        == 403
    )
    assert (
        client.get("/api/dashboard/stage-stats", headers=auth_header(chain["hr"])).status_code
        == 200
    )
