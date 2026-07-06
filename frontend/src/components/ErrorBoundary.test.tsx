import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorBoundary } from "./ErrorBoundary";

function Boom(): never {
  throw new Error("boom");
}

describe("ErrorBoundary", () => {
  it("renders children normally when nothing throws", () => {
    render(
      <ErrorBoundary>
        <p>محتوای سالم</p>
      </ErrorBoundary>
    );
    expect(screen.getByText("محتوای سالم")).toBeInTheDocument();
  });

  it("catches a render error and shows the fallback instead of crashing the tree", () => {
    // React خودش هم این خطا را در کنسول لاگ می‌کند؛ برای تست تمیز آن را بی‌صدا می‌کنیم
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      render(
        <ErrorBoundary title="یک خطای سفارشی">
          <Boom />
        </ErrorBoundary>
      );
      expect(screen.getByText("یک خطای سفارشی")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "بارگذاری مجدد" })).toBeInTheDocument();
      expect(screen.queryByText("محتوای سالم")).not.toBeInTheDocument();
    } finally {
      consoleSpy.mockRestore();
    }
  });
});
