import pytest

from app.services.pdf import TEMPLATES_DIR, _env, _local_templates_only_url_fetcher


def _snapshot_with(evidence_text: str) -> dict:
    return {
        "evaluation_code": "EVL-0001",
        "personnel": {
            "full_name": "کارمند تست",
            "personnel_code": "P-1",
            "job_title": "کارشناس",
            "org_unit": "واحد تست",
        },
        "evaluator": {"username": "sup1", "role_label": "مسئول واحد"},
        "evaluation_started_at": "2026-01-01T00:00:00+00:00",
        "finalized_at": "2026-01-02T00:00:00+00:00",
        "general_score_pct": 60.0,
        "specialized_score_pct": 60.0,
        "final_weighted_pct": 60.0,
        "recommendation": "تمدید مشروط به برنامه بهبود مکتوب",
        "evaluator_comment": None,
        "scores": [
            {
                "indicator_id": 1,
                "category": "دسته",
                "description": "شرح",
                "section": "general",
                "score": 2,
                "evidence_text": evidence_text,
            }
        ],
        "comments": [],
    }


def test_user_supplied_html_is_escaped_in_rendered_template():
    """متن شواهد ورودی کاربر است؛ HTML خام نباید وارد سند شود (جعل/حمله file://)."""
    payload = '<script>x</script><img src="file:///etc/passwd">'
    html = _env.get_template("evaluation_summary.html").render(snapshot=_snapshot_with(payload))
    assert "<script>" not in html
    assert '<img src="file:///etc/passwd">' not in html
    assert "&lt;script&gt;" in html


def test_url_fetcher_blocks_paths_outside_templates_dir():
    with pytest.raises(ValueError):
        _local_templates_only_url_fetcher("file:///etc/passwd")
    with pytest.raises(ValueError):
        _local_templates_only_url_fetcher("https://example.com/x.png")
    # فایل‌های فونت داخل templates همچنان مجازند
    font_uri = (TEMPLATES_DIR / "fonts" / "Vazirmatn-Regular.woff2").as_uri()
    result = _local_templates_only_url_fetcher(font_uri)
    assert "file_obj" in result or "string" in result


def test_jalali_filter_converts_iso_dates():
    from app.services.pdf import to_jalali

    # ۱ تیر ۱۴۰۵ = 2026-06-22
    assert to_jalali("2026-06-22T09:30:00+00:00") == "۱۴۰۵/۰۴/۰۱ ساعت ۰۹:۳۰"
    assert to_jalali(None) == "—"
    assert to_jalali("") == "—"
    # مقدار نامعتبر دست‌نخورده برمی‌گردد (snapshot های قدیمی)
    assert to_jalali("نامعتبر") == "نامعتبر"


def test_signature_block_matches_evaluation_path():
    """مسیر «مدیر» امضای مسئول واحد/HR ندارد؛ مسیر عادی هر چهار امضا را دارد."""
    snapshot = _snapshot_with("متن")
    snapshot["evaluator"]["role_label"] = "معاونت"
    html = _env.get_template("evaluation_summary.html").render(snapshot=snapshot)
    assert "امضای مسئول واحد" not in html
    assert "امضای معاونت" in html and "امضای مدیرعامل" in html

    snapshot["evaluator"]["role_label"] = "مسئول واحد"
    html = _env.get_template("evaluation_summary.html").render(snapshot=snapshot)
    assert "امضای مسئول واحد" in html
    assert "امضای منابع انسانی" in html
    assert "امضای معاونت" in html


def test_template_renders_jalali_dates():
    snapshot = _snapshot_with("متن")
    snapshot["evaluation_started_at"] = "2026-06-22T09:30:00+00:00"
    html = _env.get_template("evaluation_summary.html").render(snapshot=snapshot)
    assert "۱۴۰۵/۰۴/۰۱" in html
