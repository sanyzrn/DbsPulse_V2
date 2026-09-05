"""P2-05 — سقف فیلدهای متنی آزاد، در هر سه لایه.

سه چیز جدا این‌جا سنجیده می‌شود، چون هر سه می‌توانند مستقل از هم خراب شوند:

۱. **schema** ورودی بزرگ را رد می‌کند (مسیر عادی API).
۲. **ستون** همان سقف را دارد (مسیرهایی که از schema رد نمی‌شوند: seeder، ورودی
   اکسل، SQL دستی). عدد ستون و عدد schema باید *یکی* باشند — اگر از هم جدا
   بیفتند، یکی از دو حالت بد پیش می‌آید: یا API چیزی را می‌پذیرد که دیتابیس
   ردش می‌کند (۵۰۰ به‌جای ۴۲۲)، یا سقفِ دیتابیس عملاً بی‌اثر می‌شود.
۳. **پیام** فارسی است. سقف گذاشتن بدون گفتنِ «چقدر»، ویژگی نیست؛ بن‌بست است.
"""

import pytest
from sqlalchemy import inspect

from app.core import text_limits
from app.core.validation_errors import persian_validation_message
from app.models.enums import EvaluationStatus
from app.models.evaluation import EvaluationRecord
from tests.helpers import (
    active_indicators,
    auth_header,
    full_valid_scores,
    make_access,
    make_personnel,
    make_user,
)

# نگاشت «ستون دیتابیس ← ثابتِ text_limits». هر ردیفی که این‌جا هست باید در هر دو
# جا یک عدد داشته باشد؛ همین جدول است که جلوی جداشدنشان را می‌گیرد.
COLUMN_LIMITS = [
    ("evaluation_records", "evaluator_comment", text_limits.EVALUATOR_COMMENT_MAX),
    ("evaluation_records", "self_assessment_note", text_limits.SELF_ASSESSMENT_SUMMARY_MAX),
    ("evaluation_records", "objection_reason", text_limits.OBJECTION_MAX),
    ("evaluation_records", "objection_resolution", text_limits.OBJECTION_MAX),
    ("evaluation_scores", "evidence_text", text_limits.EVIDENCE_MAX),
    ("evaluation_comments", "comment_text", text_limits.COMMENT_MAX),
    ("improvement_plans", "summary", text_limits.PLAN_SUMMARY_MAX),
    ("improvement_plan_goals", "description", text_limits.PLAN_GOAL_MAX),
    ("indicators", "category", text_limits.INDICATOR_CATEGORY_MAX),
    ("indicators", "description", text_limits.INDICATOR_DESCRIPTION_MAX),
    ("self_assessment_scores", "note", text_limits.SELF_ASSESSMENT_NOTE_MAX),
    ("contract_self_assessments", "note", text_limits.SELF_ASSESSMENT_SUMMARY_MAX),
    (
        "contract_self_assessment_scores",
        "note",
        text_limits.SELF_ASSESSMENT_NOTE_MAX,
    ),
]


@pytest.mark.parametrize(("table", "column", "expected"), COLUMN_LIMITS)
def test_the_column_carries_the_same_limit_as_the_schema(db_session, table, column, expected):
    """ستون واقعیِ دیتابیس همان سقفی را دارد که schema اعلام می‌کند."""
    columns = {c["name"]: c for c in inspect(db_session.bind).get_columns(table)}
    assert column in columns, f"{table}.{column} وجود ندارد"
    actual = getattr(columns[column]["type"], "length", None)
    assert actual == expected, f"{table}.{column} سقفش {actual} است ولی text_limits می‌گوید {expected}"


@pytest.fixture()
def open_case(db_session):
    """یک پروندهٔ باز با ارزیابِ خودش — کمترین چیزی که برای نوشتن متن لازم است."""
    hr = make_user(db_session, "hr")
    sup = make_user(db_session, "unit_supervisor")
    dep = make_user(db_session, "deputy")
    ceo = make_user(db_session, "ceo")
    personnel = make_personnel(db_session, full_name="موضوع سقف متن")
    make_access(db_session, personnel, sup, dep, ceo)
    db_session.commit()
    return {"hr": hr, "sup": sup, "dep": dep, "ceo": ceo, "personnel": personnel}


def _create(client, case):
    return client.post(
        "/api/evaluations",
        json={"subject_personnel_id": case["personnel"].id},
        headers=auth_header(case["sup"]),
    ).json()["id"]


