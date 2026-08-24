"""شکل ورودی/خروجی طرح نمره‌دهی (P1-04)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core import constants
from app.models.enums import SchemeStatus

#: سقف تعداد پله‌های جدول آستانه. بیش از این، جدول برای خواننده بی‌معنا می‌شود و
#: تفاوت دو پلهٔ مجاور از نویز محاسبه کمتر است.
MAX_THRESHOLDS = 8


class ThresholdBand(BaseModel):
    """یک پلهٔ جدول نتیجه: «تا این درصد ⇐ این برچسب»."""

    model_config = ConfigDict(str_strip_whitespace=True)

    #: سقف بازه، exclusive. آخرین پله باید بالای ۱۰۰ باشد تا نمرهٔ ۱۰۰ هم برچسب بگیرد.
    upper_exclusive: float = Field(gt=0, le=1000)
    label: str = Field(min_length=1, max_length=200)


class SchemeInput(BaseModel):
    """پیش‌نویس یک طرح — همان شکلی که برای پیش‌نمایش هم فرستاده می‌شود."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    general_section_weight: float = Field(ge=0, le=1)
    specialized_section_weight: float = Field(ge=0, le=1)
    evidence_required_scores: list[int] = Field(default_factory=list)
    evidence_min_words: int = Field(ge=0, le=200)
    evidence_max_words: int = Field(ge=1, le=1000)
    #: سقف امتیاز ویژه. صفر یعنی این قابلیت زیر این طرح در دسترس نیست. سقفِ سقف
    #: عمداً کوچک است: امتیاز ویژه باید یک تعدیل باشد، نه راهی برای دور زدن فرم.
    bonus_max_points: float = Field(default=constants.BONUS_MAX_POINTS, ge=0, le=20)
    thresholds: list[ThresholdBand] = Field(min_length=1, max_length=MAX_THRESHOLDS)
    #: {indicator_id: weight}. شاخصِ غایب وزن ۱ می‌گیرد.
    indicator_weights: dict[int, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self) -> "SchemeInput":
        # مجموع وزن بخش‌ها باید دقیقاً ۱ باشد، وگرنه «امتیاز نهایی» دیگر درصد
        # نیست: با ۰٫۶+۰٫۳ سقف واقعی ۹۰ می‌شود و هیچ‌کس به بالاترین پله نمی‌رسد.
        total = round(self.general_section_weight + self.specialized_section_weight, 6)
        if total != 1:
            raise ValueError(
                f"مجموع وزن دو بخش باید دقیقاً ۱ باشد (الان: {total})؛ "
                "وگرنه امتیاز نهایی دیگر درصد نیست"
            )

        if any(score < 1 or score > 5 for score in self.evidence_required_scores):
            raise ValueError("امتیازهای نیازمند شواهد باید بین ۱ تا ۵ باشند")
        if len(set(self.evidence_required_scores)) != len(self.evidence_required_scores):
            raise ValueError("امتیازهای نیازمند شواهد نباید تکراری باشند")

        if self.evidence_min_words > self.evidence_max_words:
            raise ValueError("حداقل تعداد کلمات شواهد نمی‌تواند از حداکثر آن بیشتر باشد")

        # پله‌ها باید صعودی باشند، وگرنه جست‌وجوی خطی در recommendation_for
        # بی‌صدا اولین پلهٔ بزرگ‌تر را برمی‌گرداند و جدول معنایی که نوشته شده را ندارد.
        uppers = [band.upper_exclusive for band in self.thresholds]
        if uppers != sorted(uppers) or len(set(uppers)) != len(uppers):
            raise ValueError("سقف پله‌های جدول نتیجه باید صعودی و بدون تکرار باشد")
        # آخرین پله باید بالای ۱۰۰ باشد؛ با سقف ۱۰۰ نمرهٔ کاملِ ۱۰۰ به هیچ
        # برچسبی نمی‌رسد و بدون نتیجه می‌ماند.
        if uppers[-1] <= 100:
            raise ValueError(
                "سقف آخرین پله باید بزرگ‌تر از ۱۰۰ باشد تا امتیاز ۱۰۰ هم نتیجه بگیرد"
            )

        if any(weight <= 0 for weight in self.indicator_weights.values()):
            raise ValueError("وزن شاخص باید بزرگ‌تر از صفر باشد")

        return self


class SchemeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int
    name: str
    status: SchemeStatus
    general_section_weight: float
    specialized_section_weight: float
    evidence_required_scores: list[int]
    evidence_min_words: int
    evidence_max_words: int
    bonus_max_points: float
    thresholds: list[ThresholdBand]
    indicator_weights: dict[int, float]
    created_at: datetime
    created_by_username: str | None = None
    activated_at: datetime | None
    activated_by_username: str | None = None
    retired_at: datetime | None


class ReclassifiedCase(BaseModel):
    """یک پروندهٔ نهایی‌شده، همان‌طور که زیر طرح پیشنهادی حساب می‌شد."""

    evaluation_code: str
    #: نامِ فرد عمداً این‌جا نیست — پیش‌نمایش دربارهٔ *قاعده* است، نه دربارهٔ افراد.
    org_unit: str
    current_final_pct: float
    proposed_final_pct: float
    current_recommendation: str
    proposed_recommendation: str

    @property
    def changed(self) -> bool:
        return self.current_recommendation != self.proposed_recommendation


class SchemePreview(BaseModel):
    """اثر یک طرح پیشنهادی روی پرونده‌های گذشته.

    این مهم‌ترین بخش این قابلیت است: عوض‌کردن وزن‌ها تصمیمی است که پیامدش تا
    وقتی روی دادهٔ واقعی دیده نشود، قابل تصور نیست. «۰٫۷ به‌جای ۰٫۶» یک عدد
    است؛ «۱۴ نفر از تمدید استاندارد به تمدید مشروط منتقل می‌شوند» یک تصمیم.
    """

    sample_size: int
    changed_count: int
    #: تعداد جابه‌جایی بین هر جفت برچسب: [{"from": ..., "to": ..., "count": n}]
    transitions: list[dict]
    cases: list[ReclassifiedCase]
