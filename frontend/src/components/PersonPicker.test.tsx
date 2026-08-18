import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PersonPicker } from "./PersonPicker";
import type { Personnel } from "../types";

function person(id: number, full_name: string, over: Partial<Personnel> = {}): Personnel {
  return {
    id,
    personnel_code: `P-${id}`,
    full_name,
    job_title: "کارشناس",
    is_manager: false,
    org_unit: "فروش",
    contract_start_date: "2025-01-01",
    contract_end_date: "2026-01-01",
    status: "active",
    separation_date: null,
    separation_reason: null,
    created_at: "",
    updated_at: "",
    ...over,
  };
}

const ALL = [
  person(1, "علی محمدی"),
  person(2, "مریم حسینی", { org_unit: "کنترل کیفیت" }),
  person(3, "نسرین بیات", { org_unit: "فروش" }),
];

const get = vi.fn();
vi.mock("../api/client", () => ({
  apiClient: {
    get: (...args: unknown[]) => get(...args),
  },
  extractErrorMessage: (e: unknown) => String(e),
}));

/** جست‌وجو سمت سرور است؛ این‌جا همان قرارداد را شبیه‌سازی می‌کنیم. */
function mockServer(pageSize = 12) {
  get.mockImplementation((url: string, config?: { params?: Record<string, unknown> }) => {
    const detail = /\/personnel\/(\d+)$/.exec(url);
    if (detail) {
      const found = ALL.find((p) => p.id === Number(detail[1]));
      return found ? Promise.resolve({ data: found }) : Promise.reject(new Error("404"));
    }
    const q = (config?.params?.q as string | undefined)?.trim();
    const matched = q
      ? ALL.filter((p) => p.full_name.includes(q) || p.personnel_code.includes(q))
      : ALL;
    return Promise.resolve({
      data: { total: matched.length, items: matched.slice(0, pageSize) },
    });
  });
}

function renderPicker(props: Partial<Parameters<typeof PersonPicker>[0]> = {}) {
  const onChange = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <PersonPicker value={null} onChange={onChange} {...props} />
    </QueryClientProvider>,
  );
  return { onChange };
}

beforeEach(() => {
  get.mockReset();
  mockServer();
});

describe("PersonPicker", () => {
  it("جست‌وجو را به سرور می‌فرستد — نه فیلترِ سمت کلاینت روی یک فهرست از پیش واکشی‌شده", async () => {
    // دلیل وجود این کامپوننت: <select> قبلی روی limit:1000 بود، یعنی با بزرگ‌شدن
    // سازمان هم کند می‌شد هم ناقص.
    renderPicker();
    fireEvent.click(screen.getByRole("combobox"));

    fireEvent.change(await screen.findByLabelText("جست‌وجوی پرسنل"), {
      target: { value: "مریم" },
    });

    await waitFor(() => {
      const calls = get.mock.calls.filter(([url]) => url === "/personnel");
      const last = calls.at(-1)?.[1]?.params;
      expect(last?.q).toBe("مریم");
      expect(last?.limit).toBe(12);
    });
  });

  it("انتخاب با کلیک، شناسه را برمی‌گرداند و فهرست را می‌بندد", async () => {
    const { onChange } = renderPicker();
    fireEvent.click(screen.getByRole("combobox"));

    fireEvent.click(await screen.findByText("نسرین بیات"));

    expect(onChange).toHaveBeenCalledWith(3);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("با صفحه‌کلید هم می‌شود انتخاب کرد", async () => {
    const { onChange } = renderPicker();
    const box = screen.getByRole("combobox");
    fireEvent.click(box);
    await screen.findByText("علی محمدی"); // تا نتایج نرسیده‌اند، حرکت نشانگر معنا ندارد

    fireEvent.keyDown(box, { key: "ArrowDown" }); // → ردیف دوم
    fireEvent.keyDown(box, { key: "Enter" });

    expect(onChange).toHaveBeenCalledWith(2);
  });

  it("نام فرد انتخاب‌شده را نشان می‌دهد حتی وقتی در نتایج جست‌وجوی فعلی نیست", async () => {
    // بدون واکشی جداگانهٔ خودِ فرد، دکمه پس از تایپِ عبارتی دیگر به حالت
    // «انتخاب‌نشده» برمی‌گشت و کاربر فکر می‌کرد انتخابش پریده است.
    renderPicker({ value: 2 });

    expect(await screen.findByText(/مریم حسینی/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("combobox"));
    fireEvent.change(await screen.findByLabelText("جست‌وجوی پرسنل"), {
      target: { value: "علی" },
    });

    expect(await screen.findByText(/مریم حسینی/)).toBeInTheDocument();
  });

  it("دکمهٔ حذف انتخاب، مقدار را پاک می‌کند", async () => {
    const { onChange } = renderPicker({ value: 1 });

    fireEvent.click(await screen.findByLabelText("حذف انتخاب فرد"));

    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("وقتی نتیجه‌ای نیست، پیام روشن می‌دهد", async () => {
    renderPicker();
    fireEvent.click(screen.getByRole("combobox"));
    fireEvent.change(await screen.findByLabelText("جست‌وجوی پرسنل"), {
      target: { value: "کسی که نیست" },
    });

    expect(await screen.findByText(/پیدا نشد/)).toBeInTheDocument();
  });

  it("وقتی نتایج بیشتر از صفحهٔ اول است، صریح می‌گوید فهرست کامل نیست", async () => {
    mockServer(2); // سرور فقط ۲ تا از ۳ را برمی‌گرداند
    renderPicker();
    fireEvent.click(screen.getByRole("combobox"));

    expect(await screen.findByText(/نتیجهٔ نخست از/)).toBeInTheDocument();
  });
});
