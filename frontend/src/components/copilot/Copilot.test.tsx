import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Markdown } from "./Markdown";
import { PendingActionCard, StepTrace, UploadCard } from "./Cards";

function withProviders(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{node}</QueryClientProvider>;
}

// ── مارک‌داون ──────────────────────────────────────────────────────────────

describe("Markdown", () => {
  it("renders bold and inline code without raw markers", () => {
    render(<Markdown text="این **مهم** است و `کد` هم دارد." />);
    expect(screen.getByText("مهم").tagName).toBe("STRONG");
    expect(screen.getByText("کد").tagName).toBe("CODE");
    expect(document.body.textContent).not.toContain("**");
  });

  it("renders tables as real tables", () => {
    render(
      <Markdown
        text={"| واحد | میانگین |\n| --- | --- |\n| فروش | ۸۲ |"}
      />,
    );
    expect(screen.getByText("واحد").tagName).toBe("TH");
    expect(screen.getByText("فروش").tagName).toBe("TD");
  });

  it("renders lists and headings", () => {
    render(<Markdown text={"## عنوان\n- یکی\n- دومی"} />);
    expect(screen.getByText("عنوان")).toBeTruthy();
    expect(screen.getByText("یکی").tagName).toBe("LI");
    expect(screen.getByText("دومی").tagName).toBe("LI");
  });

  it("never interprets raw HTML", () => {
    render(<Markdown text={'<img src="x" onerror="alert(1)">'} />);
    expect(document.querySelector("img")).toBeNull();
  });
});

// ── کارتِ تأیید ────────────────────────────────────────────────────────────

const baseAction = {
  id: 7,
  tool: "create_personnel",
  summary: "ثبت «علی احمدی» با کد P-9 در واحد فروش",
  arguments: { full_name: "علی احمدی", personnel_code: "P-9" },
  status: "pending" as const,
};

describe("PendingActionCard", () => {
  it("offers confirm and reject while pending", () => {
    const onConfirm = vi.fn();
    const onReject = vi.fn();
    render(
      withProviders(
        <PendingActionCard action={baseAction} onConfirm={onConfirm} onReject={onReject} />,
      ),
    );
    fireEvent.click(screen.getByText("تأیید و انجام"));
    expect(onConfirm).toHaveBeenCalledWith(7);
    fireEvent.click(screen.getByText("رد"));
    expect(onReject).toHaveBeenCalledWith(7);
  });

  it("hides the decision buttons once decided", () => {
    render(
      withProviders(
        <PendingActionCard
          action={{ ...baseAction, status: "confirmed", result_text: "پرسنل ثبت شد" }}
          onConfirm={vi.fn()}
          onReject={vi.fn()}
        />,
      ),
    );
    expect(screen.queryByText("تأیید و انجام")).toBeNull();
    expect(screen.getByText("پرسنل ثبت شد")).toBeTruthy();
  });

  it("shows the payload only on demand", () => {
    render(
      withProviders(
        <PendingActionCard
          action={{ ...baseAction, arguments: { secret_note: "special-value-9912" } }}
          onConfirm={vi.fn()}
          onReject={vi.fn()}
        />,
      ),
    );
    expect(screen.queryByText(/9912/)).toBeNull();
    fireEvent.click(screen.getByText("جزئیاتِ پیشنهاد"));
    expect(screen.getByText(/9912/)).toBeTruthy();
  });
});

describe("StepTrace", () => {
  it("lists each step inside the collapsible trace", () => {
    render(
      <StepTrace
        steps={[
          { tool: "search_personnel", status: "ok", summary: "جست‌وجوی پرسنل (۳ نتیجه)" },
          { tool: "inspect_upload", status: "awaiting_confirmation", summary: "بازرسی فایل" },
        ]}
      />,
    );
    // jsdom محتوای <details> را رندر می‌کند؛ پس گام‌ها را قبل و بعد از بازکردن بررسی می‌کنیم
    expect(screen.getByText("جست‌وجوی پرسنل (۳ نتیجه)")).toBeTruthy();
    expect(screen.getByText("بازرسی فایل")).toBeTruthy();
    fireEvent.click(screen.getByText(/کاری که انجام شد/));
    expect(screen.getByText(/۲|2/)).toBeTruthy();
  });
});

describe("UploadCard", () => {
  it("shows row statistics for personnel workbooks", () => {
    render(
      <UploadCard
        upload={{ filename: "people.xlsx", kind: "personnel_import", total_rows: 12, valid_count: 10, invalid_count: 2 }}
      />,
    );
    expect(screen.getByText(/۱۲|12/)).toBeTruthy();
    expect(screen.getByText(/2 خطادار|۲ خطادار/)).toBeTruthy();
  });

  it("marks committed files", () => {
    render(
      <UploadCard upload={{ filename: "people.xlsx", kind: "personnel_import", committed: true }} />,
    );
    expect(screen.getByText("وارد شد")).toBeTruthy();
  });
});
