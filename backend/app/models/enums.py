import enum


class PersonnelStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class UserRole(str, enum.Enum):
    unit_supervisor = "unit_supervisor"
    hr = "hr"
    deputy = "deputy"
    ceo = "ceo"
    # کارمند عادی: فقط نتیجه نهایی ارزیابی خودش را می‌بیند و «رؤیت» می‌زند
    employee = "employee"


class IndicatorSection(str, enum.Enum):
    general = "general"
    specialized = "specialized"


class EvaluationStage(str, enum.Enum):
    supervisor_scoring = "supervisor_scoring"
    hr_review = "hr_review"
    deputy_review = "deputy_review"
    ceo_final = "ceo_final"


class EvaluationStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    hr_approved = "hr_approved"
    deputy_approved = "deputy_approved"
    finalized = "finalized"


class CommentStage(str, enum.Enum):
    hr_review = "hr_review"
    deputy_review = "deputy_review"
    ceo_final = "ceo_final"


class PeriodStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class ImprovementPlanStatus(str, enum.Enum):
    open = "open"
    completed = "completed"
    cancelled = "cancelled"
