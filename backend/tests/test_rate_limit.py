"""لایهٔ اول دفاع از ورود: محدودیت نرخ به ازای IP.

لایهٔ دوم (قفل حساب به ازای نام کاربری) در test_login_lockout.py است.

هر تلاش عمداً نام کاربری *متفاوتی* دارد: با نام تکراری، قفلِ حساب زودتر از سقف
per-IP فعال می‌شود و آن‌وقت این تست دیگر چیزی دربارهٔ محدودیت per-IP اثبات نمی‌کند —
دقیقاً همان اتفاقی که با اضافه‌شدن قفل حساب افتاد. این شکل، دو لایه را از هم جدا
نگه می‌دارد.
"""


def test_login_is_rate_limited_per_ip_regardless_of_username(client, db_session):
    responses = [
        client.post("/api/auth/login", json={"username": f"ghost-{i}", "password": "wrong"})
        for i in range(10)
    ]
    assert all(r.status_code == 401 for r in responses), "قفل حساب نباید این‌جا دخالت کند"

    blocked = client.post("/api/auth/login", json={"username": "ghost-11", "password": "wrong"})
    assert blocked.status_code == 429
    assert "بیش از حد مجاز" in blocked.json()["detail"]
