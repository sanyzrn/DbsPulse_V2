from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.constants import (
    EVIDENCE_REQUIRED_MIN_WORDS,
    EVIDENCE_REQUIRED_SCORES,
    FINAL_RESULT_THRESHOLDS,
    GENERAL_SECTION_WEIGHT,
    SPECIALIZED_SECTION_WEIGHT,
)
from app.models.indicator import Indicator


def word_count(text_value: str | None) -> int:
    if not text_value:
        return 0
    return len([token for token in text_value.split() if token])


def next_evaluation_code(db: Session) -> str:
    seq_value = db.execute(text("SELECT nextval('evaluation_code_seq')")).scalar_one()
    return f"EVL-{seq_value:04d}"


def recommendation_for(final_pct: float) -> str:
    """نتیجه پیشنهادی بر اساس امتیاز نهایی وزنی؛ بازه‌های نیم‌باز، بدون شکاف روی [0, 100]."""
    for upper_exclusive, label in FINAL_RESULT_THRESHOLDS:
        if final_pct < upper_exclusive:
            return label
    return FINAL_RESULT_THRESHOLDS[-1][1]


def validate_evidence(scores: list[dict], indicators_by_id: dict[int, Indicator]) -> None:
    """فقط امتیازهای ۱ و ۵ به شواهد عینی (حداقل ۳ کلمه) نیاز دارند؛ برای ۲/۳/۴
    اختیاری است. هرگز به اعتبارسنجی فرانت‌اند تنها اعتماد نمی‌شود."""
    violations = []
    for row in scores:
        if row["score"] not in EVIDENCE_REQUIRED_SCORES:
            continue
        count = word_count(row.get("evidence_text"))
        if count < EVIDENCE_REQUIRED_MIN_WORDS:
            indicator = indicators_by_id.get(row["indicator_id"])
            label = indicator.category if indicator else f"شاخص #{row['indicator_id']}"
            violations.append(f'«{label}» (حداقل ۳ کلمه لازم است، در حال حاضر: {count} کلمه)')

    if violations:
        raise ValueError(
            "شواهد عینی برای شاخص‌های زیر ناقص است: " + "؛ ".join(violations)
        )


def compute_result(scores: list[dict], indicators_by_id: dict[int, Indicator]) -> dict:
    general_sum = general_max = specialized_sum = specialized_max = 0
    for row in scores:
        indicator = indicators_by_id[row["indicator_id"]]
        if indicator.section.value == "general":
            general_sum += row["score"]
            general_max += 5
        else:
            specialized_sum += row["score"]
            specialized_max += 5

    general_pct = round((general_sum / general_max) * 100, 1) if general_max else 0.0
    specialized_pct = round((specialized_sum / specialized_max) * 100, 1) if specialized_max else 0.0
    final_pct = round(general_pct * GENERAL_SECTION_WEIGHT + specialized_pct * SPECIALIZED_SECTION_WEIGHT, 1)

    return {
        "general_score_pct": general_pct,
        "specialized_score_pct": specialized_pct,
        "final_weighted_pct": final_pct,
        "recommendation": recommendation_for(final_pct),
    }
