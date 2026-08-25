"""تفکیک «محل» (دفتر مرکزی، کارخانه) از «واحد» درون همان `org_unit`.

سازمانی که هم دفتر مرکزی دارد و هم کارخانه، «فروشِ کارخانه» و «فروشِ دفتر
مرکزی» را دو چیز می‌بیند — ولی `org_unit` یک رشتهٔ آزاد بود و هر دو را یکی
گزارش می‌کرد.

بُعد جداگانه راه درست‌تری بود، ولی `org_unit` در حدود صد نقطه استفاده شده و
تصمیم صاحب محصول این بود که فعلاً قرارداد در همان رشته بماند. پس این تست‌ها
دقیقاً همان قرارداد را می‌بندند: تنها جایی که می‌داند جداکننده چیست،
`services/org_unit.py` است.
"""
from app.services.org_unit import known_sites, site_of, split_site
from tests.helpers import auth_header, make_personnel, make_user


def test_the_three_separators_people_actually_type():
    assert split_site("کارخانه / فروش") == ("کارخانه", "فروش")
    assert split_site("کارخانه — فروش") == ("کارخانه", "فروش")
    assert split_site("کارخانه - فروش") == ("کارخانه", "فروش")


def test_no_separator_means_one_site_which_is_the_normal_case():
    """نبودِ جداکننده خطا نیست؛ سازمان‌های تک‌محلی اکثریت‌اند."""
    assert split_site("فروش") == (None, "فروش")
    assert site_of("فروش") is None


def test_a_half_written_value_is_left_alone():
    """«/ فروش» یا «کارخانه /» نیمه‌کاره‌اند.

    برگرداندنِ محلِ خالی یا واحدِ خالی، یک ردیفِ بی‌معنا در گزارش می‌سازد که
    منشأش معلوم نیست؛ رشتهٔ کامل دست‌کم قابل خواندن است.
    """
    assert split_site("/ فروش") == (None, "/ فروش")
    assert split_site("کارخانه /") == (None, "کارخانه /")


def test_the_three_known_sites_are_always_offered():
    """فهرست محل‌ها دیگر *استخراج‌شده* نیست.

    وقتی از روی داده ساخته می‌شد، محلی که هنوز هیچ‌کس در آن ثبت نشده بود در هیچ
    فیلتری وجود نداشت — یعنی برای ثبتِ اولین نفر در «مدرپ‌ها» باید اول کسی در
    «مدرپ‌ها» می‌بود.
    """
    units = ["کارخانه / فروش", "کارخانه / انبار", "دفتر مرکزی / مالی", "منابع انسانی"]
    assert known_sites(units) == ["دفتر مرکزی", "کارخانه", "مدرپ‌ها"]


def test_a_site_that_only_exists_in_the_data_is_not_hidden():
    """فهرست *شامل* واقعیت است، نه محدود به سه نام رسمی.

    اگر محدود می‌شد، دادهٔ قدیمی با املای دیگر از فیلترها ناپدید می‌شد و کسی
    نمی‌فهمید چرا چند نفر در هیچ گزارشی نیستند.
    """
    assert known_sites(["انبار مرکزی / تدارکات"]) == [
        "دفتر مرکزی",
        "کارخانه",
        "مدرپ‌ها",
        "انبار مرکزی",
    ]


def test_joining_a_site_and_unit_is_the_reverse_of_splitting():
    from app.services.org_unit import join_site

    assert join_site("کارخانه", "فروش") == "کارخانه / فروش"
    assert split_site(join_site("کارخانه", "فروش")) == ("کارخانه", "فروش")
    # بدون محل، فقط واحد — سازمانی که یک محل بیشتر ندارد نباید جداکننده ببیند.
    assert join_site(None, "فروش") == "فروش"
    assert join_site("", "فروش") == "فروش"


def test_filtering_personnel_by_site(client, db_session):
    """یک محل، همهٔ واحدهای زیرش را می‌آورد — نه فقط آن‌که نامش دقیق است."""
    hr = make_user(db_session, "hr")
    make_personnel(db_session, org_unit="کارخانه / فروش", full_name="الف")
    make_personnel(db_session, org_unit="کارخانه / انبار", full_name="ب")
    make_personnel(db_session, org_unit="دفتر مرکزی / مالی", full_name="ج")
    db_session.commit()

    response = client.get(
        "/api/personnel", params={"site": "کارخانه", "limit": 100}, headers=auth_header(hr)
    )
    assert response.status_code == 200, response.text
    names = {item["full_name"] for item in response.json()["items"]}
    assert names == {"الف", "ب"}


def test_the_site_filter_does_not_match_a_unit_of_the_same_name(client, db_session):
    """گاردِ ظریف: «کارخانه» به‌تنهایی یک *واحد* است، نه محل.

    اگر فیلتر با شباهتِ ساده کار می‌کرد، ردیفی که اصلاً محل ندارد هم می‌آمد و
    گزارشِ «کارخانه» شامل کسی می‌شد که در دفتر مرکزی نشسته.
    """
    hr = make_user(db_session, "hr")
    make_personnel(db_session, org_unit="کارخانه", full_name="بدون محل")
    make_personnel(db_session, org_unit="کارخانه / فروش", full_name="با محل")
    db_session.commit()

    response = client.get(
        "/api/personnel", params={"site": "کارخانه", "limit": 100}, headers=auth_header(hr)
    )
    names = {item["full_name"] for item in response.json()["items"]}
    assert names == {"با محل"}
