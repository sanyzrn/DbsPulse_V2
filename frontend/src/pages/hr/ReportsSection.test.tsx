import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { apiClient } from "../../api/client";
import { ToastProvider } from "../../components/Toast";
import { ReportsSection } from "./ReportsSection";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    apiClient: { ...actual.apiClient, get: vi.fn() },
  };
});

function renderSection() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <ReportsSection />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const EMPTY_SUMMARY = {
  total_evaluations: 0,
  avg_final_pct: null,
  by_org_unit: [],
  by_indicator: [],
};

function mockLookups(get: ReturnType<typeof vi.fn>) {
  get.mockImplementation(async (url: string) => {
    if (url === "/personnel/org-units") return { data: [] };
    if (url === "/periods") return { data: [] };
    if (url === "/indicators") return { data: [] };
    throw new Error(`unexpected url: ${url}`);
  });
}

describe("ReportsSection — تفکیک خطای سرور از «بدون داده» (H-7)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("در خطای سرور، حالت خطا با تلاش دوباره نشان می‌دهد نه «بدون داده» و نه صفر", async () => {
    const get = vi.mocked(apiClient.get);
    mockLookups(get);
    get.mockImplementation(async (url: string) => {
      if (url === "/dashboard/report/summary") {
        throw Object.assign(new Error("request failed"), { response: { status: 500 } });
      }
      if (url === "/personnel/org-units") return { data: [] };
      if (url === "/periods") return { data: [] };
      if (url === "/indicators") return { data: [] };
      throw new Error(`unexpected url: ${url}`);
    });

    renderSection();

    // پیام خطا می‌آید — نه حالت خالیِ فیلترها (سه کارتِ وابسته به summary همه حالت خطا دارند)
    await waitFor(() => {
      const alerts = screen.getAllByRole("alert");
      expect(alerts.length).toBeGreaterThanOrEqual(3);
      for (const alert of alerts) {
        expect(alert).toHaveTextContent("دریافت گزارش با خطا مواجه شد");
      }
    });
    expect(screen.queryByText("برای فیلترهای فعلی داده‌ای وجود ندارد.")).toBeNull();
    // کارتِ «صفر ارزیابی» هم رندر نمی‌شود؛ CountUpِ صفر دروغِ خاموشِ خطاست
    expect(screen.queryByText("ارزیابی‌های نهایی‌شدهٔ منطبق با فیلتر")).toBeNull();

    // تلاش دوباره واقعاً دوباره می‌خواند
    const callsBefore = get.mock.calls.filter(([url]) => url === "/dashboard/report/summary").length;
    await userEvent.click(screen.getAllByRole("button", { name: "تلاش دوباره" })[0]!);
    await waitFor(() => {
      const callsAfter = get.mock.calls.filter(([url]) => url === "/dashboard/report/summary").length;
      expect(callsAfter).toBeGreaterThan(callsBefore);
    });
  });

  it("در نبودِ دادهٔ واقعی، همچنان حالت خالی عادی نشان داده می‌شود — نه خطا", async () => {
    const get = vi.mocked(apiClient.get);
    mockLookups(get);
    get.mockImplementation(async (url: string) => {
      if (url === "/dashboard/report/summary") return { data: EMPTY_SUMMARY };
      if (url === "/personnel/org-units") return { data: [] };
      if (url === "/periods") return { data: [] };
      if (url === "/indicators") return { data: [] };
      throw new Error(`unexpected url: ${url}`);
    });

    renderSection();

    await waitFor(() =>
      expect(screen.getAllByText("برای فیلترهای فعلی داده‌ای وجود ندارد.").length).toBeGreaterThan(0),
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
