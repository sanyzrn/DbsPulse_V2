"""آزمونِ سرتسریِ سطحِ API: ورود، بارگذاری اکسلِ ناقص، بازرسی با مدل، پرسش و
اصلاح، پیشنهادِ ورود، تأیید، و راستی‌آزماییِ دادهٔ ساخته‌شده و ردِ ممیزی."""
import json
import re
import time
import urllib.request
from io import BytesIO

from openpyxl import Workbook

BASE = "http://127.0.0.1:8000"

RUN = str(int(time.time()))[-6:]
HEADERS = [
    "کد پرسنلی", "نام و نام خانوادگی", "عنوان شغلی", "محل", "واحد سازمانی",
    "مدیر", "وضعیت", "شروع قرارداد", "پایان قرارداد", "نام کاربری",
    "رمز اولیه", "مسئول مستقیم", "معاونت مربوطه", "مدیرعامل",
]


def unique_workbook() -> bytes:
    """فایلِ ناقص با کدهای یکتا برای هر اجرا — آزمونِ تکرارپذیر."""
    wb = Workbook()
    ws = wb.active
    ws.append(HEADERS)
    ws.append([
        f"E2E-{RUN}A", "نریمان صالحی", "کارشناس فروش", "دفتر مرکزی", "فروش",
        "خیر", "فعال", "۱۴۰۴/۰۴/۰۱", "", f"nariman{RUN}", "", "", "",
    ])
    ws.append([
        f"E2E-{RUN}B", "شبنم قادر", "کارشناس فروش", "دفتر مرکزی", "فروش",
        "خیر", "فعال", "۱۴۰۴/۰۵/۰۱", "۱۴۰۷/۰۵/۰۱", "", "", "", "",
    ])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def call(method, path, token=None, data=None, files=None):
    url = BASE + path
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if files:
        import uuid

        boundary = uuid.uuid4().hex
        parts = []
        for name, filename, content, ctype in files:
            parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\nContent-Type: {ctype}\r\n\r\n".encode()
                + content
                + b"\r\n"
            )
        parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(parts)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif data is not None:
        body = json.dumps(data, ensure_ascii=False).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


def main() -> None:
    login = call("POST", "/api/auth/login", data={"username": "ai_hr", "password": "Ai-Hr-Pass-1234"})
    token = login["access_token"]
    assert login["role"] == "hr"
    print("1) login OK")

    status = call("GET", "/api/ai/status", token)
    assert status["available"] and status["allow_write_actions"] and status["allow_uploads"]
    print("2) status:", status)

    tools = call("GET", "/api/ai/tools", token)
    assert any(t["name"] == "import_personnel" for t in tools)
    print(f"3) tools advertised: {len(tools)} (incl. import_personnel)")

    convo = call("POST", "/api/ai/conversations", token, data={})
    cid = convo["id"]
    content = unique_workbook()
    upload = call(
        "POST", f"/api/ai/conversations/{cid}/attachments", token,
        files=[("file", "e2e-personnel.xlsx", content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")],
    )
    assert upload["total_rows"] == 2 and upload["invalid_count"] == 1, upload
    print("4) staged:", {k: upload[k] for k in ("id", "kind", "total_rows", "valid_count", "invalid_count")})

    turn1 = call("POST", "/api/ai/chat", token, data={"conversation_id": cid, "message": "این فایل را بررسی کن و وارد کن"})
    pending_row_hint = 2
    print("5) assistant:", turn1["reply"][:180])
    tools_used = [s["tool"] for s in turn1["steps"]]
    assert "inspect_upload" in tools_used, tools_used
    assert "پایان قرارداد" in turn1["reply"], turn1["reply"]

    turn2 = call("POST", "/api/ai/chat", token, data={"conversation_id": cid, "message": f"پایان قراردادش ۱۴۰۶/۰۶/۰۱ است (ردیف {pending_row_hint})"})
    print("6) assistant:", turn2["reply"][:180])
    assert "patch_upload_rows" in [s["tool"] for s in turn2["steps"]]

    turn3 = call("POST", "/api/ai/chat", token, data={"conversation_id": cid, "message": "خب واردش کن"})
    assert turn3["pending"], turn3
    pending = turn3["pending"][0]
    print(f"7) pending action #{pending['id']}: {pending['tool']} — {pending['summary']}")

    confirm = call("POST", f"/api/ai/pending/{pending['id']}/confirm", token, data={})
    assert any(s["status"] == "confirmed" for s in confirm["steps"])
    print("8) confirmed:", confirm["reply"][:150])

    people = call("GET", f"/api/personnel?q=E2E-{RUN}A", token)
    assert people["total"] == 1, people
    assert people["items"][0]["full_name"] == "نریمان صالحی"
    assert people["items"][0]["contract_end_date"] == "2027-08-23"  # ۱۴۰۶/۰۶/۰۱
    people2 = call("GET", f"/api/personnel?q=E2E-{RUN}B", token)
    assert people2["total"] == 1
    print("9) both personnel imported; jalali date converted:", people["items"][0]["contract_end_date"])

    assert people["items"][0]["account_username"] == f"nariman{RUN}", people["items"]
    print("10) account created:", people["items"][0]["account_username"])

    audit = call("GET", "/api/audit-log?event_type=ai_tool_invoked", token)
    assert audit["total"] >= 3
    print("11) audit trail:", audit["total"], "ai_tool_invoked events")

    # تأییدِ دوباره ممکن نیست
    try:
        call("POST", f"/api/ai/pending/{pending['id']}/confirm", token, data={})
        raise AssertionError("دوباره تأیید شد!")
    except urllib.error.HTTPError as err:
        assert err.code == 409
    print("12) double-confirm rejected with 409")

    print("\nE2E API FLOW: ALL PASSED")


if __name__ == "__main__":
    main()
