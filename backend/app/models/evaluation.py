from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.text_limits import (
    BONUS_REASON_MAX,
    COMMENT_MAX,
    EVALUATOR_COMMENT_MAX,
    EVIDENCE_MAX,
    OBJECTION_MAX,
    SELF_ASSESSMENT_SUMMARY_MAX,
)
from app.db.base import Base
from app.models.enums import CommentStage, EvaluationStatus
from app.models.personnel import Personnel  # noqa: TC001  (relationship target)
from app.models.user import User  # noqa: TC001  (relationship target)


class EvaluationRecord(Base):
    __tablename__ = "evaluation_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    # توکن تصادفی و غیرقابل‌حدس برای صفحهٔ تأیید عمومی (/api/verify/{token})؛ برخلاف
    # evaluation_code که ترتیبی است (EVL-0001, EVL-0002, ...) و روی endpoint بدون
    # احراز هویت نباید کلید جست‌وجو باشد. فقط در لحظهٔ نهایی‌سازی مقداردهی می‌شود.
    # یکتایی از راه ایندکس یکتا اعمال می‌شود (پایین‌تر، در __table_args__) نه
    # قید UNIQUE. هر دو با هم یعنی دو شیء برای یک تضمین، و autogenerate هر بار
    # پیشنهاد می‌داد آن‌که در دیتابیس نیست را بسازد.
    verify_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject_personnel_id: Mapped[int] = mapped_column(ForeignKey("personnel.id"), nullable=False)
    # زنجیره در لحظهٔ ساخت از `EvaluationAccess` کپی می‌شود، تا تغییر بعدیِ
    # دسترسی، پروندهٔ در جریان را از زیر پای تأییدکننده‌اش عوض نکند. هر دو مرحلهٔ
    # میانی می‌توانند غایب باشند و NULL دقیقاً همان را می‌گوید: مسئول واحدِ خالی
    # یعنی مسیر «مدیر»، معاونتِ خالی یعنی فرد مستقیم زیر نظر مدیرعامل است.
    unit_supervisor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deputy_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    ceo_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # مسئولِ HR این پرونده. سه مرحلهٔ دیگر همیشه صاحب مشخصی داشتند، ولی مرحلهٔ HR
    # نداشت: هر کاربر HR روی هر پرونده‌ای می‌توانست اقدام کند، پس در سازمانی با چند
    # نفر HR پاسخ سؤال «مسئولِ این پرونده که بود؟» وجود نداشت — فقط «چه کسی کلیک کرد».
    # تا وقتی NULL است پرونده در صف مشترک HR می‌ماند و اولین اقدام، آن را claim می‌کند.
    hr_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # دوره‌ای که این ارزیابی در آن انجام شده؛ ارزیابی‌های خارج از دوره NULL می‌مانند
    period_id: Mapped[int | None] = mapped_column(ForeignKey("evaluation_periods.id"), nullable=True)
    # نسخهٔ طرح نمره‌دهی که این پرونده *زیر آن ساخته شده* (P1-04).
    #
    # محاسبه همیشه از این می‌خواند، نه از طرحِ فعال. بدون آن، تغییر وزن‌ها توسط HR
    # معنای هر پروندهٔ گذشته را بی‌صدا بازنویسی می‌کرد: نمره‌ها ثابت، ولی «نتیجهٔ
    # پیشنهادی» عوض‌شده. این ستون پایداری تاریخ را به یک خاصیت ساختاری تبدیل
    # می‌کند، نه چیزی که باید یادت بماند.
    #
    # nullable است چون پرونده‌های پیش از این قابلیت طرحی نداشتند؛ مایگریشن آن‌ها
    # را به نسخهٔ ۱ — که دقیقاً از همان ثابت‌های قبلی ساخته شده — مهر می‌زند.
    scoring_scheme_id: Mapped[int | None] = mapped_column(
        ForeignKey("scoring_schemes.id"), nullable=True
    )
    # نسخهٔ چارچوب شاخص‌ها که این پرونده زیر آن باز شده (P1-05) — یعنی *چه
    # سؤال‌هایی* پرسیده شد، در حالی که ستون بالا می‌گوید *با چه قاعده‌ای* حساب شد.
    #
    # «کامل بودن» با همین نسخه سنجیده می‌شود، نه با مجموعهٔ فعالِ امروز. بدون آن،
    # هر افزودن یا غیرفعال‌کردن شاخص، هر پیش‌نویسِ در جریان را غیرقابل‌ثبت می‌کرد
    # و کسی که ویرایش می‌کرد هیچ‌وقت خبردار نمی‌شد.
    #
    # nullable است به همان دلیل ستون بالا؛ مایگریشن پرونده‌های موجود را به نسخهٔ ۱
    # مهر می‌زند که دقیقاً از مجموعهٔ فعالِ همان لحظه ساخته می‌شود.
    indicator_framework_id: Mapped[int | None] = mapped_column(
        ForeignKey("indicator_frameworks.id"), nullable=True
    )
    # ستون stage حذف شد: همیشه ۱:۱ از status قابل استخراج بود و دو منبع حقیقت
    # هم‌معنا خطر واگرایی داشت. مقدار stage در API از status مشتق می‌شود
    # (app/schemas/evaluation.py).
    status: Mapped[EvaluationStatus] = mapped_column(
        Enum(EvaluationStatus, name="evaluation_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    # امتیازِ فرم، پیش از افزودن امتیاز ویژه. مشتق‌کردنش از (نهایی منهای ویژه)
    # وسوسه‌انگیز بود ولی نادرست است: وقتی جمع از ۱۰۰ بگذرد، نهایی روی ۱۰۰
    # می‌ایستد و آن تفریق عددی می‌داد که هیچ‌وقت محاسبه نشده بود. سند رسمی
    # نباید عددی نشان بدهد که از یک تفریقِ حدسی درآمده.
    base_weighted_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    general_score_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    specialized_score_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    final_weighted_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # امتیاز ویژه: نمرهٔ اختیاریِ ارزیاب بابت کاری خارج از شرح وظایف — کاری که در
    # هیچ شاخصی نمی‌گنجد و بدون این ستون هیچ جایی در نتیجه ندارد. عمداً جدا از
    # `final_weighted_pct` نگه داشته می‌شود، نه در آن حل: سند نهایی باید بتواند
    # بگوید «۸۴ از فرم + ۳ بابتِ فلان کار»، نه یک عدد ۸۷ که منشأش پیدا نیست.
    #
    # NULL و صفر یک معنا دارند (امتیاز ویژه‌ای در کار نیست)؛ NULL برای پرونده‌های
    # پیش از این قابلیت است.
    bonus_points: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    bonus_reason: Mapped[str | None] = mapped_column(String(BONUS_REASON_MAX), nullable=True)
    evaluator_comment: Mapped[str | None] = mapped_column(String(EVALUATOR_COMMENT_MAX), nullable=True)
    final_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # لحظهٔ ورود به وضعیت فعلی. جاروی SLA پیش از این از created_at استفاده می‌کرد،
    # یعنی «سن کل پرونده» را می‌سنجید نه «چقدر در این مرحله مانده». پرونده‌ای که سه
    # هفته در سه مرحله چرخیده بود، لحظهٔ رسیدن به مرحلهٔ چهارم فوراً تأخیردار به‌نظر
    # می‌رسید — و پرونده‌ای که تازه برگشت خورده هم همین‌طور.
    stage_entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # رؤیت رسمی نتیجه توسط خود کارمند (نقش employee) پس از نهایی شدن
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    # خودارزیابی: نظر خودِ فرد، ثبت‌شده پیش از قطعی‌شدن نمرهٔ ارزیاب. در محاسبهٔ
    # نتیجه هیچ نقشی ندارد (جدول جداست) — یک دیدگاه دوم است، نه یک رأی.
    self_assessment_submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    self_assessment_note: Mapped[str | None] = mapped_column(String(SELF_ASSESSMENT_SUMMARY_MAX), nullable=True)

    # اعتراض رسمی کارمند به نتیجه. «رؤیت» فقط ثبت می‌کند که فرد نتیجه را *دید*، نه
    # این‌که با آن موافق است — بدون مسیر اعتراض، سامانه هیچ جایی برای مخالفت او ندارد
    # و در هر بازبینی حقوقی، پاسخ «کارمند چه گفت؟» می‌شود «هیچ‌چیز ثبت نشده».
    objection_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    objection_reason: Mapped[str | None] = mapped_column(String(OBJECTION_MAX), nullable=True)
    objection_resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    objection_resolution: Mapped[str | None] = mapped_column(String(OBJECTION_MAX), nullable=True)
    objection_resolved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    scores: Mapped[list["EvaluationScore"]] = relationship(
        back_populates="evaluation_record", cascade="all, delete-orphan"
    )
    comments: Mapped[list["EvaluationComment"]] = relationship(
        back_populates="evaluation_record",
        cascade="all, delete-orphan",
        order_by="EvaluationComment.created_at",
    )
    # eager join تا فهرست‌ها بدون N+1 نام پرسنل را همراه داشته باشند
    subject: Mapped["Personnel"] = relationship(lazy="joined")
    # همان دلیل: صف بررسی HR نام مالک را در هر ردیف نشان می‌دهد
    hr_user: Mapped["User | None"] = relationship(lazy="joined", foreign_keys=[hr_user_id])

    # ایندکس‌ها در مایگریشن‌ها ساخته شده‌اند و تا امروز روی مدل اعلام نشده بودند،
    # پس `alembic revision --autogenerate` آن‌ها را «اضافی» می‌دید و DROP پیشنهاد
    # می‌داد. اعلامشان این‌جا یعنی autogenerate واقعیتِ دیتابیس را می‌بیند.
    __table_args__ = (
        # امتیاز ویژه هرگز منفی نیست، و امتیازِ بی‌دلیل هم ثبت نمی‌شود: عددی که
        # کسی نتواند توضیحش را بخواند، در سند تصمیمِ تمدید قرارداد جایی ندارد.
        # سقفِ بالا این‌جا نیست چون از نسخهٔ طرحِ همان پرونده می‌آید، نه از یک عدد ثابت.
        CheckConstraint(
            "bonus_points IS NULL OR bonus_points >= 0",
            name="ck_evaluation_records_bonus_not_negative",
        ),
        CheckConstraint(
            "bonus_points IS NULL OR bonus_points = 0 OR bonus_reason IS NOT NULL",
            name="ck_evaluation_records_bonus_needs_reason",
        ),
        # سه مرحله باید سه نفر باشند. در مایگریشن با NOT VALID اضافه شده‌اند
        # (توضیحش آن‌جاست)؛ اعلامشان این‌جا فقط برای این است که
        # `alembic --autogenerate` آن‌ها را «اضافی» نبیند و DROP پیشنهاد ندهد.
        CheckConstraint(
            "unit_supervisor_user_id IS NULL OR deputy_user_id IS NULL "
            "OR unit_supervisor_user_id <> deputy_user_id",
            name="ck_evaluation_records_supervisor_not_deputy",
        ),
        CheckConstraint(
            "unit_supervisor_user_id IS NULL OR unit_supervisor_user_id <> ceo_user_id",
            name="ck_evaluation_records_supervisor_not_ceo",
        ),
        CheckConstraint(
            "deputy_user_id IS NULL OR deputy_user_id <> ceo_user_id",
            name="ck_evaluation_records_deputy_not_ceo",
        ),
        Index("ix_evaluation_records_subject", "subject_personnel_id"),
        Index("ix_evaluation_records_supervisor", "unit_supervisor_user_id"),
        Index("ix_evaluation_records_deputy", "deputy_user_id"),
        Index("ix_evaluation_records_ceo", "ceo_user_id"),
        Index("ix_evaluation_records_hr_user_id", "hr_user_id"),
        Index("ix_evaluation_records_period", "period_id"),
        Index("ix_evaluation_records_status_created", "status", "created_at"),
        Index("ix_evaluation_records_final_pct", "final_weighted_pct"),
        Index("ix_evaluation_records_stage_entered_at", "stage_entered_at"),
        Index("ix_evaluation_records_verify_token", "verify_token", unique=True),
        # اعتراض‌های باز — ایندکس جزئی چون اکثریت رکوردها اعتراضی ندارند
        Index(
            "ix_evaluation_records_open_objection",
            "objection_at",
            postgresql_where=text("objection_at IS NOT NULL AND objection_resolved_at IS NULL"),
        ),
        # قانون «هر پرسنل حداکثر یک ارزیابی باز» — در دیتابیس، نه در کد.
        # این گاردی است که کل ایمنیِ هم‌زمانی این سامانه رویش بنا شده: بررسی در
        # کد در برابر دو درخواست هم‌زمان بی‌فایده است، چون هر دو پیش از commit
        # اولی «بازی نیست» می‌بینند. تا امروز فقط در مایگریشن بود و autogenerate
        # حذفش را پیشنهاد می‌داد.
        Index(
            "uq_open_evaluation_per_personnel",
            "subject_personnel_id",
            unique=True,
            postgresql_where=text("status NOT IN ('finalized', 'cancelled')"),
        ),
    )

    @property
    def single_decider(self) -> bool:
        """نمره‌دهندهٔ اول و تأییدکنندهٔ نهایی، یک نفرند.

        فقط برای کسی رخ می‌دهد که مستقیماً زیر نظر مدیرعامل کار می‌کند — و آن
        حالت مجاز است، چون بالای سرش کسِ دیگری وجود ندارد. ولی مجاز بودن یعنی
        «قابل ثبت»، نه «قابل کتمان»: بدون این پرچم، لاگ دو تأیید نشان می‌داد و
        خواننده‌اش دو بررسی مستقل می‌فهمید. سند نهایی همین را چاپ می‌کند.
        """
        return (
            self.unit_supervisor_user_id is not None
            and self.unit_supervisor_user_id == self.ceo_user_id
        )

    @property
    def subject_full_name(self) -> str:
        return self.subject.full_name

    @property
    def hr_username(self) -> str | None:
        return self.hr_user.username if self.hr_user else None


class EvaluationScore(Base):
    __tablename__ = "evaluation_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_record_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_records.id"), nullable=False
    )
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicators.id"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_text: Mapped[str | None] = mapped_column(String(EVIDENCE_MAX), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    evaluation_record: Mapped["EvaluationRecord"] = relationship(back_populates="scores")

    __table_args__ = (
        CheckConstraint("score BETWEEN 1 AND 5", name="ck_evaluation_scores_score_range"),
        Index("ix_evaluation_scores_record", "evaluation_record_id"),
        UniqueConstraint(
            "evaluation_record_id", "indicator_id", name="uq_evaluation_scores_record_indicator"
        ),
    )


class EvaluationComment(Base):
    __tablename__ = "evaluation_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_record_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_records.id"), nullable=False
    )
    commenter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # پاسخ threaded: کامنتِ والد (فقط یک سطح عمق). null یعنی کامنت سطح‌بالا.
    parent_comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("evaluation_comments.id", ondelete="CASCADE"), nullable=True
    )
    stage: Mapped[CommentStage] = mapped_column(
        Enum(CommentStage, name="comment_stage", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    comment_text: Mapped[str] = mapped_column(String(COMMENT_MAX), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    evaluation_record: Mapped["EvaluationRecord"] = relationship(back_populates="comments")
    commenter: Mapped["User"] = relationship(lazy="joined")

    @property
    def commenter_username(self) -> str | None:
        return self.commenter.username if self.commenter else None

    __table_args__ = (
        Index("ix_evaluation_comments_record", "evaluation_record_id"),
        Index("ix_evaluation_comments_parent_comment_id", "parent_comment_id"),
    )
