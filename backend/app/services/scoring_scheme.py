"""خواندن، ساختن و فعال‌کردن طرح نمره‌دهی (P1-04).

`Rules` — یک ساختار ساده و تغییرناپذیر — تنها چیزی است که موتور محاسبه می‌بیند.
منبعش می‌تواند یک ردیف دیتابیس باشد یا ثابت‌های قدیمی؛ محاسبه فرقش را نمی‌فهمد
و لازم هم نیست بفهمد. این جداسازی چیزی است که اجازه می‌دهد «پیش‌نمایش» یک طرحِ
هنوز-فعال‌نشده دقیقاً همان کدِ محاسبهٔ واقعی را اجرا کند، نه یک کپیِ موازی که
دیر یا زود با اصل فرق می‌کند.
"""
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import constants
from app.models.enums import SchemeStatus
from app.models.scoring_scheme import ScoringScheme


@dataclass(frozen=True)
class Rules:
    """قواعد نمره‌دهی، مستقل از این‌که از کجا آمده‌اند."""

    general_section_weight: float
    specialized_section_weight: float
    evidence_required_scores: tuple[int, ...]
    evidence_min_words: int
    evidence_max_words: int
    #: [(سقف بازه — exclusive, برچسب), ...] — مرتب و پیوسته
    thresholds: tuple[tuple[float, str], ...]
    #: {indicator_id: weight}؛ شاخصِ غایب وزن ۱ می‌گیرد
    indicator_weights: dict[int, float]
    #: شمارهٔ نسخه، یا None وقتی از ثابت‌ها آمده (فقط مسیر بازگشتی)
    version: int | None = None

    def weight_for(self, indicator_id: int) -> float:
        return self.indicator_weights.get(indicator_id, 1.0)

    def recommendation_for(self, final_pct: float) -> str:
        for upper_exclusive, label in self.thresholds:
            if final_pct < upper_exclusive:
                return label
        return self.thresholds[-1][1]


#: قواعدِ پیش از P1-04، به‌عنوان مبنای نسخهٔ ۱ و به‌عنوان مسیر بازگشتی برای
#: پرونده‌هایی که به هر دلیل طرحی ندارند. عمداً از خودِ constants خوانده می‌شود
#: تا اگر کسی آن فایل را دست بزند، نسخهٔ ۱ همچنان بازتابش باشد.
LEGACY_RULES = Rules(
    general_section_weight=constants.GENERAL_SECTION_WEIGHT,
    specialized_section_weight=constants.SPECIALIZED_SECTION_WEIGHT,
    evidence_required_scores=tuple(constants.EVIDENCE_REQUIRED_SCORES),
    evidence_min_words=constants.EVIDENCE_REQUIRED_MIN_WORDS,
    evidence_max_words=constants.EVIDENCE_MAX_WORDS,
    thresholds=tuple((float(u), label) for u, label in constants.FINAL_RESULT_THRESHOLDS),
    indicator_weights={},
)


def rules_from(scheme: ScoringScheme) -> Rules:
    return Rules(
        general_section_weight=float(scheme.general_section_weight),
        specialized_section_weight=float(scheme.specialized_section_weight),
        evidence_required_scores=tuple(int(s) for s in scheme.evidence_required_scores),
        evidence_min_words=scheme.evidence_min_words,
        evidence_max_words=scheme.evidence_max_words,
        thresholds=tuple(
            (float(row["upper_exclusive"]), row["label"]) for row in scheme.thresholds
        ),
        # کلیدهای JSONB رشته‌اند؛ برگرداندنشان به int این‌جا انجام می‌شود تا بقیهٔ
        # کد لازم نباشد بداند این داده از JSON آمده.
        indicator_weights={int(k): float(v) for k, v in (scheme.indicator_weights or {}).items()},
        version=scheme.version,
    )


def active_scheme(db: Session) -> ScoringScheme | None:
    return db.scalar(select(ScoringScheme).where(ScoringScheme.status == SchemeStatus.active))


def rules_for_record(db: Session, record) -> Rules:
    """قواعدی که این پرونده باید با آن‌ها محاسبه شود.

    نکتهٔ کل این ماژول همین یک تابع است: از `record.scoring_scheme_id` می‌خواند،
    نه از طرح فعال. پرونده‌ای که پارسال ساخته شده با قواعد پارسال حساب می‌شود،
    حتی اگر امروز HR وزن‌ها را عوض کرده باشد.
    """
    if record.scoring_scheme_id is not None:
        scheme = db.get(ScoringScheme, record.scoring_scheme_id)
        if scheme is not None:
            return rules_from(scheme)
    # پروندهٔ بی‌مهر: نباید پیش بیاید (مایگریشن همه را مهر زده و ساخت جدید هم
    # مهر می‌زند)، ولی محاسبه‌ای که به‌خاطر دادهٔ ناقص ۵۰۰ بدهد بدتر از محاسبه‌ای
    # است که به رفتار قبلی برگردد.
    scheme = active_scheme(db)
    return rules_from(scheme) if scheme is not None else LEGACY_RULES


def current_rules(db: Session) -> Rules:
    """قواعد طرح فعال — برای پرونده‌های *جدید* و برای نمایش در UI."""
    scheme = active_scheme(db)
    return rules_from(scheme) if scheme is not None else LEGACY_RULES


def next_version(db: Session) -> int:
    return (db.scalar(select(func.max(ScoringScheme.version))) or 0) + 1


def activate(db: Session, scheme: ScoringScheme, *, actor_user_id: int) -> None:
    """طرح را فعال و طرح فعلی را بازنشسته می‌کند.

    commit با فراخواننده است تا لاگ ممیزی در همان تراکنش بنشیند.
    """
    now = datetime.now(UTC)
    previous = active_scheme(db)
    if previous is not None:
        previous.status = SchemeStatus.retired
        previous.retired_at = now
        # قبل از درج فعالِ تازه flush می‌شود، وگرنه ایندکس یکتای جزئی
        # (uq_single_active_scheme) وسط همین تراکنش دو ردیف فعال می‌بیند.
        db.flush()

    scheme.status = SchemeStatus.active
    scheme.activated_at = now
    scheme.activated_by_user_id = actor_user_id
    db.flush()
