def test_login_is_rate_limited_after_repeated_attempts(client, db_session):
    # این تست کل سهمیه دقیقه‌ای /api/auth/login را مصرف می‌کند؛ عمداً تنها مصرف‌کننده
    # این endpoint در کل مجموعه تست است تا با تست‌های دیگر تداخل نکند.
    payload = {"username": "nonexistent-user", "password": "wrong"}

    responses = [client.post("/api/auth/login", json=payload) for _ in range(10)]
    assert all(r.status_code == 401 for r in responses)

    blocked = client.post("/api/auth/login", json=payload)
    assert blocked.status_code == 429
    assert "بیش از حد مجاز" in blocked.json()["detail"]
