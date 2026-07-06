from pydantic import BaseModel


class AppConfig(BaseModel):
    """قوانین کسب‌وکار که فرانت‌اند هم لازمشان دارد؛ از یک منبع واحد (backend) خوانده
    می‌شوند تا نسخه‌های کپی‌شده در UI با سرور واگرا نشوند."""

    evidence_min_words: int
    evidence_exempt_score: int
    general_section_weight: float
    specialized_section_weight: float
