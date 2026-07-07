import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Button } from "./Button";
import { Card, EmptyState } from "./Card";

describe("Button", () => {
  it("defaults to type=button so it never submits a form by accident", () => {
    render(<Button>ذخیره</Button>);
    expect(screen.getByRole("button", { name: "ذخیره" })).toHaveAttribute("type", "button");
  });

  it("respects an explicit submit type and merges className", () => {
    render(
      <Button type="submit" className="extra">
        ثبت
      </Button>
    );
    const btn = screen.getByRole("button", { name: "ثبت" });
    expect(btn).toHaveAttribute("type", "submit");
    expect(btn.className).toContain("extra");
    expect(btn.className).toContain("bg-pulse-600");
  });

  it("secondary variant uses the outline style", () => {
    render(<Button variant="secondary">انصراف</Button>);
    expect(screen.getByRole("button", { name: "انصراف" }).className).toContain("border-gray-200");
  });
});

describe("Card", () => {
  it("renders title and children", () => {
    render(<Card title="عنوان">محتوا</Card>);
    expect(screen.getByRole("heading", { name: "عنوان" })).toBeInTheDocument();
    expect(screen.getByText("محتوا")).toBeInTheDocument();
  });
});

describe("EmptyState", () => {
  it("shows the default Persian empty message", () => {
    render(<EmptyState />);
    expect(screen.getByText("موردی یافت نشد.")).toBeInTheDocument();
  });
});
