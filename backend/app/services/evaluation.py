from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.text_limits import BONUS_REASON_MIN
from app.models.indicator import Indicator
from app.services.scoring_scheme import LEGACY_RULES, Rules

#: صندلی‌های زنجیرهٔ ارزیابی به ترتیب مرحله — برای پیام‌های خطای خوانا.
_CHAIN_SEATS: tuple[tuple[str, str], ...] = (
    ("مسئول واحد", "unit_supervisor_user_id"),
    ("معاونت", "deputy_user_id"),
    ("مدیرعامل", "ceo_user_id"),
)


def inactive_seat_labels(db: Session, access) -> list[str]:
    """صندلی‌هایی از زنجیره که کاربرِ نشسته بر آن‌ها غیرفعال است.

    وضعیتِ فعال‌بودن صندلی‌ها فقط هنگام *نوشتنِ* دسترسی سنجیده می‌شد؛ حسابی که
    بعداً غیرفعال شود (جدایی، انتقال) صندلی را مرده می‌گذاشت و پرونده‌ای که
    بعداً باز می‌شد هرگز جلو نمی‌رفت — و یادآوریِ SLA هم برای حسابِ مرده
    می‌رفت (M-1 در گزارش ممیزی). بازکردنِ پرونده روی زنجیرهٔ نیمه‌مُرده ممنوع.
    """
    from app.models.evaluation_access import EvaluationAccess
    from app.models.user import User

    if not isinstance(access, EvaluationAccess):
        return []
    labels: list[str] = []
    for label, field_name in _CHAIN_SEATS:
        user_id = getattr(access, field_name)
        if user_id is None:
            continue
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            labels.append(label)
    return labels


def word_count(text_value: str | None) -> int:
    if not text_value:
        return 0
    return len([token for token in text_value.split() if token])


def next_evaluation_code(db: Session) -> str:
    seq_value = db.execute(text("SELECT nextval('evaluation_code_seq')")).scalar_one()
    return f"EVL-{seq_value:04d}"


def _fa(number: float | int) -> str:
    """عدد فارسی برای پیام‌های خطا — پیام قاعده به فارسی است، عددش هم باید باشد."""
    return f"{number:g}".translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def recommendation_for(final_pct: float, rules: Rules = LEGACY_RULES) -> str:
    """نتیجه پیشنهادی بر اساس امتیاز نهایی وزنی؛ بازه‌های نیم‌باز، بدون شکاف روی [0, 100]."""
    return rules.recommendation_for(final_pct)


def validate_evidence(
    scores: list[dict],
    indicators_by_id: dict[int, Indicator],
    rules: Rules = LEGACY_RULES,
) -> None:
    """قاعدهٔ شواهد را از طرح نمره‌دهی می‌خواند، نه از ثابت‌ها (P1-04).

    پیام‌های خطا هم از همان قاعده ساخته می‌شوند: پیش از این «حداقل ۳ کلمه» در
    متن خطا هاردکد بود، پس سازمانی که حداقل را ۵ می‌گذاشت، خطایی می‌گرفت که
    عدد اشتباه می‌گفت. هرگز به اعتبارسنجی فرانت‌اند تنها اعتماد نمی‌شود.
    """
    violations = []
    too_long = []
    for row in scores:
        count = word_count(row.get("evidence_text"))
        indicator = indicators_by_id.get(row["indicator_id"])
        label = indicator.category if indicator else f"شاخص #{row['indicator_id']}"
        # حداقل کلمات فقط برای امتیازهایی که طرح مشخص کرده اجباری است.
        if row["score"] in rules.evidence_required_scores and count < rules.evidence_min_words:
            violations.append(
                f"«{label}» (حداقل {_fa(rules.evidence_min_words)} کلمه لازم است، "
                f"در حال حاضر: {_fa(count)} کلمه)"
            )
        # سقف کلمات برای هر شواهدِ واردشده اعمال می‌شود (هر امتیازی)؛ فقط
        # اعتبارسنجی فرانت‌اند کافی نیست — کاربر می‌تواند مستقیماً API را صدا بزند.
        if count > rules.evidence_max_words:
            too_long.append(
                f"«{label}» (حداکثر {_fa(rules.evidence_max_words)} کلمه مجاز است، "
                f"در حال حاضر: {_fa(count)} کلمه)"
            )

    messages = []
    if violations:
        messages.append("شواهد عینی برای شاخص‌های زیر ناقص است: " + "؛ ".join(violations))
    if too_long:
        messages.append("شواهد عینی برای شاخص‌های زیر بیش از حد طولانی است: " + "؛ ".join(too_long))
    if messages:
        raise ValueError(" | ".join(messages))


