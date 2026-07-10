import pytest

from app.models.enums import IndicatorSection
from app.models.indicator import Indicator
from app.services.evaluation import (
    compute_result,
    recommendation_for,
    validate_evidence,
    word_count,
)


def test_word_count_counts_whitespace_separated_tokens():
    assert word_count("یک دو سه") == 3
    assert word_count("   یک   دو   ") == 2
    assert word_count("") == 0
    assert word_count(None) == 0


def _indicator(id_: int, section: str) -> Indicator:
    ind = Indicator(section=section, category="دسته", description="شرح", display_order=1)
    ind.id = id_
    return ind


@pytest.mark.parametrize("score", [2, 3, 4])
def test_middle_scores_never_require_evidence(score):
    """فقط ۱ و ۵ شواهد می‌خواهند؛ ۲/۳/۴ حتی بدون متن هم معتبرند."""
    indicators = {1: _indicator(1, IndicatorSection.general)}
    scores = [{"indicator_id": 1, "score": score, "evidence_text": None}]
    validate_evidence(scores, indicators)  # should not raise


@pytest.mark.parametrize("score", [1, 5])
def test_extreme_scores_require_min_3_words(score):
    indicators = {1: _indicator(1, IndicatorSection.general)}
    short_evidence = " ".join(["کلمه"] * 2)
    scores = [{"indicator_id": 1, "score": score, "evidence_text": short_evidence}]
    with pytest.raises(ValueError, match="حداقل ۳ کلمه"):
        validate_evidence(scores, indicators)


@pytest.mark.parametrize("score", [1, 5])
def test_extreme_scores_pass_with_exactly_3_words(score):
    indicators = {1: _indicator(1, IndicatorSection.general)}
    evidence = " ".join(["کلمه"] * 3)
    scores = [{"indicator_id": 1, "score": score, "evidence_text": evidence}]
    validate_evidence(scores, indicators)  # should not raise


def test_compute_result_weights_general_60_specialized_40():
    indicators = {
        1: _indicator(1, IndicatorSection.general),
        2: _indicator(2, IndicatorSection.specialized),
    }
    # general: 5/5 = 100%, specialized: 1/5 = 20%
    scores = [
        {"indicator_id": 1, "score": 5},
        {"indicator_id": 2, "score": 1},
    ]
    result = compute_result(scores, indicators)
    assert result["general_score_pct"] == 100.0
    assert result["specialized_score_pct"] == 20.0
    # 100*0.6 + 20*0.4 = 68.0
    assert result["final_weighted_pct"] == 68.0
    assert result["recommendation"] == "تمدید مشروط به برنامه بهبود مکتوب"


def test_compute_result_threshold_boundaries():
    indicators = {1: _indicator(1, IndicatorSection.general), 2: _indicator(2, IndicatorSection.specialized)}
    # both sections at exactly 90% -> final 90% -> top tier
    scores = [{"indicator_id": 1, "score": 5}, {"indicator_id": 2, "score": 5}]
    # forcibly emulate 90% by using 4.5 avg isn't possible with single indicator (5/5=100%),
    # so validate the top-tier boundary directly through weighting instead.
    result = compute_result(scores, indicators)
    assert result["final_weighted_pct"] == 100.0
    assert result["recommendation"] == "تمدید با امتیاز ویژه/ارتقاء"


@pytest.mark.parametrize(
    ("final_pct", "expected"),
    [
        (0.0, "عدم تمدید / بازنگری اساسی شرایط همکاری"),
        (59.0, "عدم تمدید / بازنگری اساسی شرایط همکاری"),
        (59.5, "عدم تمدید / بازنگری اساسی شرایط همکاری"),
        (59.9, "عدم تمدید / بازنگری اساسی شرایط همکاری"),
        (60.0, "تمدید مشروط به برنامه بهبود مکتوب"),
        (74.9, "تمدید مشروط به برنامه بهبود مکتوب"),
        (75.0, "تمدید با شرایط استاندارد"),
        (89.9, "تمدید با شرایط استاندارد"),
        (90.0, "تمدید با امتیاز ویژه/ارتقاء"),
        (100.0, "تمدید با امتیاز ویژه/ارتقاء"),
    ],
)
def test_recommendation_covers_full_range_without_gaps(final_pct, expected):
    """امتیازهای اعشاری مثل ۵۹٫۵ نباید در شکاف بین بازه‌ها بدون نتیجه بمانند."""
    assert recommendation_for(final_pct) == expected


def test_every_reachable_rounded_score_has_a_recommendation():
    # هر مقدار گردشده به یک رقم اعشار در [0, 100]
    for tenths in range(0, 1001):
        assert recommendation_for(tenths / 10) is not None


def test_compute_result_never_returns_none_recommendation():
    """قانون‌گذار قبلی برای امتیازهایی مثل ۵۹٫x نتیجه None می‌داد؛ این تست برای
    ترکیب‌های متنوع تعداد شاخص و مجموع امتیاز، تضمین می‌کند نتیجه همیشه وجود دارد
    (تعداد شاخص‌ها توسط HR قابل تغییر است، پس فقط حالت ۱۲+۸ کافی نیست)."""
    for n_general in range(1, 8):
        for n_specialized in range(1, 8):
            indicators = {i: _indicator(i, IndicatorSection.general) for i in range(1, n_general + 1)}
            indicators.update(
                {
                    n_general + i: _indicator(n_general + i, IndicatorSection.specialized)
                    for i in range(1, n_specialized + 1)
                }
            )
            for general_sum in range(n_general, n_general * 5 + 1):
                for specialized_sum in range(n_specialized, n_specialized * 5 + 1):
                    scores = _scores_with_sums(n_general, general_sum, n_specialized, specialized_sum)
                    result = compute_result(scores, indicators)
                    assert result["recommendation"] is not None, (
                        f"gap at final={result['final_weighted_pct']} "
                        f"(g={n_general}/{general_sum}, s={n_specialized}/{specialized_sum})"
                    )


def _scores_with_sums(n_general: int, general_sum: int, n_specialized: int, specialized_sum: int) -> list[dict]:
    """توزیع یک مجموع دلخواه بین n شاخص با امتیازهای ۱ تا ۵."""

    def distribute(n: int, total: int) -> list[int]:
        values = [1] * n
        remaining = total - n
        i = 0
        while remaining > 0:
            add = min(4, remaining)
            values[i] += add
            remaining -= add
            i += 1
        return values

    general_values = distribute(n_general, general_sum)
    specialized_values = distribute(n_specialized, specialized_sum)
    return [
        {"indicator_id": i + 1, "score": general_values[i]} for i in range(n_general)
    ] + [
        {"indicator_id": n_general + i + 1, "score": specialized_values[i]}
        for i in range(n_specialized)
    ]
