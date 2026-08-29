from pydantic import BaseModel


class AppConfig(BaseModel):
    """قوانین کسب‌وکار که فرانت‌اند هم لازمشان دارد؛ از یک منبع واحد (backend) خوانده
    می‌شوند تا نسخه‌های کپی‌شده در UI با سرور واگرا نشوند."""

    evidence_min_words: int
    evidence_max_words: int
    # امتیازهایی که شواهد عینی برایشان اجباری است (پیش‌فرض [۱، ۵]).
    evidence_required_scores: list[int]
    general_section_weight: float
    specialized_section_weight: float
    # سقف امتیاز ویژه در طرح فعال؛ صفر یعنی فرم اصلاً این بخش را نشان ندهد.
    bonus_max_points: float
    # حداقل طول توضیح امتیاز ویژه؛ قاعدهٔ مشترک فرانت و سرور.
    bonus_reason_min_length: int
