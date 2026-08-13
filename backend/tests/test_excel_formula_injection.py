"""P2-02 — متن آزادِ کاربر نباید در فایل اکسل به فرمول تبدیل شود.

سناریو: یک مسئول واحد در فیلد «شواهد» یا عنوان برنامهٔ بهبود چیزی مثل
`=cmd|'/c calc'!A1` می‌نویسد. HR فایل اکسل را باز می‌کند و Excel آن را اجرا می‌کند
(یا در حالت خفیف‌تر، openpyxl همان موقع سلول را به‌عنوان فرمول می‌نویسد).
"""
from datetime import date, datetime
from io import BytesIO

import pytest
from openpyxl import load_workbook

from app.services.excel import _neutralise, build_personnel_workbook, build_report_workbook


class _FakePersonnel:
    def __init__(self, full_name: str, job_title: str = "کارشناس"):
        self.personnel_code = "P-1"
        self.full_name = full_name
        self.job_title = job_title
        self.org_unit = "واحد"
        self.is_manager = False
        self.status = type("S", (), {"value": "active"})()
        self.contract_start_date = date(2025, 1, 1)
        self.contract_end_date = date(2026, 1, 1)
        self.created_at = datetime(2025, 1, 1)


@pytest.mark.parametrize(
    "dangerous",
    [
        "=cmd|'/c calc'!A1",
        "+1+1",
        "-2+3",
        "@SUM(A1)",
        "\t=1+1",
    ],
)
def test_formula_triggering_prefixes_are_neutralised(dangerous):
    assert _neutralise(dangerous) == "'" + dangerous


@pytest.mark.parametrize("harmless", ["علی محمدی", "واحد فروش", "", "۱۲۳", "A=B"])
def test_ordinary_text_is_left_alone(harmless):
    assert _neutralise(harmless) == harmless


@pytest.mark.parametrize("number", [0, 5, -3, 4.25, None, True])
def test_non_string_values_are_left_alone(number):
    assert _neutralise(number) is number


def test_exported_cell_is_text_not_a_formula():
    """مهم‌ترین ادعا: سلول در فایل واقعی از نوع فرمول نیست."""
    payload = "=cmd|'/c calc'!A1"
    workbook = load_workbook(
        BytesIO(build_personnel_workbook([_FakePersonnel(payload)]))
    )
    cell = workbook.active.cell(row=2, column=2)

    assert cell.data_type != "f", "سلول به‌عنوان فرمول نوشته شده است"
    assert cell.value == "'" + payload


def test_secondary_sheets_of_the_report_are_guarded_too():
    """برگه‌های دوم/سوم گزارش هم از همان مسیر امن ساخته می‌شوند."""
    workbook = load_workbook(
        BytesIO(
            build_report_workbook(
                total=1,
                avg_final_pct=80.0,
                by_org_unit=[("=HYPERLINK(\"http://evil\")", 80.0, 1)],
                by_indicator=[("@general", "-درصد رشد", 4.0, 1)],
            )
        )
    )

    unit_cell = workbook["میانگین به‌تفکیک واحد"].cell(row=2, column=1)
    assert unit_cell.data_type != "f"
    assert unit_cell.value.startswith("'=HYPERLINK")

    indicator_sheet = workbook["میانگین به‌تفکیک شاخص"]
    assert indicator_sheet.cell(row=2, column=1).value == "'@general"
    assert indicator_sheet.cell(row=2, column=2).value == "'-درصد رشد"


def test_numbers_in_the_report_stay_numeric():
    """ضدعفونی نباید ستون‌های عددی را به متن تبدیل کند، وگرنه نمودار/میانگین می‌شکند."""
    workbook = load_workbook(
        BytesIO(
            build_report_workbook(
                total=3,
                avg_final_pct=72.5,
                by_org_unit=[("فروش", 72.5, 3)],
                by_indicator=[],
            )
        )
    )

    unit_sheet = workbook["میانگین به‌تفکیک واحد"]
    assert unit_sheet.cell(row=2, column=2).value == 72.5
    assert unit_sheet.cell(row=2, column=3).value == 3
