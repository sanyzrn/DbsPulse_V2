"""خروجی Excel از فهرست ارزیابی‌ها برای گزارش‌گیری منابع انسانی."""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from app.models.evaluation import EvaluationRecord
from app.services.pdf import to_jalali

_HEADERS = [
    "کد ارزیابی",
    "نام پرسنل",
    "واحد",
    "وضعیت",
    "امتیاز عمومی ٪",
    "امتیاز تخصصی ٪",
    "امتیاز نهایی ٪",
    "نتیجه پیشنهادی",
    "تاریخ شروع",
    "تاریخ نهایی‌شدن",
]

_STATUS_LABELS = {
    "draft": "پیش‌نویس",
    "submitted": "ثبت‌شده",
    "hr_approved": "تأییدشده توسط HR",
    "deputy_approved": "تأییدشده توسط معاونت",
    "finalized": "نهایی‌شده",
}


def build_evaluations_workbook(records: list[EvaluationRecord]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "ارزیابی‌ها"
    ws.sheet_view.rightToLeft = True

    ws.append(_HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for r in records:
        ws.append(
            [
                r.evaluation_code,
                r.subject.full_name,
                r.subject.org_unit,
                _STATUS_LABELS.get(r.status.value, r.status.value),
                float(r.general_score_pct) if r.general_score_pct is not None else None,
                float(r.specialized_score_pct) if r.specialized_score_pct is not None else None,
                float(r.final_weighted_pct) if r.final_weighted_pct is not None else None,
                r.recommendation or "",
                to_jalali(r.created_at.isoformat()),
                to_jalali(r.finalized_at.isoformat()) if r.finalized_at else "",
            ]
        )

    for column_index, header in enumerate(_HEADERS, start=1):
        ws.column_dimensions[get_column_letter(column_index)].width = max(14, len(header) + 6)

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
