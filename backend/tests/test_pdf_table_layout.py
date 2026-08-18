"""چیدمان جدول‌های کارنامهٔ رسمی، وقتی سند بیش از یک صفحه می‌شود.

مسئله‌ای که این فایل نگه می‌دارد
--------------------------------
جدول‌ها چیدمان خودکار داشتند (`table-layout` پیش‌فرض)، یعنی پهنای ستون‌ها از روی
محتوا حساب می‌شد. تا وقتی جدول در یک صفحه جا می‌شود مشکلی نیست؛ ولی وقتی بین دو
صفحه می‌شکند، هر تکه محتوای خودش را دارد و پهنای خودش را می‌گیرد. نتیجه در
بدترین حالت این بود: تکه‌ای که فقط یک ردیف در انتهای صفحه داشت، ستون «شرح» را تا
عرض یک نویسه جمع می‌کرد و متن عمودی، نویسه‌به‌نویسه، می‌شکست.

این ناخوانا بودنِ ساده نیست: سند رسمی‌ای که امضا می‌شود و کد تأیید دارد، در
نسخهٔ چاپی‌اش شاخصی را نشان می‌دهد که خوانده نمی‌شود.

چرا تستِ *متنِ قالب*
--------------------
نتیجهٔ واقعی (پهنای ستون در PDF) از فایل باینری بیرون‌کشیدنی نیست بدون یک
وابستگیِ تحلیل PDF. ولی علت، یک تصمیم صریح در CSS است و همان قابل نگه‌داشتن
است: چیدمان ثابت به‌علاوهٔ پهنای اعلام‌شدهٔ ستون‌ها.
"""
import re
from pathlib import Path

import pytest

_TEMPLATE = Path(__file__).resolve().parents[1] / "app" / "templates" / "evaluation_summary.html"


@pytest.fixture(scope="module")
def template() -> str:
    return _TEMPLATE.read_text(encoding="utf-8")


def test_tables_have_fixed_layout(template: str):
    """بدون این، پهنای ستون‌ها بین دو تکهٔ یک جدول فرق می‌کند."""
    assert "table-layout: fixed" in template


def test_every_table_declares_its_columns(template: str):
    """چیدمان ثابت بدون پهنای اعلام‌شده یعنی ستون‌های مساوی.

    ستون «امتیاز» یک رقم است و «شرح» یک جملهٔ کامل؛ سهم مساوی، شرح را بی‌دلیل
    چندخطی می‌کند و همان به‌هم‌ریختگی را از راه دیگری برمی‌گرداند.
    """
    tables = template.count("<table>")
    colgroups = template.count("<colgroup>")
    assert tables > 0
    assert colgroups == tables


def test_column_widths_add_up(template: str):
    for colgroup in re.findall(r"<colgroup>(.*?)</colgroup>", template, re.DOTALL):
        widths = [int(w) for w in re.findall(r"width:\s*(\d+)%", colgroup)]
        assert widths, "colgroup بدون پهنا"
        assert sum(widths) == 100, f"جمع پهناها {sum(widths)} است، نه ۱۰۰"


def test_header_repeats_on_continuation_pages(template: str):
    """جدولی که سرستونش را در صفحهٔ اول جا گذاشته، در صفحهٔ دوم ستون «امتیاز» و
    «شواهد» را از هم قابل‌تشخیص نمی‌گذارد."""
    assert "display: table-header-group" in template


def test_rows_are_not_split_across_pages(template: str):
    assert "break-inside: avoid" in template
