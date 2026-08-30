import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { apiClient } from "../../api/client";
import { ConfirmProvider } from "../../components/ConfirmDialog";
import { ToastProvider } from "../../components/Toast";
import { AdministrationPage } from "./AdministrationPage";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    apiClient: { ...actual.apiClient, get: vi.fn(), put: vi.fn(), post: vi.fn(), patch: vi.fn() },
  };
});

vi.mock("../../auth/AuthContext", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../auth/AuthContext")>();
  return {
    ...actual,
    useAuth: () => ({
      user: {
        id: 1,
        username: "admin",
        display_name: "admin",
        role: "support",
        personnel_id: null,
        must_change_password: false,
      },
      loading: false,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    }),
  };
});

vi.mock("../../auth/PermissionsContext", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../auth/PermissionsContext")>();
  return { ...actual, usePermissions: () => ({ can: () => true, moduleEnabled: () => true }) };
});

const POLICY_FIELDS = [
  {
    key: "objection_window_days",
    label: "مهلت اعتراض کارمند (روز)",
    kind: "number",
    help: "از لحظهٔ نهایی‌شدن پرونده",
    value: 7,
    minimum: 1,
    maximum: 365,
  },
  {
    key: "min_cohort_size",
    label: "حداقل جمعیت برای نمایش میانگین",
    kind: "number",
    help: "",
    value: 5,
    minimum: 1,
    maximum: 100,
  },
];

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ToastProvider>
          <ConfirmProvider>
            <AdministrationPage />
          </ConfirmProvider>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function mockGets() {
  vi.mocked(apiClient.get).mockImplementation(async (url: string) => {
    if (url === "/administration/policy") return { data: { fields: POLICY_FIELDS } } as never;
    if (url === "/administration/integrations")
      return { data: { fields: [], secrets: [], active_channels: [] } } as never;
    if (url === "/administration/modules") return { data: [] } as never;
    if (url === "/administration/separation")
      return { data: { separated: true, overlapping_users: [] } } as never;
    if (url === "/org-units") return { data: [] } as never;
    if (url === "/personnel/sites") return { data: ["دفتر مرکزی"] } as never;
    return { data: [] } as never;
  });
}

async function openTab(name: string) {
  await userEvent.click(await screen.findByRole("tab", { name }));
}

describe("تب‌های مدیریت سامانه", () => {
  it("بخش‌ها را در تب‌های جداگانه نشان می‌دهد و فقط تب انتخاب‌شده را نمایش می‌دهد", async () => {
    mockGets();
    renderPage();

    const tabs = await screen.findAllByRole("tab");
    expect(tabs).toHaveLength(6);
    expect(screen.getByRole("tab", { name: "واحدهای سازمانی" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
});


describe("کارت قاعده‌های سازمانی", () => {
  it("کف و سقفِ سرور را روی خودِ ورودی می‌گذارد", async () => {
    // فرم باید همان قاعده‌ای را نشان بدهد که سرور اعمال می‌کند، نه اینکه کاربر
    // با ذخیره‌کردن کشفش کند.
    mockGets();
    renderPage();
    await openTab("قاعده‌های سازمانی");

    const input = await screen.findByLabelText(/مهلت اعتراض کارمند/);
    expect(input).toHaveAttribute("min", "1");
    expect(input).toHaveAttribute("max", "365");
    expect(input).toHaveValue(7);
  });

  it("فقط مقدارهای همین گروه را می‌فرستد", async () => {
    mockGets();
    vi.mocked(apiClient.put).mockResolvedValue({ data: { fields: POLICY_FIELDS } } as never);
    renderPage();
    await openTab("قاعده‌های سازمانی");

    const input = await screen.findByLabelText(/حداقل جمعیت/);
    await userEvent.clear(input);
    await userEvent.type(input, "8");
    await userEvent.click(screen.getByRole("button", { name: "ذخیرهٔ قاعده‌ها" }));

    await waitFor(() => expect(apiClient.put).toHaveBeenCalled());
    const [url, body] = vi.mocked(apiClient.put).mock.calls[0]!;
    expect(url).toBe("/administration/policy");
    expect((body as { values: Record<string, unknown> }).values).toMatchObject({
      min_cohort_size: 8,
      objection_window_days: 7,
    });
  });

  it("دکمهٔ ذخیره تا وقتی چیزی عوض نشده خاموش است", async () => {
    mockGets();
    renderPage();
    await openTab("قاعده‌های سازمانی");
    expect(await screen.findByRole("button", { name: "ذخیرهٔ قاعده‌ها" })).toBeDisabled();
  });
});
