import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { EvaluationList } from "./EvaluationList";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, get: vi.fn() } };
});

function renderWithProviders(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

function mockPage(items: unknown[] = []) {
  return { data: { total: items.length, items } };
}

describe("EvaluationList tabs", () => {
  it("defaults to the first tab's status filter and switches status on tab click", async () => {
    const getMock = vi.mocked(apiClient.get);
    getMock.mockResolvedValue(mockPage());

    renderWithProviders(
      <EvaluationList
        title="پرونده‌های ارزیابی"
        tabs={[
          { key: "pending", label: "در انتظار تأیید نهایی", status: "deputy_approved" },
          { key: "finalized", label: "نهایی‌شده", status: "finalized" },
          { key: "all", label: "همهٔ پرونده‌های من" },
        ]}
      />
    );

    await waitFor(() => expect(getMock).toHaveBeenCalled());
    expect(getMock.mock.calls[0]?.[1]?.params).toMatchObject({ status: "deputy_approved" });

    await userEvent.click(screen.getByRole("tab", { name: "همهٔ پرونده‌های من" }));

    await waitFor(() =>
      expect(getMock.mock.calls.at(-1)?.[1]?.params).toMatchObject({ status: undefined })
    );
  });

  it("does not render a tab bar when only one tab is given", async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockPage());
    renderWithProviders(<EvaluationList title="ارزیابی‌های من" tabs={[{ key: "all", label: "همه" }]} />);
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
  });
});
