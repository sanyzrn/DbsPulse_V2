import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { apiClient } from "../../api/client";
import { ConfirmProvider } from "../../components/ConfirmDialog";
import { ToastProvider } from "../../components/Toast";
import { PersonnelPage } from "./PersonnelPage";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    apiClient: { ...actual.apiClient, get: vi.fn(), patch: vi.fn(), post: vi.fn() },
  };
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ToastProvider>
          <ConfirmProvider>
            <PersonnelPage />
          </ConfirmProvider>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const SAMPLE_PERSONNEL = {
  id: 1,
  personnel_code: "P-1",
  full_name: "کارمند تست",
  job_title: "کارشناس",
  is_manager: false,
  org_unit: "واحد فروش",
  contract_start_date: "2025-01-01",
  contract_end_date: "2026-01-01",
  status: "active" as const,
  created_at: "",
  updated_at: "",
};

describe("PersonnelPage edit modal", () => {
  it("opens the edit modal and submits an updated job title + status", async () => {
    const getMock = vi.mocked(apiClient.get);
    const patchMock = vi.mocked(apiClient.patch);
    getMock.mockImplementation(async (url: string) => {
      if (url === "/personnel") {
        return { data: { total: 1, items: [SAMPLE_PERSONNEL] } };
      }
      if (url === "/users") {
        return { data: { total: 0, items: [] } };
      }
      throw new Error(`unexpected GET ${url}`);
    });
    patchMock.mockResolvedValue({ data: {} });

    renderPage();

    await screen.findByText("کارمند تست");
    await userEvent.click(screen.getByRole("button", { name: "ویرایش" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("ویرایش پرسنل: کارمند تست")).toBeInTheDocument();

    const jobTitleInput = within(dialog).getByLabelText("عنوان شغلی");
    await userEvent.clear(jobTitleInput);
    await userEvent.type(jobTitleInput, "کارشناس ارشد");
    await userEvent.selectOptions(within(dialog).getByLabelText("وضعیت"), "inactive");
    await userEvent.click(within(dialog).getByRole("button", { name: "ذخیره" }));

    await waitFor(() =>
      expect(patchMock).toHaveBeenCalledWith(
        "/personnel/1",
        expect.objectContaining({ job_title: "کارشناس ارشد", status: "inactive" })
      )
    );
  });
});
