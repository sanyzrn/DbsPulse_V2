import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { apiClient } from "../../api/client";
import { ConfirmProvider } from "../../components/ConfirmDialog";
import { ToastProvider } from "../../components/Toast";
import { UsersPage } from "./UsersPage";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    apiClient: { ...actual.apiClient, get: vi.fn(), patch: vi.fn(), post: vi.fn() },
  };
});

// صفحه برای محافظ «قفل‌نشدن حساب خود» به کاربر فعلی نیاز دارد
vi.mock("../../auth/AuthContext", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../auth/AuthContext")>();
  return {
    ...actual,
    useAuth: () => ({
      user: {
        id: 999,
        username: "hr-admin",
        role: "hr",
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

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ToastProvider>
          <ConfirmProvider>
            <UsersPage />
          </ConfirmProvider>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("UsersPage edit modal", () => {
  it("opens the edit modal for an existing user and submits a role + password change", async () => {
    const getMock = vi.mocked(apiClient.get);
    const patchMock = vi.mocked(apiClient.patch);
    getMock.mockImplementation(async (url: string) => {
      if (url === "/users") {
        return {
          data: {
            total: 1,
            items: [{ id: 1, username: "sup1", role: "unit_supervisor", is_active: true, personnel_id: null, created_at: "" }],
          },
        };
      }
      if (url === "/personnel") {
        return { data: { total: 0, items: [] } };
      }
      throw new Error(`unexpected GET ${url}`);
    });
    patchMock.mockResolvedValue({ data: {} });

    renderPage();

    await screen.findByText("sup1");
    await userEvent.click(screen.getByRole("button", { name: "ویرایش" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("ویرایش کاربر: sup1")).toBeInTheDocument();

    await userEvent.selectOptions(within(dialog).getByLabelText("نقش"), "hr");
    await userEvent.type(within(dialog).getByLabelText(/تعیین رمز جدید/), "NewPassword123");
    await userEvent.click(within(dialog).getByRole("button", { name: "ذخیره" }));

    await waitFor(() =>
      expect(patchMock).toHaveBeenCalledWith("/users/1", {
        role: "hr",
        personnel_id: null,
        password: "NewPassword123",
      })
    );
  });
});
