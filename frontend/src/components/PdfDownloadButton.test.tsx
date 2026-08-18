/** کارنامهٔ رسمی باید از مسیرِ احراز هویت‌شده گرفته شود.
 *
 * این تست وجود دارد چون پنل کارمند یک `<a href="/api/…">` ساده بود. مرورگر روی
 * ناوبری معمولی هدر `Authorization` نمی‌فرستد — آن را اینترسپتور axios اضافه
 * می‌کند و تگ لینک از آن عبور نمی‌کند — پس کارمند به‌جای سندِ خودش این را
 * می‌دید:
 *
 *     {"detail":"توکن نامعتبر یا منقضی‌شده است"}
 *
 * شکستِ دوباره‌اش هم بی‌صداست: کد کامپایل می‌شود، صفحه رندر می‌شود، و خطا فقط
 * وقتی دیده می‌شود که یک آدم واقعی روی دکمه کلیک کند.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { apiClient } from "../api/client";
import { PdfDownloadButton } from "./PdfDownloadButton";
import { ToastProvider } from "./Toast";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, get: vi.fn() } };
});

function renderButton() {
  return render(
    <ToastProvider>
      <PdfDownloadButton evaluationId={42} filename="EV-1405-0042.pdf" />
    </ToastProvider>
  );
}

describe("PdfDownloadButton", () => {
  it("fetches the PDF through the authenticated client", async () => {
    const getMock = vi.mocked(apiClient.get);
    getMock.mockResolvedValue({ data: new Blob(["%PDF-1.4"], { type: "application/pdf" }) });
    // jsdom نه createObjectURL دارد نه پنجرهٔ تازه باز می‌کند.
    URL.createObjectURL = vi.fn(() => "blob:fake");
    URL.revokeObjectURL = vi.fn();
    const openMock = vi.fn(() => ({ location: { href: "" } }));
    vi.stubGlobal("open", openMock);

    renderButton();
    await userEvent.click(screen.getByRole("button"));

    await waitFor(() =>
      expect(getMock).toHaveBeenCalledWith("/evaluations/42/summary.pdf", {
        responseType: "blob",
      })
    );
    vi.unstubAllGlobals();
  });

  it("is not a plain link, which would drop the auth header", () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: new Blob() });
    const { container } = renderButton();
    // نه فقط «دکمه هست»، بلکه «هیچ لینکی به /api نیست» — چون همان لینک بود که
    // درخواست را بدون توکن می‌فرستاد.
    expect(container.querySelector('a[href*="/api/"]')).toBeNull();
    expect(screen.getByRole("button")).toBeInTheDocument();
  });
});
