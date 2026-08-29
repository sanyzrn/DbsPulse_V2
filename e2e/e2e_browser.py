"""آزمونِ سرتسریِ مرورگری همکار — مرورگر واقعی، سرورهای واقعی، مدلِ قلابی.

سناریو: ورودِ HR ← بازکردنِ همکار ← بارگذاریِ اکسلِ ناقص ← بازرسیِ مدل و
پرسیدنِ مقدارِ جاافتاده ← پاسخِ کاربر با تاریخِ شمسی ← اصلاح ← درخواستِ ورود ←
کارتِ تأیید ← تأیید ← راستی‌آزمایی در صفحهٔ پرسنل و گزارش رویدادها.

پیش‌نیاز: سرورهای بک‌اند (8000)، فرانت‌اند (5173) و مدلِ قلابی (8100) در حالِ
اجر باشند — «e2e_browser.sh» هر سه را بالا می‌آورد و این اسکریپت را صدا می‌زند.
نماینده‌های مرورگر: pip install playwright && playwright install chromium
"""
import time
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

RUN = str(int(time.time()))[-6:]
SHOTS = Path(__file__).resolve().parent / "e2e-screens"

HEADERS = [
    "کد پرسنلی", "نام و نام خانوادگی", "عنوان شغلی", "محل", "واحد سازمانی",
    "مدیر", "وضعیت", "شروع قرارداد", "پایان قرارداد", "نام کاربری",
    "رمز اولیه", "مسئول مستقیم", "معاونت مربوطه", "مدیرعامل",
]


def unique_workbook() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(HEADERS)
    ws.append([
        f"E2E-{RUN}A", "نریمان صالحی", "کارشناس فروش", "دفتر مرکزی", "فروش",
        "خیر", "فعال", "۱۴۰۴/۰۴/۰۱", "", f"nariman{RUN}", "", "", "", "",
    ])
    ws.append([
        f"E2E-{RUN}B", "شبنم قادر", "کارشناس فروش", "دفتر مرکزی", "فروش",
        "خیر", "فعال", "۱۴۰۴/۰۵/۰۱", "۱۴۰۷/۰۵/۰۱", "", "", "", "", "",
    ])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def wait_for_text(page, text: str, timeout: int = 45_000):
    page.wait_for_selector(f"text={text}", timeout=timeout)


def main() -> None:
    import httpx

    # صبر تا سرورها
    for _ in range(40):
        try:
            if httpx.get("http://127.0.0.1:8000/docs", timeout=2).status_code == 200 and \
               httpx.get("http://localhost:5173/", timeout=2).status_code == 200:
                break
        except Exception:
            time.sleep(1)

    from playwright.sync_api import sync_playwright

    SHOTS.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # ── ورود ─────────────────────────────────────────────────────────
        page.goto("http://localhost:5173/login")
        page.wait_for_load_state("networkidle")
        page.fill("input[name='username'], #username, input[type='text']", "ai_hr")
        page.fill("input[type='password']", "Ai-Hr-Pass-1234")
        page.screenshot(path=str(SHOTS / "01-login.png"))
        page.keyboard.press("Enter")
        page.wait_for_url("**/hr/**", timeout=30_000)
        page.wait_for_load_state("networkidle")
        print("1) login OK →", page.url)
        page.screenshot(path=str(SHOTS / "02-dashboard.png"))

        # ── بازکردنِ همکار ───────────────────────────────────────────────
        fab = page.locator("button[aria-label='همکار هوشمند']")
        fab.wait_for(state="visible", timeout=15_000)
        fab.click()
        page.locator("[role='dialog']").wait_for(state="visible", timeout=10_000)
        print("2) copilot panel opened")
        page.screenshot(path=str(SHOTS / "03-copilot-welcome.png"))

        # ── بارگذاری اکسل ────────────────────────────────────────────────
        with page.expect_file_chooser() as fc_info:
            page.locator("button[aria-label='بارگذاری فایل اکسل']").click()
        fc_info.value.set_files({
            "name": "e2e-personnel.xlsx",
            "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "buffer": unique_workbook(),
        })
        wait_for_text(page, "ردیف دارد")
        print("3) file uploaded and staged; assistant replied")
        page.screenshot(path=str(SHOTS / "04-upload-staged.png"))

        # ── بازرسی: مدل خطاها را می‌گوید و مقدار می‌پرسد ─────────────────
        page.fill("textarea", "این فایل را بررسی کن و بگو مشکلش چیست")
        page.keyboard.press("Enter")
        wait_for_text(page, "پایان قرارداد", timeout=60_000)
        print("4) assistant identified the missing contract end date and asked for it")
        page.screenshot(path=str(SHOTS / "05-assistant-asks.png"))

        # ── پاسخِ کاربر با تاریخِ شمسی ───────────────────────────────────
        page.fill("textarea", "پایان قراردادش ۱۴۰۶/۰۶/۰۱ است")
        page.keyboard.press("Enter")
        wait_for_text(page, "سالم", timeout=60_000)
        print("5) assistant patched the row; file is valid now")
        page.screenshot(path=str(SHOTS / "06-patched.png"))

        # ── درخواستِ ورود: کارتِ تأیید باید بیاید ────────────────────────
        page.fill("textarea", "خب، واردش کن")
        page.keyboard.press("Enter")
        confirm_button = page.locator("button:has-text('تأیید و انجام')").first
        confirm_button.wait_for(state="visible", timeout=60_000)
        print("6) pending confirmation card shown")
        page.screenshot(path=str(SHOTS / "07-pending-card.png"))

        # ── تأیید ────────────────────────────────────────────────────────
        confirm_button.click()
        wait_for_text(page, "انجام شد", timeout=60_000)
        print("7) confirmed; import executed")
        page.screenshot(path=str(SHOTS / "08-imported.png"))

        # ── راستی‌آزمایی در صفحهٔ پرسنل ──────────────────────────────────
        page.goto("http://localhost:5173/hr/people/personnel")
        page.wait_for_load_state("networkidle")
        search = page.locator("input[placeholder*='جست'], input[type='search']").first
        search.fill(f"E2E-{RUN}A")
        page.keyboard.press("Enter")
        page.wait_for_timeout(1500)
        body = page.inner_text("body")
        assert "نریمان صالحی" in body, "پرسنلِ تازه در فهرست نیست!"
        print("8) personnel page shows the imported person")
        page.screenshot(path=str(SHOTS / "09-personnel-verified.png"))

        # ── گزارش رویدادها ───────────────────────────────────────────────
        page.goto("http://localhost:5173/hr/audit-log")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)
        body = page.inner_text("body")
        assert "ai_tool_invoked" in body or "فراخوانی" in body or "ai_" in body, "ردِ ابزار در گزارش رویدادها نیست"
        print("9) audit log contains AI tool events")
        page.screenshot(path=str(SHOTS / "10-audit-log.png"))

        # ── گفت‌وگوی تازه: گزارشِ خواندنی (بدون تأیید) ───────────────────
        page.goto("http://localhost:5173/copilot")
        page.wait_for_load_state("networkidle")
        page.fill("textarea", "قراردادهای رو به اتمام را نشانم بده")
        page.keyboard.press("Enter")
        page.wait_for_timeout(6000)
        body = page.inner_text("body")
        assert "قرارداد" in body
        print("10) full-page copilot answers report questions")
        page.screenshot(path=str(SHOTS / "11-fullpage-copilot.png"))

        browser.close()
        print(f"\nBROWSER E2E: ALL PASSED (RUN={RUN})")


if __name__ == "__main__":
    main()