def validate_bonus(
    bonus_points: float,
    bonus_reason: str | None,
    rules: Rules = LEGACY_RULES,
) -> None:
    """امتیاز ویژه را در برابر قواعدِ همان پرونده می‌سنجد.

    `compute_result` عدد خارج از بازه را بی‌صدا می‌بُرد تا محاسبه هرگز نتیجهٔ
    بی‌معنا ندهد؛ ولی در لحظهٔ *ثبت*، بریدن بی‌صدا بدترین کار ممکن است: ارزیاب ۸
    می‌زند، سامانه ۵ ذخیره می‌کند و چیزی نمی‌گوید. این تابع همان‌جا خطا می‌دهد.
    """
    if bonus_points < 0:
        raise ValueError("امتیاز ویژه نمی‌تواند منفی باشد")
    if bonus_points > 0 and rules.bonus_max_points <= 0:
        raise ValueError("امتیاز ویژه در طرح نمره‌دهی این پرونده فعال نیست")
    if bonus_points > rules.bonus_max_points:
        raise ValueError(
            f"امتیاز ویژه حداکثر می‌تواند {_fa(rules.bonus_max_points)} باشد "
            f"(مقدار واردشده: {_fa(bonus_points)})"
        )
    # دلیل، بخشِ اجباریِ این قابلیت است نه تزئین آن: نمره‌ای که کسی نتواند
    # توضیحش را بخواند، در سند تصمیمِ تمدید قرارداد قابل دفاع نیست.
    reason = (bonus_reason or "").strip()
    if bonus_points > 0 and len(reason) < BONUS_REASON_MIN:
        raise ValueError(
            f"توضیح امتیاز ویژه باید حداقل {_fa(BONUS_REASON_MIN)} نویسه باشد"
        )


def compute_result(
    scores: list[dict],
    indicators_by_id: dict[int, Indicator],
    rules: Rules = LEGACY_RULES,
    bonus_points: float = 0.0,
) -> dict:
    """درصد هر بخش و امتیاز نهایی وزنی، بر اساس قواعد داده‌شده.

    وزنِ هر شاخص هم از طرح می‌آید: شاخصی که وزن ندارد ۱ می‌گیرد، یعنی حالت
    پیش‌فرض دقیقاً همان میانگین سادهٔ قبلی است. با وزن‌های نابرابر، سقفِ بخش هم
    باید وزنی شود — وگرنه یک شاخصِ سنگین می‌تواند درصد را از ۱۰۰ بالاتر ببرد.
    """
    general_sum = general_max = specialized_sum = specialized_max = 0.0
    for row in scores:
        indicator = indicators_by_id[row["indicator_id"]]
        weight = rules.weight_for(row["indicator_id"])
        if indicator.section.value == "general":
            general_sum += row["score"] * weight
            general_max += 5 * weight
        else:
            specialized_sum += row["score"] * weight
            specialized_max += 5 * weight

    general_pct = round((general_sum / general_max) * 100, 1) if general_max else 0.0
    specialized_pct = round((specialized_sum / specialized_max) * 100, 1) if specialized_max else 0.0
    base_pct = round(
        general_pct * rules.general_section_weight
        + specialized_pct * rules.specialized_section_weight,
        1,
    )

    # امتیاز ویژه: کارِ خارج از شرح وظایف که در هیچ شاخصی جا نمی‌شود. دو مهار
    # دارد و هر دو لازم‌اند —
    #   ۱) سقفِ نسخهٔ طرح، تا یک ارزیاب نتواند فرم را با عددی دلخواه دور بزند؛
    #   ۲) سقفِ ۱۰۰، چون این ستون در همه‌جای سامانه «درصد» است: میانگین واحد،
    #      مقایسهٔ افراد و جدول آستانه‌ها همه روی بازهٔ [۰,۱۰۰] معنا دارند.
    # سقف دوم روی *امتیازِ اضافه‌شده* اعمال می‌شود نه روی حاصل جمع، تا این تساوی
    # همیشه برقرار بماند: «امتیاز فرم + امتیاز ویژه = امتیاز نهایی». اگر جمع را
    # می‌بریدیم، سند نهایی سه عددی نشان می‌داد که با هم جمع نمی‌شوند.
    # مقدار خامِ *ثبت‌شده* دست‌نخورده در خود پرونده می‌ماند؛ این‌جا فقط اثرش روی
    # نتیجه محاسبه می‌شود.
    applied_bonus = round(
        max(
            0.0,
            min(float(bonus_points or 0.0), rules.bonus_max_points, 100.0 - base_pct),
        ),
        2,
    )
    final_pct = round(base_pct + applied_bonus, 1)

    return {
        "general_score_pct": general_pct,
        "specialized_score_pct": specialized_pct,
        # امتیازِ فرم، پیش از امتیاز ویژه. در سند نهایی و لاگ ممیزی می‌نشیند تا
        # بعداً بشود گفت این عدد از کجا آمده، نه فقط اینکه چند شد.
        "base_weighted_pct": base_pct,
        "bonus_points": applied_bonus,
        "final_weighted_pct": final_pct,
        "recommendation": rules.recommendation_for(final_pct),
        # نسخهٔ طرحی که این نتیجه با آن حساب شده — در لاگ ممیزی و سند نهایی
        # می‌نشیند تا بعداً بشود گفت «با کدام قواعد».
        "scheme_version": rules.version,
    }