def test_oversized_evidence_is_refused_with_a_persian_message(client, db_session, open_case):
    record_id = _create(client, open_case)
    indicators = active_indicators(db_session)
    scores = full_valid_scores(indicators)
    scores[0]["evidence_text"] = "ش" * (text_limits.EVIDENCE_MAX + 1)

    response = client.put(
        f"/api/evaluations/{record_id}/scores",
        json={"scores": scores},
        headers=auth_header(open_case["sup"]),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    # رشته، نه آرایه — وگرنه فرانت فقط «خطایی غیرمنتظره رخ داد» نشان می‌دهد
    assert isinstance(detail, str)
    assert "شواهد" in detail
    assert str(text_limits.EVIDENCE_MAX) in detail


def test_evidence_at_exactly_the_limit_is_accepted(client, db_session, open_case):
    """مرز باید *داخل* مجاز باشد. خطای off-by-one در سقف، همان اندازهٔ نبودِ سقف
    آزاردهنده است — با این تفاوت که کسی متوجهش نمی‌شود."""
    record_id = _create(client, open_case)
    indicators = active_indicators(db_session)
    scores = full_valid_scores(indicators)
    scores[0]["evidence_text"] = "ش" * text_limits.EVIDENCE_MAX

    response = client.put(
        f"/api/evaluations/{record_id}/scores",
        json={"scores": scores},
        headers=auth_header(open_case["sup"]),
    )

    assert response.status_code == 200


def test_an_oversized_comment_is_refused(client, open_case):
    record_id = _create(client, open_case)

    response = client.post(
        f"/api/evaluations/{record_id}/comments",
        json={"comment_text": "م" * (text_limits.COMMENT_MAX + 1)},
        headers=auth_header(open_case["sup"]),
    )

    assert response.status_code == 422
    assert "متن دیدگاه" in response.json()["detail"]


def test_an_oversized_return_reason_is_refused(client, db_session, open_case):
    """دلیلِ برگشت هم ورودی آزاد است و تا امروز هیچ سقفی نداشت."""
    record_id = _create(client, open_case)
    indicators = active_indicators(db_session)
    client.put(
        f"/api/evaluations/{record_id}/scores",
        json={"scores": full_valid_scores(indicators)},
        headers=auth_header(open_case["sup"]),
    )
    client.post(f"/api/evaluations/{record_id}/submit", headers=auth_header(open_case["sup"]))

    response = client.post(
        f"/api/evaluations/{record_id}/return",
        json={"reason": "د" * (text_limits.REASON_MAX + 1)},
        headers=auth_header(open_case["hr"]),
    )

    assert response.status_code == 422
    assert "دلیل" in response.json()["detail"]
    # و پرونده جابه‌جا نشده است — رد شدن باید بی‌اثر باشد، نه نیمه‌کاره
    record = db_session.get(EvaluationRecord, record_id)
    db_session.refresh(record)
    assert record.status == EvaluationStatus.submitted


def test_an_empty_required_field_says_so_in_persian(client, open_case):
    """min_length=1 از دید کاربر یعنی «خالی نگذارید»، نه «حداقل ۱ نویسه»."""
    record_id = _create(client, open_case)

    response = client.post(
        f"/api/evaluations/{record_id}/comments",
        json={"comment_text": ""},
        headers=auth_header(open_case["sup"]),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "«متن دیدگاه» را خالی نگذارید"


def test_several_problems_are_reported_together():
    """کاربر باید همهٔ ایرادها را یک‌جا ببیند، نه اینکه هر بار یکی را رفع کند و
    به بعدی بخورد."""
    message = persian_validation_message(
        [
            {"type": "missing", "loc": ("body", "title")},
            {
                "type": "string_too_long",
                "loc": ("body", "summary"),
                "ctx": {"max_length": 4000},
            },
        ]
    )
    assert "«عنوان» الزامی است" in message
    assert "«شرح» طولانی‌تر از حد مجاز است (حداکثر 4000 نویسه)" in message
    assert "؛" in message


def test_the_row_index_is_left_out_of_the_message():
    """`scores.3.score` برای کاربر «امتیاز» است. شمارهٔ ردیفِ داخلیِ آرایه چیزی به
    فهم او اضافه نمی‌کند و فقط پیام را ترسناک می‌کند."""
    message = persian_validation_message(
        [{"type": "greater_than_equal", "loc": ("body", "scores", 3, "score"), "ctx": {"ge": 1}}]
    )
    assert message == "مقدار «امتیاز» خارج از بازهٔ مجاز است (مرز: 1)"
